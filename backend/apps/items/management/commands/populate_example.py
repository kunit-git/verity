"""
Management command: populate_example

Wipes example vaults (if they exist), then populates two realistic examples:

1. **AV System** — an Autonomous Vehicle System organised around document
   deliverables: plans, specifications, FMEA analyses, risk assessments,
   and verification & validation reports.

2. **Avionics FMS** — a Flight Management System development programme
   following DO-178C, ARP4754A, and ARP4761, including system & software
   requirements, functional hazard assessment, FMEA, verification, and
   DO-326A security assessment.

Item types used (per vault):
  Project, Plan, Specification, Report, Analysis, Information,
  Requirement, Risk, Test Case, Failure Mode, Failure Cause,
  Threat, Vulnerability, Mitigation
Relation types:
  Built-in:  is_composed_of, traces_to
  Custom:    verifies, derives_from, refines, mitigates, causes, exploits

Usage:
    python manage.py populate_example
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.items.models import CustomFieldDefinition, CustomFieldValue, DocumentTemplate, Item, ItemType
from apps.matrices.models import Matrix, MatrixColumn
from apps.relations.models import ItemRelation, RelationType
from apps.vaults.models import Vault, VaultAuditLog, VaultMembership

User = get_user_model()


class Command(BaseCommand):
    help = "Populate example vaults (AV System + Avionics FMS)"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _item(self, type_slug, title, description="", status="active", **custom):
        """Create an Item and its CustomFieldValues."""
        item_type = self._types[type_slug]
        item = Item.objects.create(
            item_type=item_type,
            title=title,
            description=description,
            status=status,
            created_by=self._author,
        )
        field_defs = {
            fd.slug: fd
            for fd in CustomFieldDefinition.objects.filter(item_type=item_type)
        }
        for slug, value in custom.items():
            if slug in field_defs:
                CustomFieldValue.objects.create(
                    item=item, field_definition=field_defs[slug], value=value
                )
        return item

    def _rel(self, relation_name, source, target):
        """Create a directional ItemRelation."""
        ItemRelation.objects.create(
            relation_type=self._relations[relation_name],
            source=source,
            target=target,
            created_by=self._author,
        )

    def _compose(self, parent, *children):
        """Shorthand: parent is_composed_of each child."""
        for child in children:
            self._rel("is_composed_of", parent, child)

    def _verifies(self, test_case, *requirements):
        """Shorthand: test_case verifies each requirement."""
        for req in requirements:
            self._rel("verifies", test_case, req)

    def _derives(self, child_req, *parent_reqs):
        """Shorthand: child_req derives_from each parent_req."""
        for parent in parent_reqs:
            self._rel("derives_from", child_req, parent)

    def _mitigates(self, source, *targets):
        """Shorthand: source mitigates each target."""
        for target in targets:
            self._rel("mitigates", source, target)

    def _refines(self, parent_req, *child_reqs):
        """Shorthand: parent_req refines each child_req."""
        for child in child_reqs:
            self._rel("refines", parent_req, child)

    def _causes(self, cause, *modes):
        """Shorthand: cause causes each failure mode."""
        for mode in modes:
            self._rel("causes", cause, mode)

    def _exploits(self, threat, *vulnerabilities):
        """Shorthand: threat exploits each vulnerability."""
        for vuln in vulnerabilities:
            self._rel("exploits", threat, vuln)

    def _matrix(self, name, description, columns):
        """
        Create a Matrix with its columns.

        columns is a list of dicts, one per column in order (position 0 first).
        Seed column (position 0) keys: label, seed_item_type_slug, seed_container (Item, optional).
        Traversal column keys: label, relation_name, direction.
        """
        matrix = Matrix.objects.create(
            name=name,
            description=description,
            created_by=self._author,
            vault=self._vault,
        )
        for position, col in enumerate(columns):
            if position == 0:
                MatrixColumn.objects.create(
                    matrix=matrix,
                    position=0,
                    label=col["label"],
                    column_kind=MatrixColumn.Kind.SEED,
                    seed_item_type=self._types[col["seed_item_type_slug"]],
                    seed_container=col.get("seed_container"),
                )
            else:
                MatrixColumn.objects.create(
                    matrix=matrix,
                    position=position,
                    label=col["label"],
                    column_kind=MatrixColumn.Kind.TRAVERSAL,
                    relation_type=self._relations[col["relation_name"]],
                    direction=col["direction"],
                )
        return matrix

    # ------------------------------------------------------------------
    # Vault lifecycle helpers
    # ------------------------------------------------------------------

    def _wipe_vault(self, slug):
        """Wipe a single vault and all its data (if it exists)."""
        from apps.items.models import ItemVersion
        from apps.mailbox.models import MailboxArtifact

        old_vault = Vault.all_objects.filter(slug=slug).first()
        if old_vault:
            self.stdout.write(f"Wiping vault '{old_vault.name}'...")
            vault_types = ItemType.all_objects.filter(vault=old_vault)
            vault_items = Item.all_objects.filter(item_type__vault=old_vault)
            vault_field_defs = CustomFieldDefinition.all_objects.filter(item_type__vault=old_vault)

            MatrixColumn.all_objects.filter(matrix__vault=old_vault).hard_delete()
            Matrix.all_objects.filter(vault=old_vault).hard_delete()
            ItemRelation.all_objects.filter(relation_type__vault=old_vault).hard_delete()
            CustomFieldValue.all_objects.filter(field_definition__in=vault_field_defs).hard_delete()
            ItemVersion.all_objects.filter(item__in=vault_items).hard_delete()
            vault_items.hard_delete()
            DocumentTemplate.all_objects.filter(item_type__in=vault_types).hard_delete()
            vault_field_defs.hard_delete()
            vault_types.hard_delete()
            RelationType.all_objects.filter(vault=old_vault).hard_delete()
            MailboxArtifact.all_objects.filter(vault=old_vault).hard_delete()
            VaultAuditLog.objects.filter(vault=old_vault).delete()
            VaultMembership.all_objects.filter(vault=old_vault).hard_delete()
            old_vault.hard_delete()
            self.stdout.write("  Done.\n")
        else:
            self.stdout.write(f"No existing '{slug}' vault found, creating fresh.\n")

    def _setup_vault_schema(self, admin):
        """
        Create item types, custom fields, custom relation types, and
        document templates for ``self._vault``.  Populates ``self._types``
        and ``self._relations``.
        """
        # Built-in relation types already created by Vault.save()
        self._relations = {r.name: r for r in RelationType.objects.filter(vault=self._vault)}

        # Ensure is_composed_of has no source type constraint
        rt = self._relations["is_composed_of"]
        rt.source_item_type = None
        rt.target_item_type = None
        rt.save(update_fields=["source_item_type", "target_item_type"])

        # -- Item types ---------------------------------------------------
        item_types = [
            ("Project", "project", "A top-level project grouping all deliverables.", "briefcase"),
            ("Plan", "plan", "A planning document such as a development plan, risk management plan, or verification plan.", "clipboard-list"),
            ("Specification", "specification", "A requirements or design specification document.", "book-open"),
            ("Report", "report", "A report document such as a verification report, validation report, or risk assessment.", "file-bar-chart"),
            ("Analysis", "analysis", "An analysis document such as an FMEA, FTA, or HAZOP study.", "microscope"),
            ("Requirement", "requirement", "A system or stakeholder requirement.", "file-text"),
            ("Risk", "risk", "A potential risk to the system or project.", "alert-triangle"),
            ("Test Case", "test-case", "A test case for verification or validation.", "check-square"),
            ("Failure Mode", "failure-mode", "A potential failure mode of the system.", "x-circle"),
            ("Failure Cause", "failure-cause", "A root cause of a failure mode.", "zap"),
            ("Threat", "threat", "A cybersecurity threat scenario describing an attack vector or threat agent.", "shield-alert"),
            ("Vulnerability", "vulnerability", "A weakness in the system that could be exploited by a threat.", "shield-off"),
            ("Mitigation", "mitigation", "A security or safety control measure that reduces risk.", "shield-check"),
            ("Information", "information", "A textual section within a document, such as Purpose, Scope, or Definitions.", "text"),
        ]
        self._types = {}
        for name, slug, desc, icon in item_types:
            obj, created = ItemType.objects.get_or_create(
                vault=self._vault,
                slug=slug,
                defaults={"name": name, "description": desc, "icon": icon},
            )
            self._types[slug] = obj
            status = "Created" if created else "Exists"
            self.stdout.write(f"  {status}: ItemType '{name}'")

        # -- Custom fields ------------------------------------------------
        custom_fields = [
            ("project", "Standard Reference", "standard-reference", "text", False, {}),
            ("plan", "Standard Reference", "standard-reference", "text", False, {}),
            ("plan", "Phase", "phase", "choice", False, {"choices": ["Draft", "Review", "Approved", "Superseded"]}),
            ("specification", "Standard Reference", "standard-reference", "text", False, {}),
            ("specification", "Baseline", "baseline", "text", False, {}),
            ("report", "Report Date", "report-date", "date", False, {}),
            ("report", "Status", "report-status", "choice", False, {"choices": ["Draft", "Under Review", "Final", "Superseded"]}),
            ("analysis", "Method", "method", "choice", False, {"choices": ["FMEA", "FTA", "HAZOP", "SOTIF", "HARA", "Other"]}),
            ("analysis", "Standard Reference", "standard-reference", "text", False, {}),
            ("requirement", "Priority", "priority", "choice", False, {"choices": ["Low", "Medium", "High", "Critical"]}),
            ("requirement", "Verification Method", "verification-method", "choice", False, {"choices": ["Test", "Analysis", "Inspection", "Demonstration"]}),
            ("risk", "Severity", "severity", "choice", False, {"choices": ["Low", "Medium", "High", "Critical"]}),
            ("risk", "Likelihood", "likelihood", "choice", False, {"choices": ["Rare", "Unlikely", "Possible", "Likely", "Almost Certain"]}),
            ("risk", "Mitigation", "mitigation", "text", False, {}),
            ("test-case", "Test Steps", "test-steps", "text", False, {}),
            ("test-case", "Expected Result", "expected-result", "text", False, {}),
            ("failure-mode", "Severity", "severity", "choice", False, {"choices": ["Low", "Medium", "High", "Critical"]}),
            ("failure-cause", "Category", "category", "choice", False, {"choices": ["Design", "Manufacturing", "Environmental", "Human Error", "Software"]}),
            ("threat", "Threat Level", "threat-level", "choice", False, {"choices": ["Low", "Medium", "High", "Critical"]}),
            ("threat", "Attack Vector", "attack-vector", "choice", False, {"choices": ["Network", "Adjacent", "Local", "Physical"]}),
            ("threat", "Threat Agent", "threat-agent", "text", False, {}),
            ("vulnerability", "Severity", "severity", "choice", False, {"choices": ["Low", "Medium", "High", "Critical"]}),
            ("vulnerability", "Attack Feasibility", "attack-feasibility", "choice", False, {"choices": ["Low", "Medium", "High", "Very High"]}),
            ("vulnerability", "Component", "component", "text", False, {}),
            ("mitigation", "Control Type", "control-type", "choice", False, {"choices": ["Preventive", "Detective", "Corrective", "Deterrent"]}),
            ("mitigation", "Implementation Status", "implementation-status", "choice", False, {"choices": ["Planned", "In Progress", "Implemented", "Verified"]}),
        ]
        for type_slug, name, slug, kind, required, options in custom_fields:
            item_type = self._types[type_slug]
            _, created = CustomFieldDefinition.objects.get_or_create(
                item_type=item_type,
                slug=slug,
                defaults={
                    "name": name,
                    "field_kind": kind,
                    "is_required": required,
                    "options": options,
                },
            )
            status = "Created" if created else "Exists"
            self.stdout.write(f"  {status}: CustomField '{type_slug}.{name}'")

        # -- Custom relation types ----------------------------------------
        custom_rels = [
            {
                "kind": "trace",
                "name": "verifies",
                "forward_label": "verifies",
                "reverse_label": "is verified by",
                "description": "A test case verifies a requirement.",
                "source_item_type": self._types["test-case"],
                "target_item_type": self._types["requirement"],
            },
            {
                "kind": "trace",
                "name": "derives_from",
                "forward_label": "derives from",
                "reverse_label": "is parent of",
                "description": "A lower-level requirement derives from a higher-level requirement.",
                "source_item_type": self._types["requirement"],
                "target_item_type": self._types["requirement"],
            },
            {
                "kind": "composition",
                "name": "refines",
                "forward_label": "is refined by",
                "reverse_label": "refines",
                "description": "A high-level requirement is refined into lower-level sub-requirements that together fulfil it.",
                "source_item_type": self._types["requirement"],
                "target_item_type": self._types["requirement"],
            },
            {
                "kind": "trace",
                "name": "mitigates",
                "forward_label": "mitigates",
                "reverse_label": "is mitigated by",
                "description": "A risk or control mitigates a failure mode or requirement gap.",
                "source_item_type": None,
                "target_item_type": None,
            },
            {
                "kind": "trace",
                "name": "causes",
                "forward_label": "causes",
                "reverse_label": "is caused by",
                "description": "A failure cause leads to a failure mode.",
                "source_item_type": self._types["failure-cause"],
                "target_item_type": self._types["failure-mode"],
            },
            {
                "kind": "trace",
                "name": "exploits",
                "forward_label": "exploits",
                "reverse_label": "is exploited by",
                "description": "A threat exploits a vulnerability.",
                "source_item_type": self._types["threat"],
                "target_item_type": self._types["vulnerability"],
            },
        ]
        for cr in custom_rels:
            obj, created = RelationType.objects.update_or_create(
                vault=self._vault,
                name=cr["name"],
                defaults={
                    "kind": cr["kind"],
                    "forward_label": cr["forward_label"],
                    "reverse_label": cr["reverse_label"],
                    "description": cr["description"],
                    "source_item_type": cr["source_item_type"],
                    "target_item_type": cr["target_item_type"],
                    "is_builtin": False,
                },
            )
            self._relations[cr["name"]] = obj
            tag = "Created" if created else "Updated"
            self.stdout.write(f"  {tag} custom relation type: {cr['name']}")

        # -- Document templates -------------------------------------------
        self.stdout.write("Seeding document templates...")
        doc_templates = [
            (
                "information",
                "{{heading}} {{title}}\n\n{{description}}\n",
            ),
            (
                "requirement",
                "{{heading}} {{title}}\n\n"
                "| Field | Value |\n"
                "|---|---|\n"
                "| **Status** | {{status}} |\n"
                "| **Priority** | {{priority}} |\n"
                "| **Verification Method** | {{verification-method}} |\n"
                "| **Version** | {{current_version}} |\n\n"
                "{{description}}\n",
            ),
            (
                "risk",
                "{{heading}} {{title}}\n\n"
                "**Severity:** {{severity}} | **Likelihood:** {{likelihood}}\n\n"
                "{{description}}\n\n"
                "**Mitigation:** {{mitigation}}\n",
            ),
            (
                "test-case",
                "{{heading}} {{title}}\n\n"
                "**Status:** {{status}} | **Version:** {{current_version}}\n\n"
                "{{description}}\n\n"
                "**Test Steps:**\n\n{{test-steps}}\n\n"
                "**Expected Result:** {{expected-result}}\n",
            ),
            (
                "failure-mode",
                "{{heading}} {{title}}\n\n"
                "**Severity:** {{severity}}\n\n"
                "{{description}}\n",
            ),
            (
                "threat",
                "{{heading}} {{title}}\n\n"
                "**Threat Level:** {{threat-level}} | **Attack Vector:** {{attack-vector}}\n\n"
                "**Threat Agent:** {{threat-agent}}\n\n"
                "{{description}}\n",
            ),
        ]
        for type_slug, template_str in doc_templates:
            item_type = self._types[type_slug]
            DocumentTemplate.objects.update_or_create(
                item_type=item_type,
                defaults={"template": template_str, "updated_by": self._author},
            )
            self.stdout.write(f"  Seeded: DocumentTemplate for '{type_slug}'")

    # ------------------------------------------------------------------
    # Command entry point
    # ------------------------------------------------------------------

    AV_VAULT_SLUG = "av-system"
    AVIONICS_VAULT_SLUG = "avionics-fms"

    @transaction.atomic
    def handle(self, *args, **options):
        # Wipe example vaults
        self._wipe_vault(self.AV_VAULT_SLUG)
        self._wipe_vault(self.AVIONICS_VAULT_SLUG)

        # Ensure admin user exists
        admin = User.objects.filter(username="admin").first()
        if not admin:
            admin = User.objects.create_superuser(
                username="admin", email="admin@example.com", password="admin282!",
                is_site_admin=True,
            )

        # Create demo author (shared across vaults)
        User.objects.filter(username="demo").delete()
        self._author = User.objects.create_user(
            username="demo",
            email="demo@example.com",
            password="DEMOdemo123!",
        )
        self.stdout.write("  Created user: admin / admin (site admin)")
        self.stdout.write("  Created user: demo / DEMOdemo123! (vault role: editor)\n")

        # ==============================================================
        # VAULT 1 — AV System
        # ==============================================================
        self.stdout.write(self.style.MIGRATE_HEADING("Setting up AV System vault..."))

        self._vault = Vault.objects.create(
            name="AV System",
            slug=self.AV_VAULT_SLUG,
            description="Autonomous Vehicle System example vault.",
            created_by=admin,
        )
        VaultMembership.objects.create(vault=self._vault, user=admin, role="admin")
        VaultMembership.objects.create(vault=self._vault, user=self._author, role="editor")
        admin.active_vault = self._vault
        admin.save(update_fields=["active_vault"])
        self._author.active_vault = self._vault
        self._author.save(update_fields=["active_vault"])

        self._setup_vault_schema(admin)

        self.stdout.write("Building Autonomous Vehicle document-deliverable example...")
        self._build()
        self.stdout.write(self.style.SUCCESS("  AV System vault complete."))

        # ==============================================================
        # VAULT 2 — Avionics FMS
        # ==============================================================
        self.stdout.write(self.style.MIGRATE_HEADING("\nSetting up Avionics FMS vault..."))

        self._vault = Vault.objects.create(
            name="Avionics FMS",
            slug=self.AVIONICS_VAULT_SLUG,
            description=(
                "Flight Management System development programme example vault, "
                "following DO-178C, ARP4754A, ARP4761, and DO-326A."
            ),
            created_by=admin,
        )
        VaultMembership.objects.create(vault=self._vault, user=admin, role="admin")
        VaultMembership.objects.create(vault=self._vault, user=self._author, role="editor")

        self._setup_vault_schema(admin)

        self.stdout.write("Building Avionics FMS document-deliverable example...")
        self._build_avionics()
        self.stdout.write(self.style.SUCCESS("  Avionics FMS vault complete."))

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        n_items = Item.objects.count()
        n_rels = ItemRelation.objects.count()
        n_matrices = Matrix.objects.count()
        self.stdout.write(f"\n  Items created    : {n_items}")
        self.stdout.write(f"  Relations created: {n_rels}")
        self.stdout.write(f"  Matrices created : {n_matrices}")

        self.stdout.write(self.style.SUCCESS(
            "\nDone. Register any account at /register to review and edit the examples."
        ))
    # ------------------------------------------------------------------
    # AV System example data
    # ------------------------------------------------------------------

    def _build(self):
        # ==============================================================
        # TOP-LEVEL PROGRAMME
        # ==============================================================
        programme = self._item(
            "project",
            "AV-2000 Autonomous Vehicle Project",
            "Top-level project for the AV-2000 autonomous vehicle "
            "development, encompassing all document deliverables.",
            **{"standard-reference": "ISO 26262, ISO 21448 (SOTIF)"},
        )

        # ==============================================================
        # PLANS
        # ==============================================================
        dev_plan = self._item(
            "plan",
            "Development Plan",
            "Defines the overall development lifecycle, milestones, roles, and "
            "processes for the AV-2000 project. Covers hardware, software, "
            "and system integration activities.",
            **{"phase": "Approved",
               "standard-reference": "ISO 26262-2"},
        )
        risk_mgmt_plan = self._item(
            "plan",
            "Risk Management Plan",
            "Describes the risk management process, risk acceptability criteria, "
            "analysis methods (FMEA, FTA), and risk review cadence for the "
            "AV-2000 project per ISO 26262 and SOTIF.",
            **{"phase": "Approved",
               "standard-reference": "ISO 26262-2, ISO 21448 (SOTIF)"},
        )
        verification_plan = self._item(
            "plan",
            "Verification Plan",
            "Defines the verification strategy, test levels, test environments, "
            "and pass/fail criteria for all system requirements.",
            **{"phase": "Approved",
               "standard-reference": "ISO 26262-8"},
        )
        validation_plan = self._item(
            "plan",
            "Validation Plan",
            "Defines the validation approach including real-world driving "
            "scenarios, acceptance criteria, and regulatory submission evidence.",
            **{"phase": "Review",
               "standard-reference": "ISO 21448 (SOTIF)"},
        )

        self._compose(programme, dev_plan,
                       verification_plan, validation_plan)

        # ==============================================================
        # PLAN SECTIONS  (Information items)
        # ==============================================================

        # -- Development Plan sections --
        dev_purpose = self._item(
            "information",
            "Purpose",
            "This document defines the overall development lifecycle, "
            "milestones, roles, and processes for the AV-2000 autonomous "
            "vehicle project. It serves as the primary reference for all "
            "engineering teams involved in design, implementation, and "
            "integration activities.",
        )
        dev_scope = self._item(
            "information",
            "Scope",
            "This plan covers the full vehicle development from concept "
            "through to production release, including hardware design, "
            "embedded software, sensor integration, and system-level "
            "verification. It does not cover manufacturing processes or "
            "post-production servicing.",
        )
        dev_refs = self._item(
            "information",
            "Normative References",
            "ISO 26262:2018 (all parts) — Road vehicles – Functional safety\n"
            "ISO 21448:2022 — Road vehicles – Safety of the intended functionality (SOTIF)\n"
            "ISO/SAE 21434:2021 — Road vehicles – Cybersecurity engineering\n"
            "IEC 61508:2010 — Functional safety of electrical/electronic/programmable electronic safety-related systems",
        )
        dev_lifecycle = self._item(
            "information",
            "Development Lifecycle",
            "The project follows a V-model development lifecycle with iterative "
            "prototyping at each stage. Requirements are captured and baselined "
            "at the left side of the V; verification and validation activities "
            "on the right side confirm that each requirement is satisfied. "
            "Agile sprints are used within each V-model phase for software "
            "development activities.",
        )
        self._compose(dev_plan, dev_purpose, dev_scope, dev_refs, dev_lifecycle)

        # -- Risk Management Plan sections --
        rmp_purpose = self._item(
            "information",
            "Purpose",
            "This plan establishes the risk management process, acceptability "
            "criteria, analysis methods, and review cadence for identifying, "
            "evaluating, and controlling risks throughout the AV-2000 project.",
        )
        rmp_scope = self._item(
            "information",
            "Scope",
            "Covers safety risks (ISO 26262 hazard analysis, FMEA, FTA), "
            "SOTIF-related risks (reasonably foreseeable misuse, performance "
            "limitations), and cybersecurity risks (ISO/SAE 21434 threat "
            "analysis). Financial and schedule risks are managed separately "
            "under the project management plan.",
        )
        rmp_criteria = self._item(
            "information",
            "Risk Acceptability Criteria",
            "Risks are classified using a 5×4 severity–likelihood matrix. "
            "Risks rated Critical or High require documented mitigation before "
            "the design is approved. Medium risks must be reviewed and either "
            "mitigated or accepted with rationale. Low risks are recorded but "
            "do not require active mitigation.",
        )
        self._compose(risk_mgmt_plan, rmp_purpose, rmp_scope, rmp_criteria)

        # -- Verification Plan sections --
        vp_purpose = self._item(
            "information",
            "Purpose",
            "This plan defines the verification strategy, test levels, test "
            "environments, tools, and pass/fail criteria for demonstrating "
            "that all system and subsystem requirements are correctly "
            "implemented.",
        )
        vp_scope = self._item(
            "information",
            "Scope",
            "Covers unit testing, integration testing, system-level testing, "
            "and hardware-in-the-loop (HIL) simulation for all AV-2000 "
            "subsystems. Regression testing and continuous integration "
            "requirements are included. Validation activities (real-world "
            "driving scenarios) are covered separately in the Validation Plan.",
        )
        vp_methods = self._item(
            "information",
            "Verification Methods",
            "Four verification methods are employed per ISO 26262-8:\n"
            "• Test — execution of software or hardware against defined stimuli\n"
            "• Analysis — formal or semi-formal reasoning including code review and static analysis\n"
            "• Inspection — visual or manual examination of work products\n"
            "• Demonstration — functional walk-through in a representative environment",
        )
        self._compose(verification_plan, vp_purpose, vp_scope, vp_methods)

        # -- Validation Plan sections --
        valp_purpose = self._item(
            "information",
            "Purpose",
            "This plan describes the validation approach for confirming that "
            "the AV-2000 system satisfies its intended use and user needs "
            "under real-world operating conditions.",
        )
        valp_scope = self._item(
            "information",
            "Scope",
            "Validation covers closed-course testing, public-road pilot "
            "programmes, and simulation-based scenario testing. It addresses "
            "both nominal driving conditions and edge cases identified through "
            "SOTIF analysis. Regulatory submission evidence requirements are "
            "included.",
        )
        valp_acceptance = self._item(
            "information",
            "Acceptance Criteria",
            "The system must complete a minimum of 100,000 km of autonomous "
            "driving without a safety-critical disengagement. Scenario-based "
            "testing must cover all SOTIF-identified triggering conditions with "
            "a pass rate ≥ 98 %. Human-factors evaluations must demonstrate "
            "safe takeover within 4 seconds for all tested transition scenarios.",
        )
        self._compose(validation_plan, valp_purpose, valp_scope, valp_acceptance)

        # ==============================================================
        # SPECIFICATIONS
        # ==============================================================
        sys_req_spec = self._item(
            "specification",
            "System Requirements Specification",
            "Captures all system-level functional and non-functional requirements "
            "for the AV-2000 autonomous vehicle.",
            **{"baseline": "SRS-BL-3",
               "standard-reference": "ISO 26262-3"},
        )
        perc_spec = self._item(
            "specification",
            "Perception Subsystem Specification",
            "Detailed requirements for the perception subsystem covering camera, "
            "lidar, and sensor-fusion capabilities.",
            **{"baseline": "PERC-BL-2",
               "standard-reference": "ISO 26262-4"},
        )
        motion_spec = self._item(
            "specification",
            "Motion Planning Specification",
            "Requirements governing trajectory computation, obstacle avoidance, "
            "and path re-planning under degraded conditions.",
            **{"baseline": "MP-BL-1",
               "standard-reference": "ISO 26262-4"},
        )
        safety_spec = self._item(
            "specification",
            "Safety Requirements Specification",
            "Functional safety requirements derived from ISO 26262 and SOTIF "
            "analysis, covering emergency braking, fail-safe transitions, "
            "and safety monitoring.",
            **{"baseline": "SAF-BL-2",
               "standard-reference": "ISO 26262-3, ISO 26262-4"},
        )

        self._compose(programme, sys_req_spec, perc_spec, motion_spec, safety_spec)

        # ==============================================================
        # RISK MANAGEMENT FILE
        # ==============================================================
        risk_mgmt_file = self._item(
            "report",
            "Risk Management File",
            "Collects all risk management artefacts: the risk management plan, "
            "FMEA analyses, risk assessment, and risk-benefit analysis for "
            "regulatory submission.",
            **{"report-status": "Draft"},
        )

        # ==============================================================
        # ANALYSES  (FMEA documents)
        # ==============================================================
        perc_fmea = self._item(
            "analysis",
            "Perception Subsystem FMEA",
            "Failure Mode and Effects Analysis for all perception hardware and "
            "software components.",
            **{"method": "FMEA",
               "standard-reference": "IEC 60812"},
        )
        motion_fmea = self._item(
            "analysis",
            "Motion Planning FMEA",
            "Failure Mode and Effects Analysis for the trajectory planner and "
            "obstacle avoidance modules.",
            **{"method": "FMEA",
               "standard-reference": "IEC 60812"},
        )
        safety_fmea = self._item(
            "analysis",
            "Safety System FMEA",
            "System-level FMEA covering emergency braking, sensor-fusion "
            "integrity, and fail-safe transition mechanisms.",
            **{"method": "FMEA",
               "standard-reference": "IEC 60812, ISO 26262-5"},
        )

        # Risk Assessment Report
        risk_assessment = self._item(
            "report",
            "Risk Assessment Report",
            "Consolidated risk evaluation summarising residual risk levels, "
            "risk acceptability decisions, and required mitigations.",
            **{"report-status": "Draft"},
        )

        self._compose(programme, risk_mgmt_file)
        self._compose(risk_mgmt_file, risk_mgmt_plan, perc_fmea,
                       motion_fmea, safety_fmea, risk_assessment)

        # ==============================================================
        # REPORTS  (Verification & Validation)
        # ==============================================================
        ver_report = self._item(
            "report",
            "Verification Report",
            "Records the results of all verification test executions, "
            "including pass/fail status and defect references.",
            **{"report-status": "Draft"},
        )
        val_report = self._item(
            "report",
            "Validation Report",
            "Documents the outcome of validation activities against user needs "
            "and intended-use scenarios.",
            **{"report-status": "Draft"},
        )

        self._compose(programme, ver_report, val_report)

        # ==============================================================
        # SYSTEM-LEVEL REQUIREMENTS  (inside System Requirements Spec)
        # ==============================================================
        req_sys_perf = self._item(
            "requirement",
            "System shall detect and classify objects within 100 ms end-to-end",
            "From raw sensor data acquisition to published object list, the "
            "full pipeline latency must not exceed 100 ms at the 99th percentile.",
            priority="Critical", **{"verification-method": "Test"},
        )
        req_sys_avail = self._item(
            "requirement",
            "System availability shall be ≥ 99.9 % during operation",
            "The autonomous driving function shall maintain operational "
            "availability of at least 99.9 % measured over any continuous "
            "8-hour driving session.",
            priority="High", **{"verification-method": "Analysis"},
        )
        req_sys_safe = self._item(
            "requirement",
            "System shall achieve ASIL-D for safety-critical functions",
            "All functions whose failure could lead to life-threatening injury "
            "shall be designed and verified to ASIL-D per ISO 26262.",
            priority="Critical", **{"verification-method": "Analysis"},
        )

        self._compose(sys_req_spec, req_sys_perf, req_sys_avail, req_sys_safe)

        # ==============================================================
        # PERCEPTION REQUIREMENTS  (inside Perception Spec)
        # ==============================================================
        req_cam = self._item(
            "requirement",
            "Camera resolution shall be ≥ 8 MP per sensor",
            "Each forward-facing camera must provide sufficient resolution for "
            "lane marking and sign detection at speeds up to 130 km/h.",
            priority="High", **{"verification-method": "Test"},
        )
        req_lidar = self._item(
            "requirement",
            "Lidar effective range shall be ≥ 150 m",
            "The lidar system must reliably detect objects at 150 m range "
            "under clear weather conditions.",
            priority="High", **{"verification-method": "Test"},
        )
        req_latency = self._item(
            "requirement",
            "Object detection latency shall be < 50 ms",
            "End-to-end latency from sensor capture to object classification "
            "must not exceed 50 ms at the 99th percentile.",
            priority="Critical", **{"verification-method": "Test"},
        )
        req_weather = self._item(
            "requirement",
            "Perception shall maintain ≥ 90 % accuracy in rain and fog",
            "System shall maintain object detection accuracy ≥ 90 % in rain "
            "up to 50 mm/h and fog with visibility ≥ 50 m.",
            priority="High", **{"verification-method": "Analysis"},
        )
        req_fusion = self._item(
            "requirement",
            "Sensor fusion shall reconcile camera and lidar within 10 ms",
            "The fusion layer must produce a unified object list from camera "
            "and lidar inputs within 10 ms of the later input arriving.",
            priority="High", **{"verification-method": "Test"},
        )

        self._compose(perc_spec, req_cam, req_lidar, req_latency,
                       req_weather, req_fusion)

        # Derive perception reqs from system reqs
        self._derives(req_latency, req_sys_perf)
        self._derives(req_fusion, req_sys_perf)

        # ==============================================================
        # MOTION PLANNING REQUIREMENTS  (inside Motion Planning Spec)
        # ==============================================================
        req_path = self._item(
            "requirement",
            "Path planning shall complete within 100 ms",
            "A collision-free trajectory from current position to 5 m ahead "
            "must be re-computed in ≤ 100 ms at the 99th percentile.",
            priority="Critical", **{"verification-method": "Test"},
        )
        req_clearance = self._item(
            "requirement",
            "Minimum lateral obstacle clearance shall be ≥ 0.5 m",
            "The planned path must maintain at least 0.5 m lateral distance "
            "from all detected obstacles.",
            priority="High", **{"verification-method": "Demonstration"},
        )
        req_gps = self._item(
            "requirement",
            "System shall maintain lane keeping without GPS for ≥ 30 s",
            "Using dead reckoning, the vehicle must remain within lane "
            "boundaries for at least 30 seconds after GPS signal loss.",
            priority="Medium", **{"verification-method": "Test"},
        )

        self._compose(motion_spec, req_path, req_clearance, req_gps)

        # Derive motion reqs from system reqs
        self._derives(req_path, req_sys_perf)

        # ==============================================================
        # SAFETY REQUIREMENTS  (inside Safety Spec)
        # ==============================================================
        req_brake = self._item(
            "requirement",
            "Emergency braking shall initiate within 200 ms of threat detection",
            "From the moment a collision-imminent event is detected, the brake "
            "actuator must receive the full-stop command within 200 ms.",
            priority="Critical", **{"verification-method": "Test"},
        )
        req_safe_state = self._item(
            "requirement",
            "System shall enter minimal risk condition within 3 s on sensor failure",
            "If any safety-critical sensor becomes unavailable, the system must "
            "transition to a controlled stop within 3 seconds.",
            priority="Critical", **{"verification-method": "Demonstration"},
        )
        req_integrity = self._item(
            "requirement",
            "Safety monitor watchdog shall achieve ASIL-D integrity",
            "The safety monitor watchdog shall be designed and verified to "
            "ASIL-D as defined in ISO 26262-5.",
            priority="Critical", **{"verification-method": "Analysis"},
        )
        req_diag = self._item(
            "requirement",
            "Continuous diagnostic coverage shall be ≥ 99 % for safety-critical HW",
            "All safety-critical hardware elements shall have online diagnostic "
            "coverage of at least 99 % per ISO 26262 diagnostic requirements.",
            priority="High", **{"verification-method": "Analysis"},
        )

        self._compose(safety_spec, req_brake, req_safe_state,
                       req_integrity, req_diag)

        # Derive safety reqs from system reqs
        self._derives(req_brake, req_sys_perf)
        self._derives(req_safe_state, req_sys_safe)
        self._derives(req_integrity, req_sys_safe)
        self._derives(req_diag, req_sys_safe)

        # Cross-subsystem derivation
        self._derives(req_brake, req_latency, req_path)
        self._derives(req_safe_state, req_gps, req_integrity)

        # ==============================================================
        # REQUIREMENT DECOMPOSITION
        # Demonstrates how a high-level requirement is decomposed into
        # lower-level sub-requirements that together fulfil it.
        # ==============================================================

        # Decompose "System shall detect and classify objects within 100 ms"
        # into its time-budget sub-requirements
        req_acquire = self._item(
            "requirement",
            "Sensor data acquisition shall complete within 15 ms",
            "Raw data from all active sensors (cameras, lidar, radar) must "
            "be captured, timestamped, and available to the processing "
            "pipeline within 15 ms of the sensor trigger.",
            priority="High", **{"verification-method": "Test"},
        )
        req_preprocess = self._item(
            "requirement",
            "Sensor preprocessing shall complete within 20 ms",
            "Image debayering, lidar point-cloud assembly, and radar FFT "
            "processing shall each complete within 20 ms of data arrival.",
            priority="High", **{"verification-method": "Test"},
        )
        req_detect = self._item(
            "requirement",
            "Object detection inference shall complete within 25 ms",
            "The neural-network inference pipeline shall produce bounding "
            "boxes and class labels within 25 ms per frame on the target "
            "compute platform.",
            priority="Critical", **{"verification-method": "Test"},
        )
        req_track = self._item(
            "requirement",
            "Object tracking and association shall complete within 15 ms",
            "Multi-object tracking shall associate detections across frames "
            "and update track state within 15 ms.",
            priority="High", **{"verification-method": "Test"},
        )
        req_publish = self._item(
            "requirement",
            "Object list publication shall complete within 5 ms",
            "The final classified object list shall be serialised and "
            "published to the vehicle bus within 5 ms of track update.",
            priority="Medium", **{"verification-method": "Test"},
        )

        self._refines(req_sys_perf, req_acquire, req_preprocess,
                         req_detect, req_track, req_publish)

        # Decompose "System availability ≥ 99.9 %" into constituent
        # availability sub-requirements per subsystem
        req_perc_avail = self._item(
            "requirement",
            "Perception subsystem availability shall be ≥ 99.95 %",
            "The perception pipeline shall maintain operational availability "
            "of at least 99.95 % to meet the overall system budget, "
            "accounting for sensor redundancy failover time.",
            priority="High", **{"verification-method": "Analysis"},
        )
        req_plan_avail = self._item(
            "requirement",
            "Motion planning availability shall be ≥ 99.95 %",
            "The trajectory planner shall remain available at least 99.95 % "
            "of the time, with a hot-standby failover completing in < 50 ms.",
            priority="High", **{"verification-method": "Analysis"},
        )
        req_actuation_avail = self._item(
            "requirement",
            "Actuation subsystem availability shall be ≥ 99.99 %",
            "Steering, braking, and throttle actuators shall maintain "
            "operational availability of at least 99.99 % through "
            "redundant hardware channels.",
            priority="Critical", **{"verification-method": "Analysis"},
        )

        self._refines(req_sys_avail, req_perc_avail, req_plan_avail,
                         req_actuation_avail)

        # ==============================================================
        # PERCEPTION FMEA CONTENTS
        # ==============================================================
        fm_cam = self._item(
            "failure-mode",
            "Camera sensor total loss of output",
            "Complete loss of video output from one or more forward-facing "
            "cameras, resulting in a blind zone.",
            severity="High",
        )
        fm_cam_degrad = self._item(
            "failure-mode",
            "Camera image degradation",
            "Partial loss of image quality (blur, noise, saturation) reducing "
            "object detection confidence below acceptable thresholds.",
            severity="Medium",
        )
        fm_lidar = self._item(
            "failure-mode",
            "Lidar range degradation below 150 m",
            "Effective detection range drops below the 150 m threshold due to "
            "hardware or environmental factors.",
            severity="High",
        )
        fm_fusion_mismatch = self._item(
            "failure-mode",
            "Sensor fusion object mismatch",
            "Camera and lidar object lists diverge, causing the fusion layer "
            "to produce phantom or missing objects.",
            severity="High",
        )

        self._compose(perc_fmea, fm_cam, fm_cam_degrad, fm_lidar,
                       fm_fusion_mismatch)

        # Failure causes for perception
        fc_lens = self._item(
            "failure-cause",
            "Lens contamination (mud, ice, water droplets)",
            "Foreign material on the lens blocks or scatters incoming light.",
            category="Environmental",
        )
        fc_power = self._item(
            "failure-cause",
            "Camera power supply failure",
            "Loss of regulated voltage to the camera module due to fuse blow "
            "or wiring fault.",
            category="Design",
        )
        fc_vibration = self._item(
            "failure-cause",
            "Mechanical vibration causing lidar misalignment",
            "Road-induced vibration shifts the lidar optical assembly outside "
            "its calibration envelope.",
            category="Manufacturing",
        )
        fc_temp = self._item(
            "failure-cause",
            "Thermal overload of image sensor",
            "Prolonged operation above 60 °C causes the CMOS sensor to "
            "introduce excessive thermal noise.",
            category="Environmental",
        )
        fc_sync = self._item(
            "failure-cause",
            "Timestamp synchronisation drift between sensors",
            "Clock drift exceeding 5 ms between camera and lidar causes "
            "spatial mis-registration in the fusion layer.",
            category="Software",
        )

        self._compose(perc_fmea, fc_lens, fc_power, fc_vibration,
                       fc_temp, fc_sync)

        # Cause → mode
        self._causes(fc_lens, fm_cam, fm_cam_degrad)
        self._causes(fc_power, fm_cam)
        self._causes(fc_vibration, fm_lidar)
        self._causes(fc_temp, fm_cam_degrad)
        self._causes(fc_sync, fm_fusion_mismatch)

        # Mode → requirement (failure mode challenges requirement)
        self._mitigates(fm_cam, req_latency, req_weather)
        self._mitigates(fm_cam_degrad, req_weather)
        self._mitigates(fm_lidar, req_lidar)
        self._mitigates(fm_fusion_mismatch, req_fusion, req_safe_state)

        # ==============================================================
        # MOTION PLANNING FMEA CONTENTS
        # ==============================================================
        fm_planner = self._item(
            "failure-mode",
            "Path planner compute timeout",
            "Trajectory computation does not complete within 100 ms, causing "
            "the vehicle to continue on the last known trajectory.",
            severity="Critical",
        )
        fm_local_min = self._item(
            "failure-mode",
            "Path planner trapped in local minimum",
            "The optimisation algorithm converges to a sub-optimal trajectory "
            "that violates the clearance requirement.",
            severity="Medium",
        )

        self._compose(motion_fmea, fm_planner, fm_local_min)

        fc_deadlock = self._item(
            "failure-cause",
            "Software deadlock in planning thread",
            "A race condition causes the planning thread to block indefinitely "
            "on a shared resource.",
            category="Software",
        )
        fc_cpu = self._item(
            "failure-cause",
            "CPU thermal throttling under sustained load",
            "High ambient temperature combined with sustained planning load "
            "triggers CPU frequency reduction.",
            category="Environmental",
        )

        self._compose(motion_fmea, fc_deadlock, fc_cpu)

        self._causes(fc_deadlock, fm_planner)
        self._causes(fc_cpu, fm_planner)
        self._mitigates(fm_planner, req_path)
        self._mitigates(fm_local_min, req_clearance)

        # ==============================================================
        # SAFETY SYSTEM FMEA CONTENTS
        # ==============================================================
        fm_brake = self._item(
            "failure-mode",
            "Brake actuator no response",
            "The brake actuator does not respond to the emergency stop "
            "command within the required time window.",
            severity="Critical",
        )
        fm_watchdog = self._item(
            "failure-mode",
            "Safety watchdog fails to trigger",
            "The hardware watchdog timer does not fire despite a detected "
            "safety-critical fault, allowing continued operation.",
            severity="Critical",
        )
        fm_comm = self._item(
            "failure-mode",
            "Safety bus communication loss",
            "Loss of communication on the safety-rated CAN bus between the "
            "safety monitor and actuator controllers.",
            severity="High",
        )

        self._compose(safety_fmea, fm_brake, fm_watchdog, fm_comm)

        fc_hydraulic = self._item(
            "failure-cause",
            "Hydraulic pressure loss in brake circuit",
            "A leak in the brake hydraulic circuit reduces available braking "
            "force below the threshold for emergency stop.",
            category="Design",
        )
        fc_emi = self._item(
            "failure-cause",
            "Electromagnetic interference on safety CAN bus",
            "High-intensity EMI disrupts CAN frames between the safety "
            "monitor and the brake actuator ECU.",
            category="Environmental",
        )
        fc_firmware = self._item(
            "failure-cause",
            "Watchdog timer firmware register misconfiguration",
            "Incorrect register initialisation during boot causes the "
            "watchdog timeout period to exceed the safety window.",
            category="Software",
        )

        self._compose(safety_fmea, fc_hydraulic, fc_emi, fc_firmware)

        self._causes(fc_hydraulic, fm_brake)
        self._causes(fc_emi, fm_comm, fm_brake)
        self._causes(fc_firmware, fm_watchdog)
        self._mitigates(fm_brake, req_brake)
        self._mitigates(fm_watchdog, req_integrity, req_safe_state)
        self._mitigates(fm_comm, req_safe_state)

        # ==============================================================
        # RISK ASSESSMENT CONTENTS  (Risk items inside Risk Assessment Report)
        # ==============================================================
        risk_weather = self._item(
            "risk",
            "Adverse weather degrades perception accuracy",
            "Heavy rain, snow, or fog may reduce camera and lidar "
            "effectiveness below minimum required accuracy, increasing "
            "collision risk.",
            severity="High", likelihood="Likely",
            mitigation=(
                "Implement sensor fusion redundancy. Set conservative speed "
                "limits when weather confidence drops below threshold. "
                "Require successful adverse-weather test suite."
            ),
        )
        risk_cyber = self._item(
            "risk",
            "Cybersecurity attack on vehicle control bus",
            "An adversary gaining access to the internal vehicle network "
            "could inject malicious commands to override driving functions.",
            severity="Critical", likelihood="Possible",
            mitigation=(
                "Implement gateway firewall with message authentication. "
                "Conduct annual penetration testing. Apply OTA security patches."
            ),
        )
        risk_gps = self._item(
            "risk",
            "GPS signal loss in urban canyon",
            "Tall buildings cause multi-path errors or complete GPS outages, "
            "compromising the position solution used by the path planner.",
            severity="Medium", likelihood="Likely",
            mitigation=(
                "Fuse GPS with IMU and HD-map localisation. Validate "
                "dead-reckoning on standardised urban test routes."
            ),
        )
        risk_supply = self._item(
            "risk",
            "Critical component supply chain disruption",
            "Single-source lidar or compute module becomes unavailable, "
            "delaying production and verification milestones.",
            severity="High", likelihood="Possible",
            mitigation=(
                "Qualify secondary suppliers. Maintain 6-month safety stock "
                "of critical components. Include supply risk in project reviews."
            ),
        )

        self._compose(risk_assessment, risk_weather, risk_cyber,
                       risk_gps, risk_supply)

        # Risk → requirement (risk challenges requirement)
        self._mitigates(risk_weather, req_cam, req_lidar, req_weather)
        self._mitigates(risk_cyber, req_safe_state, req_integrity)
        self._mitigates(risk_gps, req_gps)

        # ==============================================================
        # CYBERSECURITY ASSESSMENT
        # ==============================================================

        # -- Documents --
        cyber_spec = self._item(
            "specification",
            "Cybersecurity Requirements Specification",
            "Security requirements for the AV-2000 derived from the TARA, "
            "covering network security, authentication, secure boot, and "
            "intrusion detection.",
            **{"baseline": "SEC-BL-1",
               "standard-reference": "ISO/SAE 21434"},
        )
        tara = self._item(
            "analysis",
            "Threat Analysis and Risk Assessment (TARA)",
            "Systematic identification and evaluation of cybersecurity threats, "
            "vulnerabilities, and attack paths for the AV-2000 vehicle platform "
            "per ISO/SAE 21434.",
            **{"method": "Other",
               "standard-reference": "ISO/SAE 21434"},
        )
        pentest_report = self._item(
            "report",
            "Penetration Test Report",
            "Results of the annual penetration test covering external network "
            "interfaces, OTA update mechanism, and in-vehicle bus access.",
            **{"report-status": "Draft"},
        )

        self._compose(programme, cyber_spec, tara, pentest_report)

        # -- Security requirements (inside Cybersecurity Requirements Spec) --
        req_sec_auth = self._item(
            "requirement",
            "All external interfaces shall require mutual authentication",
            "Every external communication channel (V2X, telematics, OTA, "
            "diagnostic) must implement mutual TLS or equivalent mutual "
            "authentication before data exchange.",
            priority="Critical", **{"verification-method": "Test"},
        )
        req_sec_bus = self._item(
            "requirement",
            "In-vehicle bus messages shall be authenticated with MACs",
            "All safety-critical CAN/Ethernet messages shall carry a message "
            "authentication code (MAC) verified by the receiver within 5 ms.",
            priority="Critical", **{"verification-method": "Test"},
        )
        req_sec_boot = self._item(
            "requirement",
            "All ECUs shall implement verified secure boot",
            "Each ECU shall verify the cryptographic signature of its firmware "
            "image before execution. Unsigned or tampered images shall be "
            "rejected and the ECU shall enter a safe state.",
            priority="High", **{"verification-method": "Demonstration"},
        )
        req_sec_ids = self._item(
            "requirement",
            "System shall detect and log anomalous network traffic within 500 ms",
            "An intrusion detection system shall monitor in-vehicle network "
            "traffic and flag anomalous patterns within 500 ms, logging the "
            "event for forensic analysis.",
            priority="High", **{"verification-method": "Test"},
        )
        req_sec_ota = self._item(
            "requirement",
            "OTA updates shall be signed and verified before installation",
            "All over-the-air software updates shall be cryptographically "
            "signed. The update agent shall verify the signature and rollback "
            "on verification failure.",
            priority="Critical", **{"verification-method": "Test"},
        )
        req_sec_keys = self._item(
            "requirement",
            "Cryptographic keys shall be stored in a hardware security module",
            "All long-term cryptographic keys used for authentication, secure "
            "boot, and OTA signing shall reside in an HSM with tamper "
            "resistance meeting FIPS 140-2 Level 2 or above.",
            priority="High", **{"verification-method": "Inspection"},
        )

        self._compose(cyber_spec, req_sec_auth, req_sec_bus, req_sec_boot,
                       req_sec_ids, req_sec_ota, req_sec_keys)

        # Derive security reqs from system safety reqs
        self._derives(req_sec_bus, req_sys_safe)
        self._derives(req_sec_boot, req_sys_safe)
        self._derives(req_sec_auth, req_sys_safe)

        # -- Threats (inside TARA) --
        thr_can = self._item(
            "threat",
            "CAN bus message injection via OBD-II port",
            "An attacker with physical access to the OBD-II port injects "
            "forged CAN frames to manipulate steering, braking, or throttle "
            "commands.",
            **{"threat-level": "Critical", "attack-vector": "Physical",
               "threat-agent": "Skilled attacker with physical access"},
        )
        thr_ota = self._item(
            "threat",
            "Malicious OTA firmware update",
            "An attacker compromises the OTA update server or performs a "
            "man-in-the-middle attack to deliver tampered firmware to "
            "vehicle ECUs.",
            **{"threat-level": "Critical", "attack-vector": "Network",
               "threat-agent": "Remote attacker / nation-state actor"},
        )
        thr_v2x = self._item(
            "threat",
            "V2X message spoofing",
            "An attacker broadcasts forged V2X messages (e.g. fake emergency "
            "vehicle warnings or phantom obstacles) to trigger unintended "
            "braking or lane changes.",
            **{"threat-level": "High", "attack-vector": "Adjacent",
               "threat-agent": "Proximate attacker with SDR equipment"},
        )
        thr_telematics = self._item(
            "threat",
            "Remote exploitation of telematics control unit",
            "An attacker exploits a vulnerability in the telematics unit's "
            "cellular stack to gain remote code execution and pivot to the "
            "in-vehicle network.",
            **{"threat-level": "Critical", "attack-vector": "Network",
               "threat-agent": "Remote attacker"},
        )
        thr_replay = self._item(
            "threat",
            "Key fob relay / replay attack",
            "An attacker captures and replays key fob RF signals to unlock "
            "the vehicle and potentially access diagnostic interfaces.",
            **{"threat-level": "Medium", "attack-vector": "Adjacent",
               "threat-agent": "Opportunistic thief with relay equipment"},
        )

        self._compose(tara, thr_can, thr_ota, thr_v2x, thr_telematics,
                       thr_replay)

        # -- Vulnerabilities (inside TARA) --
        vuln_can_noauth = self._item(
            "vulnerability",
            "CAN bus lacks message authentication",
            "The legacy CAN bus protocol does not provide native message "
            "authentication, allowing any node to spoof any message ID.",
            severity="Critical",
            **{"attack-feasibility": "High",
               "component": "In-vehicle CAN network"},
        )
        vuln_ota_verify = self._item(
            "vulnerability",
            "Insufficient OTA signature verification",
            "The current OTA agent only checks the update package hash but "
            "does not verify a cryptographic signature against a trusted root.",
            severity="Critical",
            **{"attack-feasibility": "Medium",
               "component": "OTA update agent"},
        )
        vuln_tcu_stack = self._item(
            "vulnerability",
            "Unpatched buffer overflow in telematics cellular stack",
            "The telematics control unit runs a cellular modem firmware with "
            "a known heap overflow vulnerability (CVE-2024-XXXX) that allows "
            "remote code execution.",
            severity="Critical",
            **{"attack-feasibility": "High",
               "component": "Telematics Control Unit"},
        )
        vuln_v2x_nocheck = self._item(
            "vulnerability",
            "V2X message plausibility checks missing",
            "Received V2X messages are accepted without plausibility or "
            "consistency verification, enabling phantom object injection.",
            severity="High",
            **{"attack-feasibility": "Medium",
               "component": "V2X communication module"},
        )
        vuln_debug_port = self._item(
            "vulnerability",
            "Debug port accessible without authentication",
            "JTAG/SWD debug ports on safety-critical ECUs are not disabled "
            "or protected in production builds, allowing firmware extraction.",
            severity="High",
            **{"attack-feasibility": "Medium",
               "component": "ECU hardware"},
        )

        self._compose(tara, vuln_can_noauth, vuln_ota_verify, vuln_tcu_stack,
                       vuln_v2x_nocheck, vuln_debug_port)

        # Threat → Vulnerability (exploits)
        self._exploits(thr_can, vuln_can_noauth)
        self._exploits(thr_ota, vuln_ota_verify)
        self._exploits(thr_v2x, vuln_v2x_nocheck)
        self._exploits(thr_telematics, vuln_tcu_stack)
        self._exploits(thr_replay, vuln_debug_port)

        # -- Mitigations (inside TARA) --
        mit_can_mac = self._item(
            "mitigation",
            "Implement SecOC message authentication on CAN bus",
            "Deploy AUTOSAR SecOC with AES-128-CMAC on all safety-critical "
            "CAN messages. Key management via HSM.",
            **{"control-type": "Preventive",
               "implementation-status": "In Progress"},
        )
        mit_ota_sign = self._item(
            "mitigation",
            "Cryptographic OTA update signing and verification",
            "Sign all OTA packages with Ed25519 using an offline signing key. "
            "The on-vehicle agent verifies against a pinned public key stored "
            "in the HSM before applying any update.",
            **{"control-type": "Preventive",
               "implementation-status": "Implemented"},
        )
        mit_tcu_patch = self._item(
            "mitigation",
            "Patch telematics cellular stack and add network segmentation",
            "Apply vendor patch for CVE-2024-XXXX. Isolate the telematics "
            "unit from the safety-critical domain via an Ethernet gateway "
            "with strict allowlist firewall rules.",
            **{"control-type": "Corrective",
               "implementation-status": "In Progress"},
        )
        mit_v2x_plaus = self._item(
            "mitigation",
            "V2X message plausibility and consistency validation",
            "Implement multi-source plausibility checks on received V2X "
            "messages: cross-reference with own sensor data, check spatial/"
            "temporal consistency, and rate-limit message acceptance.",
            **{"control-type": "Detective",
               "implementation-status": "Planned"},
        )
        mit_ids = self._item(
            "mitigation",
            "Deploy in-vehicle intrusion detection system",
            "Install a CAN/Ethernet IDS that monitors traffic patterns, "
            "detects anomalies using a trained baseline model, and logs "
            "alerts to the security event store.",
            **{"control-type": "Detective",
               "implementation-status": "In Progress"},
        )
        mit_secure_boot = self._item(
            "mitigation",
            "Enable hardware-rooted secure boot on all ECUs",
            "Configure each ECU's boot ROM to verify a chain of trust from "
            "the hardware root of trust through bootloader to application "
            "firmware. Disable debug ports in production fuses.",
            **{"control-type": "Preventive",
               "implementation-status": "Implemented"},
        )

        self._compose(tara, mit_can_mac, mit_ota_sign, mit_tcu_patch,
                       mit_v2x_plaus, mit_ids, mit_secure_boot)

        # Mitigation → Vulnerability (mitigates)
        self._mitigates(mit_can_mac, vuln_can_noauth)
        self._mitigates(mit_ota_sign, vuln_ota_verify)
        self._mitigates(mit_tcu_patch, vuln_tcu_stack)
        self._mitigates(mit_v2x_plaus, vuln_v2x_nocheck)
        self._mitigates(mit_ids, vuln_can_noauth, vuln_tcu_stack)
        self._mitigates(mit_secure_boot, vuln_debug_port, vuln_ota_verify)

        # Mitigation → Requirement (mitigates / satisfies)
        self._mitigates(mit_can_mac, req_sec_bus)
        self._mitigates(mit_ota_sign, req_sec_ota)
        self._mitigates(mit_ids, req_sec_ids)
        self._mitigates(mit_secure_boot, req_sec_boot, req_sec_keys)
        self._mitigates(mit_v2x_plaus, req_sec_auth)

        # Threat → Requirement (threatens)
        self._mitigates(thr_can, req_sec_bus, req_safe_state)
        self._mitigates(thr_ota, req_sec_ota, req_sec_boot)
        self._mitigates(thr_telematics, req_sec_ids, req_safe_state)
        self._mitigates(thr_v2x, req_sec_auth)

        # -- Security risks (inside Risk Assessment Report, alongside safety risks) --
        risk_cyber_intrusion = self._item(
            "risk",
            "Remote intrusion via telematics unit compromises vehicle control",
            "Exploitation of the telematics cellular stack allows an attacker "
            "to pivot to the safety-critical domain and issue unauthorised "
            "driving commands.",
            severity="Critical", likelihood="Possible",
            mitigation=(
                "Patch telematics firmware, enforce network segmentation via "
                "gateway firewall, deploy IDS, conduct annual penetration tests."
            ),
        )
        risk_ota_tampering = self._item(
            "risk",
            "Tampered OTA update installs malicious firmware",
            "An attacker intercepts or replaces an OTA package with malicious "
            "firmware, potentially disabling safety functions.",
            severity="Critical", likelihood="Unlikely",
            mitigation=(
                "Cryptographic signing with HSM-stored keys, signature "
                "verification before install, secure rollback mechanism."
            ),
        )
        risk_v2x_spoof = self._item(
            "risk",
            "Spoofed V2X messages cause unintended braking",
            "Forged V2X emergency vehicle or hazard warnings trigger "
            "unnecessary hard braking on a motorway, creating a rear-end "
            "collision hazard.",
            severity="High", likelihood="Possible",
            mitigation=(
                "Plausibility checks against own sensor data, rate limiting, "
                "V2X PKI certificate validation."
            ),
        )

        self._compose(risk_assessment, risk_cyber_intrusion,
                       risk_ota_tampering, risk_v2x_spoof)

        self._mitigates(risk_cyber_intrusion, req_sec_ids, req_safe_state)
        self._mitigates(risk_ota_tampering, req_sec_ota, req_sec_boot)
        self._mitigates(risk_v2x_spoof, req_sec_auth)

        # ==============================================================
        # VERIFICATION TEST CASES  (inside Verification Plan)
        # ==============================================================

        # -- Perception verification --
        tc_cam = self._item(
            "test-case",
            "VER-P-001: Camera resolution bench test",
            "Verify each installed camera meets the 8 MP resolution requirement.",
            **{
                "test-steps": (
                    "1. Mount camera on bench fixture.\n"
                    "2. Capture ISO 12233 chart at 5 m.\n"
                    "3. Analyse with MTF tool.\n"
                    "4. Record measured resolution."
                ),
                "expected-result": "Measured resolution ≥ 8 MP for all cameras.",
            },
        )
        tc_lidar = self._item(
            "test-case",
            "VER-P-002: Lidar 150 m range test",
            "Verify lidar detects a retroreflective target at 150 m.",
            **{
                "test-steps": (
                    "1. Position calibrated target at 150 m.\n"
                    "2. Capture for 60 s.\n"
                    "3. Analyse point cloud for target returns."
                ),
                "expected-result": "Target detected in ≥ 99 % of frames.",
            },
        )
        tc_latency = self._item(
            "test-case",
            "VER-P-003: Object detection end-to-end latency",
            "Measure latency from raw sensor frame to published object list.",
            **{
                "test-steps": (
                    "1. Inject timestamped synthetic frames at 30 Hz.\n"
                    "2. Record detection output timestamps.\n"
                    "3. Compute per-frame latency over 10 000 frames.\n"
                    "4. Calculate 99th-percentile latency."
                ),
                "expected-result": "p99 latency < 50 ms.",
            },
        )
        tc_weather = self._item(
            "test-case",
            "VER-P-004: Adverse weather perception accuracy",
            "Evaluate object detection under simulated rain.",
            **{
                "test-steps": (
                    "1. Rain simulation chamber at 50 mm/h.\n"
                    "2. Replay scenario with 30 annotated objects.\n"
                    "3. Compute detection accuracy."
                ),
                "expected-result": "Detection accuracy ≥ 90 %.",
            },
        )
        tc_fusion = self._item(
            "test-case",
            "VER-P-005: Sensor fusion latency test",
            "Verify the fusion layer produces a unified object list within "
            "10 ms of the later input arriving.",
            **{
                "test-steps": (
                    "1. Inject camera and lidar frames with known timestamps.\n"
                    "2. Record fusion output timestamp.\n"
                    "3. Compute delta over 5 000 frame pairs."
                ),
                "expected-result": "Fusion latency ≤ 10 ms at p99.",
            },
        )

        self._compose(verification_plan, tc_cam, tc_lidar, tc_latency,
                       tc_weather, tc_fusion)

        # -- Motion planning verification --
        tc_path = self._item(
            "test-case",
            "VER-M-001: Path planning latency under complex scenarios",
            "Measure worst-case trajectory re-computation time.",
            **{
                "test-steps": (
                    "1. Replay 5 dense urban scenarios.\n"
                    "2. Instrument planner with timestamps.\n"
                    "3. Collect latency for 50 000 cycles.\n"
                    "4. Compute p99."
                ),
                "expected-result": "p99 planning latency ≤ 100 ms.",
            },
        )
        tc_clearance = self._item(
            "test-case",
            "VER-M-002: Obstacle clearance closed-track test",
            "Verify minimum lateral clearance during avoidance manoeuvre.",
            **{
                "test-steps": (
                    "1. Place cone on closed track.\n"
                    "2. Perform 10 avoidance runs at 30 km/h.\n"
                    "3. Measure closest distance via RTK GPS."
                ),
                "expected-result": "Minimum clearance ≥ 0.5 m in all runs.",
            },
        )
        tc_gps = self._item(
            "test-case",
            "VER-M-003: GPS loss dead-reckoning test",
            "Verify vehicle remains in lane for 30 s after GPS cut.",
            **{
                "test-steps": (
                    "1. Enable GPS jamming via HIL rig.\n"
                    "2. Drive 1 km highway section.\n"
                    "3. Monitor lane position via independent vision."
                ),
                "expected-result": "Vehicle stays within lane for ≥ 30 s.",
            },
        )

        self._compose(verification_plan, tc_path, tc_clearance, tc_gps)

        # -- Safety verification --
        tc_brake = self._item(
            "test-case",
            "VER-S-001: Emergency braking response time",
            "Measure time from threat detection to brake command on closed track.",
            **{
                "test-steps": (
                    "1. Deploy pop-up target at 40 m, approach at 50 km/h.\n"
                    "2. Log detection and brake command timestamps.\n"
                    "3. Repeat 20 times."
                ),
                "expected-result": "Max response time < 200 ms.",
            },
        )
        tc_safe_state = self._item(
            "test-case",
            "VER-S-002: Safe-state transition on sensor failure",
            "Inject sensor failure and verify controlled stop.",
            **{
                "test-steps": (
                    "1. At 30 km/h, cut lidar power remotely.\n"
                    "2. Measure time to vehicle standstill.\n"
                    "3. Verify vehicle stays in lane."
                ),
                "expected-result": "Controlled stop within 3 s; vehicle in lane.",
            },
        )
        tc_diag = self._item(
            "test-case",
            "VER-S-003: Diagnostic coverage analysis review",
            "Review the diagnostic coverage calculation for all safety-critical "
            "hardware elements.",
            **{
                "test-steps": (
                    "1. Collect FMEDA results for each safety element.\n"
                    "2. Verify DC calculation method per ISO 26262-5.\n"
                    "3. Confirm DC ≥ 99 % for each element."
                ),
                "expected-result": "All safety-critical HW elements DC ≥ 99 %.",
            },
        )

        self._compose(verification_plan, tc_brake, tc_safe_state, tc_diag)

        # -- Security verification --
        tc_sec_auth = self._item(
            "test-case",
            "VER-SEC-001: External interface mutual authentication",
            "Verify that all external interfaces enforce mutual authentication.",
            **{
                "test-steps": (
                    "1. Attempt connection to telematics, V2X, OTA, and "
                    "diagnostic interfaces without valid credentials.\n"
                    "2. Verify connection is rejected in each case.\n"
                    "3. Connect with valid mutual TLS and confirm success."
                ),
                "expected-result": "All unauthenticated connections rejected.",
            },
        )
        tc_sec_bus = self._item(
            "test-case",
            "VER-SEC-002: CAN bus message authentication",
            "Verify that safety-critical CAN messages carry valid MACs.",
            **{
                "test-steps": (
                    "1. Inject CAN frame with correct ID but no MAC.\n"
                    "2. Inject CAN frame with incorrect MAC.\n"
                    "3. Inject CAN frame with valid MAC.\n"
                    "4. Verify only the valid-MAC frame is accepted."
                ),
                "expected-result": "Frames without valid MAC are dropped.",
            },
        )
        tc_sec_boot = self._item(
            "test-case",
            "VER-SEC-003: Secure boot verification",
            "Verify that ECUs reject unsigned or tampered firmware.",
            **{
                "test-steps": (
                    "1. Flash an ECU with an unsigned firmware image.\n"
                    "2. Observe boot sequence — ECU must not run application.\n"
                    "3. Flash with correctly signed image and confirm normal boot."
                ),
                "expected-result": "Unsigned image rejected; signed image boots.",
            },
        )
        tc_sec_ids = self._item(
            "test-case",
            "VER-SEC-004: Intrusion detection response time",
            "Verify the IDS detects anomalous traffic within 500 ms.",
            **{
                "test-steps": (
                    "1. Inject known anomalous CAN traffic pattern.\n"
                    "2. Measure time from injection to IDS alert.\n"
                    "3. Repeat 50 times and compute p99."
                ),
                "expected-result": "p99 detection latency < 500 ms.",
            },
        )
        tc_sec_ota = self._item(
            "test-case",
            "VER-SEC-005: OTA update signature verification",
            "Verify the OTA agent rejects tampered update packages.",
            **{
                "test-steps": (
                    "1. Deliver an OTA package with modified payload.\n"
                    "2. Verify the agent rejects and logs the failure.\n"
                    "3. Deliver a correctly signed package and confirm install."
                ),
                "expected-result": "Tampered package rejected; valid package installed.",
            },
        )
        tc_sec_pentest = self._item(
            "test-case",
            "VER-SEC-006: Penetration test — external attack surface",
            "Execute a full penetration test against all externally reachable "
            "interfaces.",
            **{
                "test-steps": (
                    "1. Enumerate external attack surface (telematics, V2X, BT, Wi-Fi).\n"
                    "2. Execute automated vulnerability scan.\n"
                    "3. Perform manual exploitation attempts on findings.\n"
                    "4. Document all findings with CVSS scores."
                ),
                "expected-result": "No critical or high findings; all medium "
                "findings have documented mitigations.",
            },
        )

        self._compose(verification_plan, tc_sec_auth, tc_sec_bus,
                       tc_sec_boot, tc_sec_ids, tc_sec_ota, tc_sec_pentest)

        # ==============================================================
        # VALIDATION TEST CASES  (inside Validation Plan)
        # ==============================================================
        tc_val_urban = self._item(
            "test-case",
            "VAL-001: Urban driving scenario acceptance",
            "Execute a standardised 50 km urban driving route covering "
            "intersections, pedestrians, and construction zones.",
            **{
                "test-steps": (
                    "1. Load pre-defined urban route on test vehicle.\n"
                    "2. Execute route with safety driver present.\n"
                    "3. Record all interventions and near-misses.\n"
                    "4. Evaluate against acceptance criteria."
                ),
                "expected-result": "Zero safety-critical interventions; "
                "≤ 2 comfort interventions per 50 km.",
            },
        )
        tc_val_highway = self._item(
            "test-case",
            "VAL-002: Highway driving endurance",
            "Complete a 500 km highway endurance run including lane changes, "
            "overtaking, and merging manoeuvres.",
            **{
                "test-steps": (
                    "1. Execute 500 km highway route.\n"
                    "2. Log system health and intervention events.\n"
                    "3. Analyse post-drive for anomalies."
                ),
                "expected-result": "No system faults; zero safety interventions.",
            },
        )
        tc_val_weather = self._item(
            "test-case",
            "VAL-003: Adverse weather acceptance drive",
            "Execute a 20 km route in rain (≥ 20 mm/h) to validate "
            "real-world perception and planning performance.",
            **{
                "test-steps": (
                    "1. Wait for suitable rain conditions (≥ 20 mm/h).\n"
                    "2. Execute pre-defined route.\n"
                    "3. Record perception confidence and interventions."
                ),
                "expected-result": "System maintains autonomous operation; "
                "perception confidence ≥ 85 %.",
            },
        )

        self._compose(validation_plan, tc_val_urban, tc_val_highway,
                       tc_val_weather)

        # ==============================================================
        # VERIFICATION RELATIONS  (test case verifies requirement)
        # ==============================================================

        # Perception tests → requirements
        self._verifies(tc_cam, req_cam)
        self._verifies(tc_lidar, req_lidar)
        self._verifies(tc_latency, req_latency)
        self._verifies(tc_weather, req_weather)
        self._verifies(tc_fusion, req_fusion)

        # Motion tests → requirements
        self._verifies(tc_path, req_path)
        self._verifies(tc_clearance, req_clearance)
        self._verifies(tc_gps, req_gps)

        # Safety tests → requirements
        self._verifies(tc_brake, req_brake)
        self._verifies(tc_safe_state, req_safe_state)
        self._verifies(tc_diag, req_diag)

        # Validation tests → system requirements
        self._verifies(tc_val_urban, req_sys_perf, req_sys_safe)
        self._verifies(tc_val_highway, req_sys_avail)
        self._verifies(tc_val_weather, req_weather, req_sys_perf)

        # Security tests → security requirements
        self._verifies(tc_sec_auth, req_sec_auth)
        self._verifies(tc_sec_bus, req_sec_bus)
        self._verifies(tc_sec_boot, req_sec_boot, req_sec_keys)
        self._verifies(tc_sec_ids, req_sec_ids)
        self._verifies(tc_sec_ota, req_sec_ota)
        self._verifies(tc_sec_pentest, req_sec_auth, req_sec_bus, req_sec_ids)

        # ==============================================================
        # MATRICES  (traceability tables)
        # ==============================================================

        # 1. System RTM: Requirements → Verifying Test Cases
        self._matrix(
            name="System Requirements Traceability Matrix",
            description=(
                "Traces every requirement to the verification and validation "
                "test cases that cover it."
            ),
            columns=[
                {
                    "label": "Requirement",
                    "seed_item_type_slug": "requirement",
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixColumn.Direction.INCOMING,
                },
            ],
        )

        # 2. Perception Spec: Requirements → Test Cases + Derived From
        self._matrix(
            name="Perception Requirements Traceability",
            description=(
                "Traces each Perception requirement to test cases that verify "
                "it and the system requirements it derives from."
            ),
            columns=[
                {
                    "label": "Requirement",
                    "seed_item_type_slug": "requirement",
                    "seed_container": perc_spec,
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixColumn.Direction.INCOMING,
                },
                {
                    "label": "Derives From",
                    "relation_name": "derives_from",
                    "direction": MatrixColumn.Direction.OUTGOING,
                },
            ],
        )

        # 3. Perception FMEA: Failure Modes → Causes + Challenged Requirements
        self._matrix(
            name="Perception FMEA Analysis",
            description=(
                "Links each Perception failure mode to its root causes and "
                "the requirements it challenges."
            ),
            columns=[
                {
                    "label": "Failure Mode",
                    "seed_item_type_slug": "failure-mode",
                    "seed_container": perc_fmea,
                },
                {
                    "label": "Caused By",
                    "relation_name": "causes",
                    "direction": MatrixColumn.Direction.INCOMING,
                },
                {
                    "label": "Challenged Requirements",
                    "relation_name": "mitigates",
                    "direction": MatrixColumn.Direction.OUTGOING,
                },
            ],
        )

        # 4. Safety FMEA: Failure Modes → Causes + Threatened Requirements
        self._matrix(
            name="Safety FMEA Analysis",
            description=(
                "Links each Safety failure mode to its root causes and "
                "the requirements it threatens."
            ),
            columns=[
                {
                    "label": "Failure Mode",
                    "seed_item_type_slug": "failure-mode",
                    "seed_container": safety_fmea,
                },
                {
                    "label": "Caused By",
                    "relation_name": "causes",
                    "direction": MatrixColumn.Direction.INCOMING,
                },
                {
                    "label": "Threatened Requirements",
                    "relation_name": "mitigates",
                    "direction": MatrixColumn.Direction.OUTGOING,
                },
            ],
        )

        # 5. Risk Assessment: Risks → Challenged Requirements
        self._matrix(
            name="Risk Assessment Matrix",
            description=(
                "Shows each risk and the requirements it challenges, "
                "providing an overview for risk acceptability review."
            ),
            columns=[
                {
                    "label": "Risk",
                    "seed_item_type_slug": "risk",
                    "seed_container": risk_assessment,
                },
                {
                    "label": "Challenged Requirements",
                    "relation_name": "mitigates",
                    "direction": MatrixColumn.Direction.OUTGOING,
                },
            ],
        )

        # 6. TARA: Threats → Exploited Vulnerabilities + Mitigations
        self._matrix(
            name="Threat Analysis and Risk Assessment (TARA)",
            description=(
                "ISO/SAE 21434 TARA matrix linking each threat to the "
                "vulnerabilities it exploits and the mitigations applied."
            ),
            columns=[
                {
                    "label": "Threat",
                    "seed_item_type_slug": "threat",
                    "seed_container": tara,
                },
                {
                    "label": "Exploited Vulnerabilities",
                    "relation_name": "exploits",
                    "direction": MatrixColumn.Direction.OUTGOING,
                },
                {
                    "label": "Mitigations",
                    "relation_name": "mitigates",
                    "direction": MatrixColumn.Direction.INCOMING,
                },
            ],
        )

        # 7. Requirement Decomposition: High-level → Sub-requirements
        self._matrix(
            name="Requirement Decomposition Matrix",
            description=(
                "Shows how high-level system requirements are decomposed "
                "into lower-level sub-requirements."
            ),
            columns=[
                {
                    "label": "System Requirement",
                    "seed_item_type_slug": "requirement",
                    "seed_container": sys_req_spec,
                },
                {
                    "label": "Refined By",
                    "relation_name": "refines",
                    "direction": MatrixColumn.Direction.OUTGOING,
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixColumn.Direction.INCOMING,
                },
            ],
        )

    # ------------------------------------------------------------------
    # Avionics FMS example data
    # ------------------------------------------------------------------

    def _build_avionics(self):
        # ==============================================================
        # TOP-LEVEL PROGRAMME
        # ==============================================================
        programme = self._item(
            "project",
            "FMS-3000 Flight Management System",
            "Development programme for the FMS-3000 flight management system, "
            "a DAL A/B avionics unit providing lateral and vertical navigation, "
            "performance computation, and flight planning for Part 25 transport "
            "category aircraft.",
            **{"standard-reference": "ARP4754A, DO-178C, DO-254, DO-326A"},
        )

        # ==============================================================
        # PLANS
        # ==============================================================
        sys_dev_plan = self._item(
            "plan",
            "System Development Plan",
            "Defines the system-level development process for the FMS-3000 "
            "including requirements capture, allocation to hardware and "
            "software, integration, and certification liaison activities "
            "per ARP4754A.",
            **{"phase": "Approved",
               "standard-reference": "ARP4754A §5"},
        )
        sw_dev_plan = self._item(
            "plan",
            "Software Development Plan",
            "Describes the software life cycle processes, standards, tools, "
            "and environment for the FMS-3000 application software. Covers "
            "planning, requirements, design, coding, integration, and "
            "verification per DO-178C objectives for DAL A software.",
            **{"phase": "Approved",
               "standard-reference": "DO-178C §11.1"},
        )
        sw_ver_plan = self._item(
            "plan",
            "Software Verification Plan",
            "Defines the verification strategy, methods, tools, and "
            "environment for demonstrating that the FMS-3000 software "
            "satisfies its requirements and DO-178C objectives including "
            "structural coverage analysis.",
            **{"phase": "Approved",
               "standard-reference": "DO-178C §11.3"},
        )
        safety_plan = self._item(
            "plan",
            "Safety Assessment Plan",
            "Describes the safety assessment process, methods, and schedule "
            "for the FMS-3000. Covers Functional Hazard Assessment, "
            "Preliminary System Safety Assessment, System Safety Assessment, "
            "and Common Cause Analysis per ARP4761.",
            **{"phase": "Approved",
               "standard-reference": "ARP4761"},
        )
        hw_dev_plan = self._item(
            "plan",
            "Hardware Development Plan",
            "Describes the hardware design assurance process for the FMS "
            "processor module, I/O boards, and display controller per "
            "DO-254. Covers planning, requirements capture, conceptual "
            "design, detailed design, and verification.",
            **{"phase": "Review",
               "standard-reference": "DO-254 §10.1"},
        )

        self._compose(programme, sys_dev_plan, sw_dev_plan, sw_ver_plan,
                       safety_plan, hw_dev_plan)

        # ==============================================================
        # PLAN SECTIONS (Information items)
        # ==============================================================

        # -- System Development Plan sections --
        sdp_purpose = self._item(
            "information",
            "Purpose",
            "This plan establishes the system-level development process "
            "for the FMS-3000 flight management system. It serves as the "
            "primary reference for all engineering activities from "
            "requirements capture through certification.",
        )
        sdp_scope = self._item(
            "information",
            "Scope",
            "Covers the FMS computer unit (LRU), its interfaces to "
            "ARINC 429/629 avionics buses, ARINC 661 display system, "
            "GNSS receivers, and inertial reference units. Does not cover "
            "airframe integration or airline-specific operational procedures.",
        )
        sdp_lifecycle = self._item(
            "information",
            "Development Lifecycle",
            "The programme follows the ARP4754A V-model with defined "
            "review gates at each phase: System Requirements Review (SRR), "
            "Preliminary Design Review (PDR), Critical Design Review (CDR), "
            "and First Article Inspection (FAI). Software development "
            "within each phase follows DO-178C processes.",
        )
        sdp_cert = self._item(
            "information",
            "Certification Liaison",
            "Certification activities follow FAA Order 8110.49 and EASA "
            "CS-25. Stage of Involvement (SOI) reviews are planned at "
            "SOI #1 (planning), SOI #2 (development), SOI #3 (verification), "
            "and SOI #4 (final certification). DER/CVE involvement is "
            "required for all DAL A functions.",
        )
        self._compose(sys_dev_plan, sdp_purpose, sdp_scope, sdp_lifecycle,
                       sdp_cert)

        # -- Software Development Plan sections --
        swdp_purpose = self._item(
            "information",
            "Purpose",
            "This plan defines the software life cycle processes for the "
            "FMS-3000 application software classified as DAL A under "
            "DO-178C. It addresses all objectives in tables A-1 through A-10.",
        )
        swdp_standards = self._item(
            "information",
            "Software Development Standards",
            "Coding standard: MISRA C:2012 with DO-178C supplement.\n"
            "Design standard: UML-based architectural modelling with formal "
            "interface definitions.\n"
            "Requirements standard: EARS (Easy Approach to Requirements "
            "Syntax) for unambiguous natural-language requirements.",
        )
        swdp_environment = self._item(
            "information",
            "Software Development Environment",
            "Host platform: Linux workstations with qualified cross-compiler "
            "(Tool Qualification TQL-5 per DO-330).\n"
            "Target platform: PowerPC-based FMS processor module.\n"
            "Configuration management: Git with qualified branching model.\n"
            "Requirements management: Verity tool suite.",
        )
        self._compose(sw_dev_plan, swdp_purpose, swdp_standards, swdp_environment)

        # -- Safety Assessment Plan sections --
        sap_purpose = self._item(
            "information",
            "Purpose",
            "This plan defines the safety assessment activities for the "
            "FMS-3000, ensuring that potential failure conditions are "
            "identified, classified, and mitigated to acceptable levels.",
        )
        sap_methods = self._item(
            "information",
            "Safety Assessment Methods",
            "The following methods are employed per ARP4761:\n"
            "• Functional Hazard Assessment (FHA) — identifies failure "
            "conditions and assigns severity classifications\n"
            "• Preliminary System Safety Assessment (PSSA) — derives safety "
            "requirements from the FHA using fault trees\n"
            "• System Safety Assessment (SSA) — verifies that safety "
            "requirements are met through FMEA and analysis of the "
            "implemented design\n"
            "• Common Cause Analysis (CCA) — assesses vulnerability to "
            "common-mode failures, zonal hazards, and particular risks",
        )
        self._compose(safety_plan, sap_purpose, sap_methods)

        # ==============================================================
        # SPECIFICATIONS
        # ==============================================================
        sys_req_spec = self._item(
            "specification",
            "System Requirements Document",
            "Captures all system-level functional and performance requirements "
            "for the FMS-3000, allocated from aircraft-level requirements and "
            "derived from safety analysis.",
            **{"baseline": "SRD-BL-4",
               "standard-reference": "ARP4754A §5.3"},
        )
        sw_hlr_spec = self._item(
            "specification",
            "Software High-Level Requirements",
            "Software requirements derived from system requirements and "
            "safety requirements for the FMS-3000 application software. "
            "These are the primary basis for software design and "
            "verification per DO-178C §5.1.",
            **{"baseline": "SHLR-BL-3",
               "standard-reference": "DO-178C §11.8"},
        )
        sw_llr_spec = self._item(
            "specification",
            "Software Low-Level Requirements",
            "Detailed software design requirements that directly drive "
            "source code implementation. Derived from high-level "
            "requirements and architectural design decisions.",
            **{"baseline": "SLLR-BL-2",
               "standard-reference": "DO-178C §11.9"},
        )
        hw_req_spec = self._item(
            "specification",
            "Hardware Requirements Specification",
            "Requirements for the FMS processor module, I/O interface "
            "boards, and power supply unit derived from system requirements "
            "and safety analysis.",
            **{"baseline": "HRS-BL-1",
               "standard-reference": "DO-254 §5.1"},
        )

        self._compose(programme, sys_req_spec, sw_hlr_spec, sw_llr_spec,
                       hw_req_spec)

        # ==============================================================
        # SAFETY ANALYSES
        # ==============================================================
        fha = self._item(
            "analysis",
            "Functional Hazard Assessment",
            "Identifies failure conditions of the FMS-3000 at the aircraft "
            "level and classifies each by severity (Catastrophic, Hazardous, "
            "Major, Minor, No Safety Effect) per AC 25.1309.",
            **{"method": "HARA",
               "standard-reference": "ARP4761 §4, AC 25.1309-1A"},
        )
        pssa = self._item(
            "analysis",
            "Preliminary System Safety Assessment",
            "Derives safety requirements from the FHA using fault tree "
            "analysis and reliability modelling. Determines required DAL "
            "for each function and establishes quantitative safety targets.",
            **{"method": "FTA",
               "standard-reference": "ARP4761 §5"},
        )
        ssa = self._item(
            "analysis",
            "System Safety Assessment",
            "Verifies that the implemented FMS-3000 design meets all "
            "safety requirements derived in the PSSA. Uses bottom-up FMEA "
            "and updated fault trees to confirm residual failure "
            "probabilities are within budget.",
            **{"method": "FMEA",
               "standard-reference": "ARP4761 §6, IEC 60812"},
        )
        cca = self._item(
            "analysis",
            "Common Cause Analysis",
            "Evaluates the FMS-3000 for vulnerability to common-mode "
            "failures that could defeat redundancy. Includes zonal safety "
            "analysis, particular risks assessment, and common-mode "
            "failure analysis per ARP4761 Appendix E.",
            **{"method": "Other",
               "standard-reference": "ARP4761 Appendix E"},
        )

        self._compose(programme, fha, pssa, ssa, cca)

        # ==============================================================
        # REPORTS
        # ==============================================================
        sw_ver_report = self._item(
            "report",
            "Software Verification Results Report",
            "Records the results of all software verification activities "
            "including requirements-based testing, structural coverage "
            "analysis, and review/analysis results per DO-178C §11.14.",
            **{"report-status": "Draft"},
        )
        sw_config_index = self._item(
            "report",
            "Software Configuration Index",
            "Identifies the configuration of the software product, "
            "including all life cycle data items, their versions, and "
            "the tools used to produce them per DO-178C §11.16.",
            **{"report-status": "Draft"},
        )
        sw_qa_report = self._item(
            "report",
            "Software Quality Assurance Report",
            "Summarises SQA audit results, process compliance findings, "
            "and status of all open problem reports per DO-178C §11.18.",
            **{"report-status": "Draft"},
        )
        safety_assessment_report = self._item(
            "report",
            "Safety Assessment Report",
            "Consolidates results from the FHA, PSSA, SSA, and CCA into "
            "a single report demonstrating compliance with AC 25.1309 "
            "safety objectives.",
            **{"report-status": "Draft"},
        )

        self._compose(programme, sw_ver_report, sw_config_index,
                       sw_qa_report, safety_assessment_report)

        # ==============================================================
        # SYSTEM-LEVEL REQUIREMENTS (inside System Requirements Document)
        # ==============================================================
        req_nav_accuracy = self._item(
            "requirement",
            "Navigation accuracy shall be ≤ 0.1 NM for RNP operations",
            "The FMS shall compute lateral position with total system error "
            "not exceeding 0.1 NM (95 %) to support RNP 0.1 approach "
            "operations as defined in RTCA DO-283B.",
            priority="Critical", **{"verification-method": "Test"},
        )
        req_availability = self._item(
            "requirement",
            "System availability shall be ≥ 99.999 % per flight hour",
            "The FMS function shall meet a loss-of-function probability "
            "of no greater than 1 × 10⁻⁵ per flight hour, consistent "
            "with a Major failure condition classification.",
            priority="Critical", **{"verification-method": "Analysis"},
        )
        req_mtbf = self._item(
            "requirement",
            "MTBF shall be ≥ 5,000 flight hours",
            "The FMS LRU shall demonstrate a mean time between failures "
            "of at least 5,000 flight hours based on in-service data or "
            "reliability prediction per MIL-HDBK-217.",
            priority="High", **{"verification-method": "Analysis"},
        )
        req_perf_compute = self._item(
            "requirement",
            "Performance computation shall complete within 2 seconds",
            "All performance computations (takeoff, landing, cruise "
            "optimisation) shall produce results within 2 seconds of "
            "crew initiation on the CDU.",
            priority="High", **{"verification-method": "Test"},
        )
        req_arinc_429 = self._item(
            "requirement",
            "System shall interface via ARINC 429 and ARINC 629 buses",
            "The FMS shall receive and transmit data on ARINC 429 low- "
            "and high-speed buses and ARINC 629 data bus per the "
            "applicable Interface Control Documents.",
            priority="High", **{"verification-method": "Test"},
        )
        req_dal_a = self._item(
            "requirement",
            "Navigation function shall be developed to DAL A",
            "All software and hardware items implementing the navigation "
            "function shall comply with DAL A assurance objectives per "
            "DO-178C and DO-254 respectively, as derived from the FHA "
            "Hazardous classification.",
            priority="Critical", **{"verification-method": "Analysis"},
        )

        self._compose(sys_req_spec, req_nav_accuracy, req_availability,
                       req_mtbf, req_perf_compute, req_arinc_429, req_dal_a)

        # ==============================================================
        # SOFTWARE HIGH-LEVEL REQUIREMENTS (inside SHLR spec)
        # ==============================================================
        hlr_flight_plan = self._item(
            "requirement",
            "FMS shall compute a flight plan route within 2 seconds",
            "Given a departure, destination, and airway/waypoint sequence, "
            "the FMS shall compute the complete lateral and vertical "
            "flight plan within 2 seconds of crew activation.",
            priority="High", **{"verification-method": "Test"},
        )
        hlr_pos_update = self._item(
            "requirement",
            "Position update rate shall be ≥ 20 Hz",
            "The navigation filter shall produce updated position, "
            "velocity, and time estimates at a minimum rate of 20 Hz.",
            priority="Critical", **{"verification-method": "Test"},
        )
        hlr_db_crc = self._item(
            "requirement",
            "Navigation database CRC shall be verified at power-up",
            "On each power-up, the FMS shall compute a CRC-32 over the "
            "entire navigation database and compare it against the stored "
            "reference value. A mismatch shall inhibit use of the database "
            "and annunciate a fault to the crew.",
            priority="Critical", **{"verification-method": "Test"},
        )
        hlr_lateral_dev = self._item(
            "requirement",
            "Lateral deviation display shall update within 100 ms",
            "The computed lateral deviation (cross-track error) shall be "
            "transmitted to the display system within 100 ms of the "
            "navigation solution update.",
            priority="High", **{"verification-method": "Test"},
        )
        hlr_vnav = self._item(
            "requirement",
            "FMS shall provide VNAV guidance from TOC to TOD",
            "The FMS shall compute and transmit vertical navigation "
            "guidance (target altitude, vertical speed, flight path angle) "
            "from top of climb to top of descent, accounting for wind "
            "and temperature deviations.",
            priority="High", **{"verification-method": "Test"},
        )
        hlr_integrity = self._item(
            "requirement",
            "FMS shall detect and annunciate navigation integrity failures",
            "The FMS shall monitor navigation source integrity using RAIM "
            "or equivalent. When integrity cannot be assured, the FMS "
            "shall annunciate 'NAV UNABLE RNP' within 1 second.",
            priority="Critical", **{"verification-method": "Test"},
        )

        self._compose(sw_hlr_spec, hlr_flight_plan, hlr_pos_update,
                       hlr_db_crc, hlr_lateral_dev, hlr_vnav, hlr_integrity)

        # Derive HLR from system requirements
        self._derives(hlr_flight_plan, req_perf_compute)
        self._derives(hlr_pos_update, req_nav_accuracy)
        self._derives(hlr_db_crc, req_nav_accuracy)
        self._derives(hlr_lateral_dev, req_nav_accuracy)
        self._derives(hlr_vnav, req_nav_accuracy, req_perf_compute)
        self._derives(hlr_integrity, req_nav_accuracy, req_dal_a)

        # ==============================================================
        # SOFTWARE LOW-LEVEL REQUIREMENTS (inside SLLR spec)
        # ==============================================================
        llr_db_loader = self._item(
            "requirement",
            "Database loader shall validate CRC-32 on all navigation records",
            "The database loader module shall compute CRC-32 for each "
            "ARINC 424 record group and compare against the index CRC. "
            "Any mismatch shall set the database_valid flag to FALSE.",
            priority="Critical", **{"verification-method": "Test"},
        )
        llr_kalman = self._item(
            "requirement",
            "Position filter Kalman gain shall converge within 10 cycles",
            "After initialisation, the Kalman filter gain matrix shall "
            "converge to steady-state values within 10 update cycles "
            "(0.5 seconds at 20 Hz).",
            priority="High", **{"verification-method": "Test"},
        )
        llr_waypoint = self._item(
            "requirement",
            "Waypoint sequencing shall handle path discontinuities",
            "When the active flight plan contains a course change > 90°, "
            "the sequencing logic shall insert a fly-by or fly-over turn "
            "anticipation segment and compute the correct transition path.",
            priority="High", **{"verification-method": "Test"},
        )
        llr_rnp_monitor = self._item(
            "requirement",
            "RNP monitoring shall compare ANP against RNP value each cycle",
            "Each navigation cycle, the Actual Navigation Performance (ANP) "
            "shall be compared against the Required Navigation Performance "
            "(RNP). If ANP > RNP for 10 consecutive cycles, the NAV UNABLE "
            "RNP alert shall be raised.",
            priority="Critical", **{"verification-method": "Test"},
        )
        llr_arinc_tx = self._item(
            "requirement",
            "ARINC 429 transmit shall complete within 1 ms per label",
            "Each ARINC 429 output label shall be loaded into the "
            "transmit register and sent within 1 ms to maintain bus "
            "timing compliance.",
            priority="High", **{"verification-method": "Test"},
        )

        self._compose(sw_llr_spec, llr_db_loader, llr_kalman, llr_waypoint,
                       llr_rnp_monitor, llr_arinc_tx)

        # Derive LLR from HLR
        self._derives(llr_db_loader, hlr_db_crc)
        self._derives(llr_kalman, hlr_pos_update)
        self._derives(llr_waypoint, hlr_flight_plan)
        self._derives(llr_rnp_monitor, hlr_integrity)
        self._derives(llr_arinc_tx, hlr_lateral_dev)

        # ==============================================================
        # REQUIREMENT DECOMPOSITION
        # ==============================================================

        # Decompose nav accuracy into sub-requirements
        req_gnss_accuracy = self._item(
            "requirement",
            "GNSS position accuracy shall be ≤ 5 m (95 %) in nominal conditions",
            "The FMS shall use dual-frequency GNSS receivers providing "
            "position accuracy of 5 m or better under open-sky conditions.",
            priority="High", **{"verification-method": "Test"},
        )
        req_iru_drift = self._item(
            "requirement",
            "IRU drift rate shall not exceed 1 NM per hour",
            "The inertial reference unit drift contribution to total "
            "system error shall not exceed 1 NM per hour of unaided "
            "inertial navigation.",
            priority="High", **{"verification-method": "Test"},
        )
        req_filter_accuracy = self._item(
            "requirement",
            "Navigation filter shall maintain ≤ 0.05 NM accuracy when aided",
            "When GNSS aiding is available, the blended navigation solution "
            "shall achieve position accuracy of 0.05 NM or better (95 %).",
            priority="Critical", **{"verification-method": "Test"},
        )

        self._refines(req_nav_accuracy, req_gnss_accuracy, req_iru_drift,
                         req_filter_accuracy)

        # Decompose availability into sub-requirements
        req_sw_partition = self._item(
            "requirement",
            "Software partitioning shall prevent fault propagation between functions",
            "ARINC 653 partitioning shall isolate the navigation function "
            "from non-critical functions so that a failure in a DAL C "
            "partition cannot affect DAL A navigation.",
            priority="Critical", **{"verification-method": "Analysis"},
        )
        req_hw_redundancy = self._item(
            "requirement",
            "Dual FMS architecture shall provide hot-standby switchover < 500 ms",
            "On detection of a failure in the active FMS, the standby unit "
            "shall assume the active role within 500 ms with no loss of "
            "navigation guidance to the autopilot.",
            priority="Critical", **{"verification-method": "Test"},
        )

        self._refines(req_availability, req_sw_partition, req_hw_redundancy)

        # ==============================================================
        # FHA CONTENTS (failure conditions inside FHA)
        # ==============================================================
        fha_loss_nav = self._item(
            "information",
            "FC-01: Loss of navigation function",
            "Complete loss of FMS navigation guidance during approach. "
            "Classification: Hazardous. Crew must revert to raw-data "
            "navigation; risk of controlled flight into terrain if "
            "undetected.\n\n"
            "**Severity classification:** Hazardous\n"
            "**Probability objective:** < 1 × 10⁻⁷ per flight hour",
        )
        fha_misleading_nav = self._item(
            "information",
            "FC-02: Misleading navigation information without annunciation",
            "FMS provides erroneous position or guidance data without crew "
            "awareness. Classification: Catastrophic. Could lead to "
            "controlled flight into terrain or mid-air collision.\n\n"
            "**Severity classification:** Catastrophic\n"
            "**Probability objective:** < 1 × 10⁻⁹ per flight hour",
        )
        fha_loss_perf = self._item(
            "information",
            "FC-03: Loss of performance computation",
            "FMS unable to provide takeoff or landing performance data. "
            "Classification: Major. Crew must use manual performance "
            "tables; increased workload.\n\n"
            "**Severity classification:** Major\n"
            "**Probability objective:** < 1 × 10⁻⁵ per flight hour",
        )
        fha_loss_fp = self._item(
            "information",
            "FC-04: Loss of flight plan management",
            "FMS unable to create or modify flight plans. Classification: "
            "Major. Crew must fly heading-based navigation; increased "
            "workload and fuel consumption.\n\n"
            "**Severity classification:** Major\n"
            "**Probability objective:** < 1 × 10⁻⁵ per flight hour",
        )

        self._compose(fha, fha_loss_nav, fha_misleading_nav, fha_loss_perf,
                       fha_loss_fp)

        # ==============================================================
        # SSA / FMEA CONTENTS (inside System Safety Assessment)
        # ==============================================================
        fm_db_corrupt = self._item(
            "failure-mode",
            "Navigation database corruption",
            "Navigation database contains corrupted waypoint coordinates "
            "or procedure data, leading to incorrect flight plan "
            "computation or misleading guidance.",
            severity="Critical",
        )
        fm_pos_diverge = self._item(
            "failure-mode",
            "Position computation divergence",
            "Kalman filter state diverges from true position due to "
            "undetected sensor faults or incorrect aiding data, "
            "producing progressively worsening navigation error.",
            severity="Critical",
        )
        fm_display_freeze = self._item(
            "failure-mode",
            "Navigation display rendering freeze",
            "The ARINC 661 display controller stops updating the "
            "navigation display, showing stale position and guidance "
            "information to the crew.",
            severity="High",
        )
        fm_bus_loss = self._item(
            "failure-mode",
            "FMS-to-autopilot ARINC 429 data link loss",
            "Loss of the ARINC 429 output bus connecting the FMS to "
            "the autopilot/flight director, causing loss of coupled "
            "navigation guidance.",
            severity="High",
        )
        fm_perf_error = self._item(
            "failure-mode",
            "Performance computation erroneous output",
            "Takeoff or landing performance computation produces "
            "incorrect V-speeds or field length due to incorrect "
            "aircraft configuration input or algorithm error.",
            severity="High",
        )

        self._compose(ssa, fm_db_corrupt, fm_pos_diverge, fm_display_freeze,
                       fm_bus_loss, fm_perf_error)

        # Failure causes
        fc_nand = self._item(
            "failure-cause",
            "NAND flash bit rot in navigation database storage",
            "Silent bit errors in the NAND flash memory storing the "
            "navigation database corrupt waypoint data over time.",
            category="Design",
        )
        fc_fp_overflow = self._item(
            "failure-cause",
            "Floating-point overflow in position filter",
            "Extreme input values (e.g. near-polar latitude) cause "
            "floating-point overflow in the Kalman filter state vector, "
            "leading to position divergence.",
            category="Software",
        )
        fc_gpu_leak = self._item(
            "failure-cause",
            "GPU memory leak in display controller",
            "A memory leak in the display rendering software gradually "
            "exhausts GPU memory, causing the display to freeze.",
            category="Software",
        )
        fc_wire_break = self._item(
            "failure-cause",
            "ARINC 429 bus wire break",
            "Physical break in the ARINC 429 twisted-pair wiring due to "
            "vibration fatigue or connector failure.",
            category="Manufacturing",
        )
        fc_config_input = self._item(
            "failure-cause",
            "Incorrect aircraft configuration data entry",
            "Crew enters wrong aircraft weight, flap setting, or runway "
            "condition, leading to erroneous performance computation.",
            category="Human Error",
        )
        fc_cosmic_ray = self._item(
            "failure-cause",
            "Single-event upset from cosmic radiation",
            "High-energy neutron strikes flip bits in processor registers "
            "or SRAM, corrupting computation results.",
            category="Environmental",
        )

        self._compose(ssa, fc_nand, fc_fp_overflow, fc_gpu_leak,
                       fc_wire_break, fc_config_input, fc_cosmic_ray)

        # Cause → mode
        self._causes(fc_nand, fm_db_corrupt)
        self._causes(fc_fp_overflow, fm_pos_diverge)
        self._causes(fc_gpu_leak, fm_display_freeze)
        self._causes(fc_wire_break, fm_bus_loss)
        self._causes(fc_config_input, fm_perf_error)
        self._causes(fc_cosmic_ray, fm_pos_diverge, fm_db_corrupt)

        # Mode → requirement
        self._mitigates(fm_db_corrupt, hlr_db_crc, req_nav_accuracy)
        self._mitigates(fm_pos_diverge, hlr_integrity, req_nav_accuracy)
        self._mitigates(fm_display_freeze, hlr_lateral_dev)
        self._mitigates(fm_bus_loss, req_arinc_429, req_availability)
        self._mitigates(fm_perf_error, req_perf_compute)

        # ==============================================================
        # RISK ASSESSMENT (inside Safety Assessment Report)
        # ==============================================================
        risk_gnss = self._item(
            "risk",
            "GNSS signal loss or degradation during RNP approach",
            "Loss of GNSS signals during an RNP approach due to "
            "interference, ionospheric scintillation, or intentional "
            "jamming, causing reversion to degraded navigation.",
            severity="High", likelihood="Possible",
            mitigation=(
                "Dual-frequency GNSS receivers with RAIM. Automatic "
                "reversion to IRU-only navigation with crew annunciation. "
                "Operational procedure to abort approach if RNP cannot be "
                "maintained."
            ),
        )
        risk_db_update = self._item(
            "risk",
            "Navigation database update introduces erroneous data",
            "An AIRAC cycle update contains incorrect procedure or "
            "waypoint data due to data provider error, affecting flight "
            "plan accuracy.",
            severity="Critical", likelihood="Unlikely",
            mitigation=(
                "CRC-32 validation at load time. Cross-check of critical "
                "procedures against NOTAMs. Qualification of database "
                "supplier per DO-200B."
            ),
        )
        risk_common_mode = self._item(
            "risk",
            "Common-mode software fault in dual FMS installation",
            "A software defect present in both FMS units causes "
            "simultaneous failure of the active and standby FMS, "
            "resulting in total loss of FMS function.",
            severity="Critical", likelihood="Rare",
            mitigation=(
                "DAL A development and verification processes per DO-178C. "
                "Modified Condition/Decision Coverage analysis. "
                "Independent review of safety-critical algorithms."
            ),
        )
        risk_seu = self._item(
            "risk",
            "Single-event upset causes undetected computation error",
            "A cosmic ray-induced bit flip in the processor or memory "
            "corrupts a safety-critical computation without detection, "
            "leading to misleading guidance.",
            severity="Critical", likelihood="Possible",
            mitigation=(
                "ECC memory for all safety-critical data. Dual-lock-step "
                "processor comparison for DAL A functions. Software "
                "reasonableness checks on all outputs."
            ),
        )

        self._compose(safety_assessment_report, risk_gnss, risk_db_update,
                       risk_common_mode, risk_seu)

        # Risk → requirement
        self._mitigates(risk_gnss, req_nav_accuracy, req_availability)
        self._mitigates(risk_db_update, hlr_db_crc, req_nav_accuracy)
        self._mitigates(risk_common_mode, req_availability, req_dal_a)
        self._mitigates(risk_seu, req_dal_a, hlr_integrity)

        # ==============================================================
        # SECURITY ASSESSMENT (DO-326A / ED-202A)
        # ==============================================================
        security_spec = self._item(
            "specification",
            "Security Requirements Specification",
            "Airworthiness security requirements for the FMS-3000 derived "
            "from threat assessment per DO-326A / ED-202A, covering data "
            "loading, maintenance ports, and datalink interfaces.",
            **{"baseline": "SEC-BL-1",
               "standard-reference": "DO-326A, ED-202A"},
        )
        tara = self._item(
            "analysis",
            "Threat Assessment (DO-326A)",
            "Systematic identification and evaluation of intentional "
            "unauthorised electronic interactions (IUEI) for the FMS-3000 "
            "per DO-326A / ED-202A.",
            **{"method": "Other",
               "standard-reference": "DO-326A §4"},
        )

        self._compose(programme, security_spec, tara)

        # Security requirements
        req_sec_dataload = self._item(
            "requirement",
            "Database loading shall verify cryptographic signature",
            "All navigation database and software loads shall be "
            "cryptographically signed. The FMS shall verify the signature "
            "using a stored public key before accepting the load.",
            priority="Critical", **{"verification-method": "Test"},
        )
        req_sec_maint = self._item(
            "requirement",
            "Maintenance port access shall require authentication",
            "The FMS maintenance port (ARINC 615A data loader interface) "
            "shall require certificate-based authentication before "
            "accepting any configuration or software load commands.",
            priority="High", **{"verification-method": "Test"},
        )
        req_sec_datalink = self._item(
            "requirement",
            "ACARS/VDL datalink messages shall be authenticated",
            "All uplink messages received via ACARS or VDL Mode 2 that "
            "affect the active flight plan shall be authenticated and "
            "integrity-checked before processing.",
            priority="High", **{"verification-method": "Test"},
        )

        self._compose(security_spec, req_sec_dataload, req_sec_maint,
                       req_sec_datalink)
        self._derives(req_sec_dataload, req_dal_a)

        # Threats
        thr_gps_spoof = self._item(
            "threat",
            "GPS spoofing via counterfeit GNSS signals",
            "An attacker broadcasts counterfeit GNSS signals to mislead "
            "the FMS navigation solution, potentially causing the "
            "aircraft to deviate from the intended flight path.",
            **{"threat-level": "Critical", "attack-vector": "Adjacent",
               "threat-agent": "State-level actor or sophisticated attacker"},
        )
        thr_malicious_db = self._item(
            "threat",
            "Malicious navigation database injection",
            "An attacker inserts tampered navigation data during the "
            "database loading process, modifying waypoint coordinates "
            "or procedure definitions.",
            **{"threat-level": "Critical", "attack-vector": "Physical",
               "threat-agent": "Insider with maintenance access"},
        )
        thr_maint_access = self._item(
            "threat",
            "Unauthorised maintenance port access",
            "An attacker gains physical access to the FMS maintenance "
            "port and attempts to upload unauthorised software or "
            "extract sensitive data.",
            **{"threat-level": "High", "attack-vector": "Physical",
               "threat-agent": "Insider or opportunistic attacker"},
        )
        thr_datalink = self._item(
            "threat",
            "ACARS uplink message injection",
            "An attacker injects forged ACARS uplink messages to modify "
            "the active flight plan waypoints or performance parameters.",
            **{"threat-level": "High", "attack-vector": "Network",
               "threat-agent": "Remote attacker with radio equipment"},
        )

        self._compose(tara, thr_gps_spoof, thr_malicious_db,
                       thr_maint_access, thr_datalink)

        # Vulnerabilities
        vuln_gnss_noauth = self._item(
            "vulnerability",
            "GNSS civil signals lack authentication",
            "GPS L1 C/A and L5 civil signals do not include native "
            "authentication, allowing spoofing with commercially "
            "available equipment.",
            severity="Critical",
            **{"attack-feasibility": "High",
               "component": "GNSS receiver"},
        )
        vuln_db_unsigned = self._item(
            "vulnerability",
            "Legacy database loader accepts unsigned data",
            "The current database loader only verifies ARINC 424 format "
            "but does not verify a cryptographic signature over the "
            "database contents.",
            severity="Critical",
            **{"attack-feasibility": "Medium",
               "component": "Database loader"},
        )
        vuln_maint_noauth = self._item(
            "vulnerability",
            "Maintenance port lacks access authentication",
            "The ARINC 615A data loader interface accepts connections "
            "without authentication, relying solely on physical access "
            "control.",
            severity="High",
            **{"attack-feasibility": "Medium",
               "component": "Maintenance interface"},
        )
        vuln_acars_noauth = self._item(
            "vulnerability",
            "ACARS messages not integrity-protected",
            "ACARS uplink messages are accepted without message "
            "authentication codes, relying on procedural controls.",
            severity="High",
            **{"attack-feasibility": "Medium",
               "component": "ACARS interface"},
        )

        self._compose(tara, vuln_gnss_noauth, vuln_db_unsigned,
                       vuln_maint_noauth, vuln_acars_noauth)

        # Threat → Vulnerability
        self._exploits(thr_gps_spoof, vuln_gnss_noauth)
        self._exploits(thr_malicious_db, vuln_db_unsigned)
        self._exploits(thr_maint_access, vuln_maint_noauth)
        self._exploits(thr_datalink, vuln_acars_noauth)

        # Mitigations
        mit_raim = self._item(
            "mitigation",
            "RAIM and dual-frequency GNSS cross-check",
            "Implement Receiver Autonomous Integrity Monitoring with "
            "dual-frequency cross-checking to detect spoofed or "
            "anomalous GNSS signals.",
            **{"control-type": "Detective",
               "implementation-status": "Implemented"},
        )
        mit_db_signing = self._item(
            "mitigation",
            "Cryptographic database signing per DO-200B",
            "Sign all navigation databases with RSA-2048 using an "
            "offline signing authority. The FMS verifies the signature "
            "against a securely stored public key before loading.",
            **{"control-type": "Preventive",
               "implementation-status": "Implemented"},
        )
        mit_maint_auth = self._item(
            "mitigation",
            "Certificate-based maintenance port authentication",
            "Require X.509 certificate exchange on the maintenance "
            "port before accepting any data loader commands. "
            "Certificates are provisioned during manufacture.",
            **{"control-type": "Preventive",
               "implementation-status": "In Progress"},
        )
        mit_acars_mac = self._item(
            "mitigation",
            "ACARS message authentication code verification",
            "Implement HMAC-SHA256 verification on all ACARS uplink "
            "messages that modify the active flight plan. Messages "
            "without valid MACs are rejected and logged.",
            **{"control-type": "Preventive",
               "implementation-status": "Planned"},
        )

        self._compose(tara, mit_raim, mit_db_signing, mit_maint_auth,
                       mit_acars_mac)

        # Mitigation → Vulnerability
        self._mitigates(mit_raim, vuln_gnss_noauth)
        self._mitigates(mit_db_signing, vuln_db_unsigned)
        self._mitigates(mit_maint_auth, vuln_maint_noauth)
        self._mitigates(mit_acars_mac, vuln_acars_noauth)

        # Mitigation → Requirement
        self._mitigates(mit_raim, hlr_integrity, req_nav_accuracy)
        self._mitigates(mit_db_signing, req_sec_dataload)
        self._mitigates(mit_maint_auth, req_sec_maint)
        self._mitigates(mit_acars_mac, req_sec_datalink)

        # Threat → Requirement
        self._mitigates(thr_gps_spoof, req_nav_accuracy, hlr_integrity)
        self._mitigates(thr_malicious_db, hlr_db_crc, req_sec_dataload)
        self._mitigates(thr_maint_access, req_sec_maint)
        self._mitigates(thr_datalink, req_sec_datalink)

        # ==============================================================
        # VERIFICATION TEST CASES (inside Software Verification Plan)
        # ==============================================================

        # -- Navigation verification --
        tc_nav_accuracy = self._item(
            "test-case",
            "VER-NAV-001: RNP 0.1 navigation accuracy test",
            "Verify the FMS meets 0.1 NM accuracy under simulated RNP "
            "approach conditions.",
            **{
                "test-steps": (
                    "1. Configure HIL simulator with known reference trajectory.\n"
                    "2. Inject GNSS and IRU data for an RNP 0.1 approach.\n"
                    "3. Record FMS computed position at 20 Hz.\n"
                    "4. Compare against reference; compute 95th-percentile error."
                ),
                "expected-result": "95th-percentile total system error ≤ 0.1 NM.",
            },
        )
        tc_pos_rate = self._item(
            "test-case",
            "VER-NAV-002: Position update rate verification",
            "Verify the navigation filter produces outputs at ≥ 20 Hz.",
            **{
                "test-steps": (
                    "1. Run FMS in HIL with nominal sensor inputs.\n"
                    "2. Monitor ARINC 429 output labels for position data.\n"
                    "3. Measure update interval over 10,000 cycles."
                ),
                "expected-result": "Mean update rate ≥ 20 Hz; no gap > 100 ms.",
            },
        )
        tc_db_crc = self._item(
            "test-case",
            "VER-NAV-003: Navigation database CRC check",
            "Verify that a corrupted database is detected and rejected.",
            **{
                "test-steps": (
                    "1. Load a known-good navigation database.\n"
                    "2. Flip one bit in a waypoint record.\n"
                    "3. Power-cycle the FMS.\n"
                    "4. Verify CRC check fails and 'NAV DB FAIL' annunciation appears."
                ),
                "expected-result": "Corrupted database rejected; fault annunciated.",
            },
        )
        tc_integrity = self._item(
            "test-case",
            "VER-NAV-004: Navigation integrity monitoring test",
            "Verify FMS detects and annunciates loss of RNP integrity.",
            **{
                "test-steps": (
                    "1. Simulate gradual GNSS degradation during RNP approach.\n"
                    "2. Monitor for 'NAV UNABLE RNP' annunciation.\n"
                    "3. Verify annunciation occurs within 1 second of ANP > RNP."
                ),
                "expected-result": "'NAV UNABLE RNP' annunciated within 1 s.",
            },
        )

        self._compose(sw_ver_plan, tc_nav_accuracy, tc_pos_rate, tc_db_crc,
                       tc_integrity)

        # -- Flight planning verification --
        tc_fp_compute = self._item(
            "test-case",
            "VER-FP-001: Flight plan computation time",
            "Verify flight plan computation completes within 2 seconds.",
            **{
                "test-steps": (
                    "1. Enter a 15-waypoint flight plan on the CDU.\n"
                    "2. Press EXEC and start timer.\n"
                    "3. Record time to route display completion.\n"
                    "4. Repeat with 50-waypoint plan."
                ),
                "expected-result": "Computation time ≤ 2 s for both cases.",
            },
        )
        tc_vnav = self._item(
            "test-case",
            "VER-FP-002: VNAV guidance accuracy",
            "Verify VNAV profile computation against reference trajectories.",
            **{
                "test-steps": (
                    "1. Load reference flight plan with known wind data.\n"
                    "2. Compare FMS VNAV targets (altitude, VS) against "
                    "certified reference at 20 waypoints.\n"
                    "3. Record deviations."
                ),
                "expected-result": "Altitude deviation ≤ 50 ft; VS deviation ≤ 100 fpm.",
            },
        )
        tc_discontinuity = self._item(
            "test-case",
            "VER-FP-003: Path discontinuity handling",
            "Verify correct waypoint sequencing at course changes > 90°.",
            **{
                "test-steps": (
                    "1. Create flight plan with 120° course change.\n"
                    "2. Fly the plan in HIL simulation.\n"
                    "3. Verify turn anticipation segment is inserted.\n"
                    "4. Verify no lateral deviation exceedance during turn."
                ),
                "expected-result": "Smooth transition with XTK ≤ 0.05 NM.",
            },
        )

        self._compose(sw_ver_plan, tc_fp_compute, tc_vnav, tc_discontinuity)

        # -- Performance computation verification --
        tc_perf = self._item(
            "test-case",
            "VER-PERF-001: Takeoff performance computation",
            "Verify takeoff V-speeds and field length against certified "
            "performance data.",
            **{
                "test-steps": (
                    "1. Enter aircraft weight, temperature, pressure altitude, "
                    "and runway length for 10 standard conditions.\n"
                    "2. Compare FMS-computed V1, VR, V2 against certified tables.\n"
                    "3. Compare field length required."
                ),
                "expected-result": "V-speed error ≤ 1 kt; field length error ≤ 50 ft.",
            },
        )

        self._compose(sw_ver_plan, tc_perf)

        # -- Structural coverage test cases (DO-178C DAL A) --
        tc_mcdc = self._item(
            "test-case",
            "VER-COV-001: MC/DC structural coverage analysis",
            "Verify Modified Condition/Decision Coverage meets DO-178C "
            "DAL A objectives for all source code modules.",
            **{
                "test-steps": (
                    "1. Execute full requirements-based test suite.\n"
                    "2. Collect MC/DC coverage data using qualified tool.\n"
                    "3. Identify gaps and add supplementary test cases.\n"
                    "4. Analyse uncoverable code and document justifications."
                ),
                "expected-result": "100 % MC/DC achieved or all gaps justified.",
            },
        )
        tc_stack = self._item(
            "test-case",
            "VER-COV-002: Stack usage analysis",
            "Verify worst-case stack usage is within allocated limits.",
            **{
                "test-steps": (
                    "1. Run static stack analysis tool on all tasks.\n"
                    "2. Add measured interrupt stack to each task's worst case.\n"
                    "3. Verify total ≤ 80 % of allocated stack per ARINC 653 partition."
                ),
                "expected-result": "All partitions ≤ 80 % stack utilisation.",
            },
        )

        self._compose(sw_ver_plan, tc_mcdc, tc_stack)

        # -- Security verification --
        tc_sec_db = self._item(
            "test-case",
            "VER-SEC-001: Database signature verification",
            "Verify that unsigned or tampered databases are rejected.",
            **{
                "test-steps": (
                    "1. Attempt to load a database without a signature.\n"
                    "2. Attempt to load a database with an invalid signature.\n"
                    "3. Load a correctly signed database.\n"
                    "4. Verify only the valid load succeeds."
                ),
                "expected-result": "Unsigned/tampered loads rejected; valid load accepted.",
            },
        )
        tc_sec_maint = self._item(
            "test-case",
            "VER-SEC-002: Maintenance port authentication test",
            "Verify the maintenance port rejects unauthenticated connections.",
            **{
                "test-steps": (
                    "1. Connect to maintenance port without certificate.\n"
                    "2. Verify connection is rejected.\n"
                    "3. Connect with valid certificate.\n"
                    "4. Verify connection is accepted."
                ),
                "expected-result": "Unauthenticated connections refused.",
            },
        )

        self._compose(sw_ver_plan, tc_sec_db, tc_sec_maint)

        # ==============================================================
        # VERIFICATION RELATIONS (test case verifies requirement)
        # ==============================================================

        # Navigation tests → requirements
        self._verifies(tc_nav_accuracy, req_nav_accuracy, req_filter_accuracy)
        self._verifies(tc_pos_rate, hlr_pos_update, llr_kalman)
        self._verifies(tc_db_crc, hlr_db_crc, llr_db_loader)
        self._verifies(tc_integrity, hlr_integrity, llr_rnp_monitor)

        # Flight planning tests → requirements
        self._verifies(tc_fp_compute, hlr_flight_plan, req_perf_compute)
        self._verifies(tc_vnav, hlr_vnav)
        self._verifies(tc_discontinuity, llr_waypoint)

        # Performance tests → requirements
        self._verifies(tc_perf, req_perf_compute)

        # Coverage tests → DAL A
        self._verifies(tc_mcdc, req_dal_a)
        self._verifies(tc_stack, req_sw_partition)

        # Security tests → security requirements
        self._verifies(tc_sec_db, req_sec_dataload)
        self._verifies(tc_sec_maint, req_sec_maint)

        # ==============================================================
        # MATRICES (traceability tables)
        # ==============================================================

        # 1. System RTM: Requirements → Verifying Test Cases
        self._matrix(
            name="System Requirements Traceability Matrix",
            description=(
                "Traces every system requirement to the verification "
                "test cases that cover it."
            ),
            columns=[
                {
                    "label": "Requirement",
                    "seed_item_type_slug": "requirement",
                    "seed_container": sys_req_spec,
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixColumn.Direction.INCOMING,
                },
            ],
        )

        # 2. Software HLR → Tests + Derived From
        self._matrix(
            name="Software HLR Traceability",
            description=(
                "Traces each Software High-Level Requirement to its "
                "verification test cases and the system requirements "
                "it derives from."
            ),
            columns=[
                {
                    "label": "High-Level Requirement",
                    "seed_item_type_slug": "requirement",
                    "seed_container": sw_hlr_spec,
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixColumn.Direction.INCOMING,
                },
                {
                    "label": "Derives From",
                    "relation_name": "derives_from",
                    "direction": MatrixColumn.Direction.OUTGOING,
                },
            ],
        )

        # 3. Software LLR → Tests + Derived From HLR
        self._matrix(
            name="Software LLR Traceability",
            description=(
                "Traces each Software Low-Level Requirement to its "
                "verification test cases and the HLRs it derives from."
            ),
            columns=[
                {
                    "label": "Low-Level Requirement",
                    "seed_item_type_slug": "requirement",
                    "seed_container": sw_llr_spec,
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixColumn.Direction.INCOMING,
                },
                {
                    "label": "Derives From",
                    "relation_name": "derives_from",
                    "direction": MatrixColumn.Direction.OUTGOING,
                },
            ],
        )

        # 4. SSA FMEA: Failure Modes → Causes + Challenged Requirements
        self._matrix(
            name="System Safety Assessment (FMEA)",
            description=(
                "Links each failure mode to its root causes and the "
                "requirements it challenges."
            ),
            columns=[
                {
                    "label": "Failure Mode",
                    "seed_item_type_slug": "failure-mode",
                    "seed_container": ssa,
                },
                {
                    "label": "Caused By",
                    "relation_name": "causes",
                    "direction": MatrixColumn.Direction.INCOMING,
                },
                {
                    "label": "Challenged Requirements",
                    "relation_name": "mitigates",
                    "direction": MatrixColumn.Direction.OUTGOING,
                },
            ],
        )

        # 5. Risk Assessment
        self._matrix(
            name="Safety Risk Assessment",
            description=(
                "Shows each safety risk and the requirements it "
                "challenges, for risk acceptability review."
            ),
            columns=[
                {
                    "label": "Risk",
                    "seed_item_type_slug": "risk",
                    "seed_container": safety_assessment_report,
                },
                {
                    "label": "Challenged Requirements",
                    "relation_name": "mitigates",
                    "direction": MatrixColumn.Direction.OUTGOING,
                },
            ],
        )

        # 6. DO-326A Threat Assessment
        self._matrix(
            name="DO-326A Threat Assessment",
            description=(
                "Links each security threat to the vulnerabilities it "
                "exploits and the mitigations applied."
            ),
            columns=[
                {
                    "label": "Threat",
                    "seed_item_type_slug": "threat",
                    "seed_container": tara,
                },
                {
                    "label": "Exploited Vulnerabilities",
                    "relation_name": "exploits",
                    "direction": MatrixColumn.Direction.OUTGOING,
                },
                {
                    "label": "Mitigations",
                    "relation_name": "mitigates",
                    "direction": MatrixColumn.Direction.INCOMING,
                },
            ],
        )

        # 7. Requirement Decomposition
        self._matrix(
            name="Requirement Decomposition Matrix",
            description=(
                "Shows how system requirements are decomposed into "
                "lower-level sub-requirements."
            ),
            columns=[
                {
                    "label": "System Requirement",
                    "seed_item_type_slug": "requirement",
                    "seed_container": sys_req_spec,
                },
                {
                    "label": "Refined By",
                    "relation_name": "refines",
                    "direction": MatrixColumn.Direction.OUTGOING,
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixColumn.Direction.INCOMING,
                },
            ],
        )
