"""
Management command: populate_example

Wipes example vaults (if they exist), then populates six realistic examples:

1. **AV System** — an Autonomous Vehicle System organised around document
   deliverables: plans, specifications, FMEA analyses, risk assessments,
   and verification & validation reports.

2. **Avionics FMS** — a Flight Management System development programme
   following DO-178C, ARP4754A, and ARP4761, including system & software
   requirements, functional hazard assessment, FMEA, verification, and
   DO-326A security assessment.

3. **Medical Device** — an Implantable Cardiac Pacemaker development
   programme following IEC 62304 (software lifecycle), ISO 14971 (risk
   management), IEC 60601-1 (general safety), and EU MDR / FDA 21 CFR 820,
   with emphasis on patient safety, biocompatibility, and cybersecurity.

4. **Financial Risk Management** — a Trading Risk Platform for an investment
   bank covering market risk, credit risk, operational risk, and model
   validation following Basel III/IV, FRTB, BCBS 239, MiFID II, and
   Dodd-Frank.

5. **DoD RFP Response** — a defence-contractor pursuit of a $250M
   Next-Gen Command & Control (NGCC) contract, with RFP requirements,
   proposal volumes, compliance matrix, past performance citations,
   competitive analysis, and color-team gate reviews.

6. **Enterprise Software Deal** — a SaaS analytics company pursuing a
   $2.4M ARR deal with a global bank, tracking customer requirements,
   solution mapping, POC scenarios, security questionnaire, stakeholder
   management, and competitive positioning.

R&D vaults (1–4) share a common schema (Project, Plan, Requirement, etc.).
Sales vaults (5–6) each have their own domain-specific schemas.

Usage:
    python manage.py populate_example
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.items.models import CustomFieldDefinition, CustomFieldValue, DocumentTemplate, Item, ItemType
from apps.matrices.models import Matrix, MatrixDisplayColumn, MatrixSource
from apps.relations.models import ItemRelation, RelationType
from apps.vaults.models import Vault, VaultAuditLog, VaultMembership

User = get_user_model()


class Command(BaseCommand):
    help = "Populate example vaults (AV System + Avionics FMS + Medical Device + Financial Risk + DoD RFP + Enterprise Deal)"

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

    # -- Sales-domain shorthand helpers ------------------------------------

    def _responds_to(self, section, *requirements):
        for req in requirements:
            self._rel("responds_to", section, req)

    def _demonstrates(self, scenario, *requirements):
        for req in requirements:
            self._rel("demonstrates", scenario, req)

    def _evidenced_by(self, response, *citations):
        for cite in citations:
            self._rel("evidenced_by", response, cite)

    def _counters(self, source, *targets):
        for t in targets:
            self._rel("counters", source, t)

    def _prices(self, element, *requirements):
        for req in requirements:
            self._rel("prices", element, req)

    def _clarifies(self, question, *requirements):
        for req in requirements:
            self._rel("clarifies", question, req)

    def _addresses(self, component, *requirements):
        for req in requirements:
            self._rel("addresses", component, req)

    def _validates(self, scenario, *requirements):
        for req in requirements:
            self._rel("validates", scenario, req)

    def _answers(self, response, *requirements):
        for req in requirements:
            self._rel("answers", response, req)

    def _competes_with(self, competitor, *components):
        for comp in components:
            self._rel("competes_with", competitor, comp)

    def _influences(self, stakeholder, *requirements):
        for req in requirements:
            self._rel("influences", stakeholder, req)

    def _covers(self, section, *requirements):
        for req in requirements:
            self._rel("covers", section, req)

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
            label = col["label"]
            # Generate a slug name from the label
            name = label.lower().replace(" ", "-").replace("_", "-")
            # Ensure uniqueness by appending position if needed
            if position == 0:
                MatrixSource.objects.create(
                    matrix=matrix,
                    name=name,
                    position=0,
                    kind=MatrixSource.Kind.SEED,
                    seed_item_type=self._types[col["seed_item_type_slug"]],
                    seed_container=col.get("seed_container"),
                )
            else:
                MatrixSource.objects.create(
                    matrix=matrix,
                    name=name,
                    position=position,
                    kind=MatrixSource.Kind.TRAVERSAL,
                    relation_type=self._relations[col["relation_name"]],
                    direction=col["direction"],
                )
            MatrixDisplayColumn.objects.create(
                matrix=matrix,
                position=position,
                heading=label,
                source_name=name,
            )
        return matrix

    # ------------------------------------------------------------------
    # Vault lifecycle helpers
    # ------------------------------------------------------------------

    def _wipe_vault(self, slug):
        """Wipe a single vault and all its data (if it exists)."""
        from apps.items.models import ItemTableAnnotation, ItemVersion
        from apps.agent.models import Conversation, Message, PendingAction
        from apps.mailbox.models import MailboxArtifact
        from apps.matrices.models import MatrixAnnotation

        old_vault = Vault.all_objects.filter(slug=slug).first()
        if old_vault:
            self.stdout.write(f"Wiping vault '{old_vault.name}'...")
            vault_types = ItemType.all_objects.filter(vault=old_vault)
            vault_items = Item.all_objects.filter(item_type__vault=old_vault)
            vault_field_defs = CustomFieldDefinition.all_objects.filter(item_type__vault=old_vault)
            vault_conversations = Conversation.all_objects.filter(vault=old_vault)

            PendingAction.all_objects.filter(conversation__in=vault_conversations).hard_delete()
            Message.all_objects.filter(conversation__in=vault_conversations).hard_delete()
            vault_conversations.hard_delete()
            MatrixAnnotation.all_objects.filter(matrix__vault=old_vault).hard_delete()
            MatrixDisplayColumn.all_objects.filter(matrix__vault=old_vault).hard_delete()
            MatrixSource.all_objects.filter(matrix__vault=old_vault).hard_delete()
            Matrix.all_objects.filter(vault=old_vault).hard_delete()
            ItemRelation.all_objects.filter(relation_type__vault=old_vault).hard_delete()
            ItemTableAnnotation.all_objects.filter(item__in=vault_items).hard_delete()
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
    MEDICAL_VAULT_SLUG = "medical-device"
    FINANCE_VAULT_SLUG = "finance-risk"
    DOD_VAULT_SLUG = "dod-rfp"
    ENTERPRISE_VAULT_SLUG = "enterprise-deal"

    @transaction.atomic
    def handle(self, *args, **options):
        # Wipe example vaults
        self._wipe_vault(self.AV_VAULT_SLUG)
        self._wipe_vault(self.AVIONICS_VAULT_SLUG)
        self._wipe_vault(self.MEDICAL_VAULT_SLUG)
        self._wipe_vault(self.FINANCE_VAULT_SLUG)
        self._wipe_vault(self.DOD_VAULT_SLUG)
        self._wipe_vault(self.ENTERPRISE_VAULT_SLUG)

        # Require an existing site admin — never create one here.
        admin = User.objects.filter(is_site_admin=True).first()
        if not admin:
            raise SystemExit(
                "No site-admin account found. Complete the initial setup at /setup "
                "before running populate_example."
            )

        # Create demo author (shared across vaults)
        User.objects.filter(username="demo").delete()
        self._author = User.objects.create_user(
            username="demo",
            email="demo@example.com",
            password="DEMOdemo123!",
        )
        self.stdout.write(f"  Using site admin: {admin.username}")
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

        # ==============================================================
        # VAULT 3 — Medical Device (Cardiac Pacemaker)
        # ==============================================================
        self.stdout.write(self.style.MIGRATE_HEADING("\nSetting up Medical Device vault..."))

        self._vault = Vault.objects.create(
            name="Cardiac Pacemaker",
            slug=self.MEDICAL_VAULT_SLUG,
            description=(
                "Implantable Cardiac Pacemaker development programme following "
                "IEC 62304, ISO 14971, IEC 60601-1, and EU MDR / FDA 21 CFR 820."
            ),
            created_by=admin,
        )
        VaultMembership.objects.create(vault=self._vault, user=admin, role="admin")
        VaultMembership.objects.create(vault=self._vault, user=self._author, role="editor")

        self._setup_vault_schema(admin)

        self.stdout.write("Building Medical Device document-deliverable example...")
        self._build_medical()
        self.stdout.write(self.style.SUCCESS("  Medical Device vault complete."))

        # ==============================================================
        # VAULT 4 — Financial Risk Management
        # ==============================================================
        self.stdout.write(self.style.MIGRATE_HEADING("\nSetting up Financial Risk Management vault..."))

        self._vault = Vault.objects.create(
            name="Trading Risk Platform",
            slug=self.FINANCE_VAULT_SLUG,
            description=(
                "Market-making and proprietary trading risk management platform "
                "following Basel III/IV, FRTB, BCBS 239, MiFID II, and Dodd-Frank. "
                "Covers market risk, credit risk, operational risk, and model validation."
            ),
            created_by=admin,
        )
        VaultMembership.objects.create(vault=self._vault, user=admin, role="admin")
        VaultMembership.objects.create(vault=self._vault, user=self._author, role="editor")

        self._setup_vault_schema(admin)

        self.stdout.write("Building Financial Risk Management example...")
        self._build_finance()
        self.stdout.write(self.style.SUCCESS("  Financial Risk Management vault complete."))

        # ==============================================================
        # VAULT 5 — DoD RFP Response
        # ==============================================================
        self.stdout.write(self.style.MIGRATE_HEADING("\nSetting up DoD RFP Response vault..."))

        self._vault = Vault.objects.create(
            name="NGCC Pursuit",
            slug=self.DOD_VAULT_SLUG,
            description=(
                "Next-Gen Command & Control (NGCC) $250M DoD contract pursuit — "
                "RFP requirements, proposal volumes, compliance matrix, past performance, "
                "competitive analysis, and color-team gate reviews."
            ),
            created_by=admin,
        )
        VaultMembership.objects.create(vault=self._vault, user=admin, role="admin")
        VaultMembership.objects.create(vault=self._vault, user=self._author, role="editor")

        self._setup_dod_sales_schema(admin)

        self.stdout.write("Building DoD RFP Response example...")
        self._build_dod_rfp()
        self.stdout.write(self.style.SUCCESS("  DoD RFP Response vault complete."))

        # ==============================================================
        # VAULT 6 — Enterprise Software Deal
        # ==============================================================
        self.stdout.write(self.style.MIGRATE_HEADING("\nSetting up Enterprise Software Deal vault..."))

        self._vault = Vault.objects.create(
            name="Meridian Analytics Deal",
            slug=self.ENTERPRISE_VAULT_SLUG,
            description=(
                "Meridian Analytics $2.4M ARR enterprise deal with Global Trust Bank — "
                "customer requirements, solution mapping, POC scenarios, security "
                "questionnaire, stakeholder management, and competitive positioning."
            ),
            created_by=admin,
        )
        VaultMembership.objects.create(vault=self._vault, user=admin, role="admin")
        VaultMembership.objects.create(vault=self._vault, user=self._author, role="editor")

        self._setup_enterprise_sales_schema(admin)

        self.stdout.write("Building Enterprise Software Deal example...")
        self._build_enterprise_deal()
        self.stdout.write(self.style.SUCCESS("  Enterprise Software Deal vault complete."))

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
                    "direction": MatrixSource.Direction.INCOMING,
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
                    "direction": MatrixSource.Direction.INCOMING,
                },
                {
                    "label": "Derives From",
                    "relation_name": "derives_from",
                    "direction": MatrixSource.Direction.OUTGOING,
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
                    "direction": MatrixSource.Direction.INCOMING,
                },
                {
                    "label": "Challenged Requirements",
                    "relation_name": "mitigates",
                    "direction": MatrixSource.Direction.OUTGOING,
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
                    "direction": MatrixSource.Direction.INCOMING,
                },
                {
                    "label": "Threatened Requirements",
                    "relation_name": "mitigates",
                    "direction": MatrixSource.Direction.OUTGOING,
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
                    "direction": MatrixSource.Direction.OUTGOING,
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
                    "direction": MatrixSource.Direction.OUTGOING,
                },
                {
                    "label": "Mitigations",
                    "relation_name": "mitigates",
                    "direction": MatrixSource.Direction.INCOMING,
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
                    "direction": MatrixSource.Direction.OUTGOING,
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixSource.Direction.INCOMING,
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
                    "direction": MatrixSource.Direction.INCOMING,
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
                    "direction": MatrixSource.Direction.INCOMING,
                },
                {
                    "label": "Derives From",
                    "relation_name": "derives_from",
                    "direction": MatrixSource.Direction.OUTGOING,
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
                    "direction": MatrixSource.Direction.INCOMING,
                },
                {
                    "label": "Derives From",
                    "relation_name": "derives_from",
                    "direction": MatrixSource.Direction.OUTGOING,
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
                    "direction": MatrixSource.Direction.INCOMING,
                },
                {
                    "label": "Challenged Requirements",
                    "relation_name": "mitigates",
                    "direction": MatrixSource.Direction.OUTGOING,
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
                    "direction": MatrixSource.Direction.OUTGOING,
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
                    "direction": MatrixSource.Direction.OUTGOING,
                },
                {
                    "label": "Mitigations",
                    "relation_name": "mitigates",
                    "direction": MatrixSource.Direction.INCOMING,
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
                    "direction": MatrixSource.Direction.OUTGOING,
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

    # ------------------------------------------------------------------
    # Medical Device (Cardiac Pacemaker) example data
    # ------------------------------------------------------------------

    def _build_medical(self):
        # ==============================================================
        # TOP-LEVEL PROGRAMME
        # ==============================================================
        programme = self._item(
            "project",
            "PM-500 Implantable Cardiac Pacemaker",
            "Top-level programme for the PM-500 dual-chamber implantable "
            "cardiac pacemaker. Class III medical device (EU MDR Rule 8, "
            "FDA Class III PMA). Encompasses all design control deliverables "
            "from user needs through design validation.",
            **{"standard-reference": "IEC 62304, ISO 14971, IEC 60601-1, EU MDR 2017/745, FDA 21 CFR 820"},
        )

        # ==============================================================
        # PLANS
        # ==============================================================
        dev_plan = self._item(
            "plan",
            "Design and Development Plan",
            "Defines the design control process for the PM-500 pacemaker "
            "per FDA 21 CFR 820.30 and EU MDR Annex II. Covers design "
            "input, output, review, verification, validation, and transfer.",
            **{"phase": "Approved",
               "standard-reference": "FDA 21 CFR 820.30, ISO 13485:2016 §7.3"},
        )
        dev_plan_purpose = self._item(
            "information",
            "Purpose",
            "This plan establishes the design control procedures for the PM-500 "
            "implantable cardiac pacemaker. It ensures systematic translation of "
            "user needs into verified and validated design outputs, with full "
            "traceability throughout the product lifecycle.",
        )
        dev_plan_scope = self._item(
            "information",
            "Scope",
            "Covers the pulse generator hardware, embedded firmware (IEC 62304 "
            "Class C software), lead interface, telemetry subsystem, and "
            "programmer/interrogator interface. Excludes the implantable lead "
            "itself (covered under a separate design history file).",
        )
        dev_plan_standards = self._item(
            "information",
            "Applicable Standards",
            "IEC 62304:2006+A1:2015 (software lifecycle), ISO 14971:2019 (risk "
            "management), IEC 60601-1:2005+A2:2020 (general safety), "
            "IEC 60601-1-2 (EMC), ISO 14708-2 (implantable pacemakers), "
            "AAMI TIR57 (cybersecurity), FDA guidance on premarket submissions.",
        )
        dev_plan_lifecycle = self._item(
            "information",
            "Development Lifecycle",
            "The PM-500 follows a V-model lifecycle: user needs → design input → "
            "system architecture → subsystem design → implementation → unit test → "
            "integration test → system verification → design validation. Each "
            "phase requires formal design review before proceeding.",
        )
        self._compose(dev_plan, dev_plan_purpose, dev_plan_scope, dev_plan_standards, dev_plan_lifecycle)

        risk_plan = self._item(
            "plan",
            "Risk Management Plan",
            "Defines the risk management process per ISO 14971:2019 for the PM-500. "
            "Covers hazard identification, risk estimation, risk evaluation, risk "
            "control, and residual risk evaluation. Risk acceptability criteria "
            "follow the ALARP principle with absolute limits for patient safety.",
            **{"phase": "Approved",
               "standard-reference": "ISO 14971:2019, IEC 60601-1 §4"},
        )
        risk_plan_criteria = self._item(
            "information",
            "Risk Acceptability Criteria",
            "Risks are evaluated on a 5×5 severity/probability matrix. For patient "
            "safety hazards: catastrophic (death) or critical (permanent injury) risks "
            "must be reduced to ALARP with probability ≤ 10⁻⁶ per hour. Risks that "
            "cannot meet this threshold require explicit benefit-risk justification "
            "per ISO 14971 §7.",
        )
        risk_plan_process = self._item(
            "information",
            "Risk Analysis Process",
            "Systematic hazard identification using FTA, FMEA, and HAZOP. Each "
            "identified hazard is traced to its root cause, evaluated for severity "
            "and probability, and linked to risk control measures. Residual risk "
            "is re-evaluated after control implementation.",
        )
        self._compose(risk_plan, risk_plan_criteria, risk_plan_process)

        sw_plan = self._item(
            "plan",
            "Software Development Plan",
            "Defines the software development lifecycle for PM-500 firmware per "
            "IEC 62304:2006+A1:2015. Software safety classification: Class C "
            "(can contribute to a hazardous situation resulting in death or "
            "serious injury). Covers all software development activities, "
            "configuration management, and problem resolution.",
            **{"phase": "Approved",
               "standard-reference": "IEC 62304:2006+A1:2015"},
        )
        sw_plan_class = self._item(
            "information",
            "Software Safety Classification",
            "The PM-500 firmware is classified as IEC 62304 Class C (highest safety "
            "class). This classification applies because: (1) the software directly "
            "controls therapeutic pacing pulses, (2) failure to pace can result in "
            "death, and (3) no independent hardware mechanism can fully mitigate "
            "software failure modes.",
        )
        sw_plan_architecture = self._item(
            "information",
            "Software Architecture Overview",
            "Three-layer architecture: (1) Hardware Abstraction Layer — ADC, timers, "
            "telemetry radio; (2) Real-Time Kernel — deterministic scheduler with "
            "worst-case execution time analysis; (3) Therapy Layer — sensing, "
            "arrhythmia detection, pacing algorithms, and rate-response. Strict "
            "memory partitioning between safety-critical and non-critical modules.",
        )
        sw_plan_tools = self._item(
            "information",
            "Development Tools and Qualification",
            "Compiler: ARM GCC (qualified per IEC 62304 §8.1.2). Static analysis: "
            "Polyspace, MISRA C:2012 compliance. Unit test framework: qualified test "
            "harness with 100% MC/DC coverage for Class C modules. SOUP: FreeRTOS "
            "(qualified per IEC 62304 §8.1.2), BLE stack (assessed for anomalies).",
        )
        self._compose(sw_plan, sw_plan_class, sw_plan_architecture, sw_plan_tools)

        ver_plan = self._item(
            "plan",
            "Verification Plan",
            "Defines the verification strategy for PM-500 design outputs. "
            "Verification demonstrates that design outputs meet design inputs "
            "under controlled conditions. Includes bench testing, software "
            "testing, EMC testing, and accelerated life testing.",
            **{"phase": "Approved",
               "standard-reference": "FDA 21 CFR 820.30(f), IEC 60601-1"},
        )
        ver_plan_methods = self._item(
            "information",
            "Verification Methods",
            "Test: Objective evidence from bench or automated testing. "
            "Analysis: Mathematical or simulation-based demonstration. "
            "Inspection: Visual or dimensional examination. "
            "Demonstration: Functional operation under nominal conditions. "
            "Each design input specifies its required verification method.",
        )
        self._compose(ver_plan, ver_plan_methods)

        val_plan = self._item(
            "plan",
            "Validation Plan",
            "Defines design validation to confirm the PM-500 meets user needs "
            "and intended use under actual or simulated use conditions. Includes "
            "pre-clinical bench testing, animal studies (ovine model), and "
            "clinical investigation (IDE).",
            **{"phase": "Approved",
               "standard-reference": "FDA 21 CFR 820.30(g), EU MDR Annex XV"},
        )
        val_plan_clinical = self._item(
            "information",
            "Clinical Investigation Strategy",
            "Multi-centre, prospective, non-randomised clinical study in 500 "
            "patients with bradycardia requiring dual-chamber pacing. Primary "
            "endpoints: pacing capture threshold stability (6 months), freedom "
            "from system-related serious adverse events. Study conducted under "
            "FDA IDE and EU MDR Article 62.",
        )
        self._compose(val_plan, val_plan_clinical)

        cybersec_plan = self._item(
            "plan",
            "Cybersecurity Plan",
            "Defines the cybersecurity risk management process for the PM-500 "
            "per AAMI TIR57 and FDA premarket cybersecurity guidance. Covers "
            "threat modelling, security requirements, penetration testing, "
            "and post-market vulnerability management.",
            **{"phase": "Approved",
               "standard-reference": "AAMI TIR57:2016, FDA Cybersecurity Guidance 2023"},
        )
        cybersec_plan_threat_model = self._item(
            "information",
            "Threat Modelling Approach",
            "STRIDE-based threat modelling applied to all external interfaces: "
            "RF telemetry (proprietary near-field), BLE (programmer link), and "
            "remote monitoring uplink. Attack surface analysis considers the "
            "implanted device, the clinical programmer, and the home monitor.",
        )
        self._compose(cybersec_plan, cybersec_plan_threat_model)

        # ==============================================================
        # TOP-LEVEL SECTIONS (Design History File structure)
        # ==============================================================
        section_plans = self._item(
            "project",
            "Planning",
            "All planning documents for the PM-500 design control process: "
            "development plan, risk management plan, software lifecycle plan, "
            "verification plan, validation plan, and cybersecurity plan.",
        )
        section_design_input = self._item(
            "project",
            "Design Input",
            "User needs and design input specifications that define what the "
            "PM-500 must do. Covers system, software, hardware, cybersecurity, "
            "and biocompatibility requirements per FDA 21 CFR 820.30(c).",
        )
        section_risk = self._item(
            "project",
            "Risk Management",
            "ISO 14971 risk management documentation: risk management file, "
            "failure mode analyses (hardware FMEA, software FMEA, use-related "
            "FMEA), and fault tree analysis.",
        )
        section_verification = self._item(
            "project",
            "Design Verification",
            "Design verification evidence demonstrating that design outputs "
            "meet design inputs under controlled conditions per "
            "FDA 21 CFR 820.30(f).",
        )
        section_validation = self._item(
            "project",
            "Design Validation",
            "Design validation evidence confirming the PM-500 meets user needs "
            "and intended use under actual or simulated conditions per "
            "FDA 21 CFR 820.30(g). Includes pre-clinical and clinical data.",
        )
        section_cybersecurity = self._item(
            "project",
            "Cybersecurity",
            "Cybersecurity risk management per AAMI TIR57 and FDA premarket "
            "cybersecurity guidance: threat assessment, vulnerability analysis, "
            "and security controls.",
        )

        self._compose(programme, section_plans, section_design_input,
                       section_risk, section_verification, section_validation,
                       section_cybersecurity)

        # -- Plans under Planning section --
        self._compose(section_plans, dev_plan, risk_plan, sw_plan, ver_plan,
                       val_plan, cybersec_plan)

        # ==============================================================
        # SPECIFICATIONS (under Design Input)
        # ==============================================================
        user_needs = self._item(
            "specification",
            "User Needs Document",
            "Captures the needs of intended users (cardiologists, EP specialists, "
            "patients) and the clinical context of use for the PM-500 dual-chamber "
            "pacemaker. These form the basis for all design inputs.",
            **{"standard-reference": "FDA 21 CFR 820.30(c), EU MDR Annex I §1",
               "baseline": "1.0"},
        )

        sys_req_spec = self._item(
            "specification",
            "System Requirements Specification",
            "Top-level design inputs for the PM-500 pulse generator, derived from "
            "user needs and regulatory requirements. Covers functional, performance, "
            "safety, biocompatibility, and EMC requirements.",
            **{"standard-reference": "IEC 60601-1, ISO 14708-2",
               "baseline": "2.1"},
        )

        sw_req_spec = self._item(
            "specification",
            "Software Requirements Specification",
            "Software-level requirements for PM-500 firmware derived from the "
            "system requirements specification. Covers all IEC 62304 Class C "
            "software items: sensing, pacing, arrhythmia detection, telemetry, "
            "and diagnostics.",
            **{"standard-reference": "IEC 62304:2006+A1:2015 §5.2",
               "baseline": "3.0"},
        )

        hw_req_spec = self._item(
            "specification",
            "Hardware Requirements Specification",
            "Hardware design inputs for the PM-500 pulse generator: output stage, "
            "sensing amplifiers, microcontroller, power management, telemetry "
            "radio, hermetic enclosure, and header/connector.",
            **{"standard-reference": "IEC 60601-1, ISO 14708-2",
               "baseline": "1.2"},
        )

        cybersec_req_spec = self._item(
            "specification",
            "Cybersecurity Requirements Specification",
            "Security design inputs for the PM-500 covering authentication, "
            "encryption, integrity verification, access control, and "
            "software update mechanisms.",
            **{"standard-reference": "AAMI TIR57, FDA Cybersecurity Guidance",
               "baseline": "1.0"},
        )

        biocompat_spec = self._item(
            "specification",
            "Biocompatibility Evaluation Plan",
            "Defines the biological safety evaluation strategy per ISO 10993-1 "
            "for all patient-contacting materials: titanium enclosure, epoxy "
            "header, silicone seal, and connector contacts.",
            **{"standard-reference": "ISO 10993-1:2018",
               "baseline": "1.0"},
        )

        self._compose(section_design_input, user_needs, sys_req_spec, sw_req_spec,
                       hw_req_spec, cybersec_req_spec, biocompat_spec)

        # ==============================================================
        # RISK MANAGEMENT (under Risk Management section)
        # ==============================================================
        risk_mgmt_file = self._item(
            "report",
            "Risk Management File",
            "Comprehensive risk management documentation per ISO 14971:2019 "
            "including hazard analysis, risk estimation, risk evaluation, "
            "risk control records, and residual risk evaluation.",
            **{"report-status": "Draft"},
        )

        hw_fmea = self._item(
            "analysis",
            "Hardware FMEA — Pulse Generator",
            "Failure Mode and Effects Analysis for the PM-500 pulse generator "
            "hardware: output stage, sensing front-end, power supply, "
            "microcontroller, and telemetry subsystem.",
            **{"method": "FMEA",
               "standard-reference": "IEC 60812, ISO 14971"},
        )
        sw_fmea = self._item(
            "analysis",
            "Software FMEA — Firmware",
            "Failure Mode and Effects Analysis for PM-500 firmware modules: "
            "sensing algorithm, pacing engine, arrhythmia detection, "
            "rate-response, telemetry protocol, and diagnostics.",
            **{"method": "FMEA",
               "standard-reference": "IEC 60812, IEC 62304"},
        )
        fta_pacing = self._item(
            "analysis",
            "Fault Tree Analysis — Loss of Pacing",
            "Top-level undesired event: complete loss of therapeutic pacing. "
            "Analyses all single-point and common-cause failures that could "
            "lead to pacing cessation in a pacemaker-dependent patient.",
            **{"method": "FTA",
               "standard-reference": "IEC 61025, ISO 14971"},
        )
        use_fmea = self._item(
            "analysis",
            "Use-Related FMEA",
            "Analysis of use errors during implantation, programming, and "
            "follow-up that could lead to patient harm. Covers the clinical "
            "programmer interface and home monitoring setup.",
            **{"method": "FMEA",
               "standard-reference": "IEC 62366-1:2015, ISO 14971"},
        )

        self._compose(section_risk, risk_mgmt_file, hw_fmea, sw_fmea,
                       fta_pacing, use_fmea)

        # ==============================================================
        # DESIGN VERIFICATION (under Verification section)
        # ==============================================================
        ver_report = self._item(
            "report",
            "Verification Report",
            "Consolidated results from all verification activities: bench "
            "testing, software testing, EMC testing, electrical safety testing, "
            "and accelerated life testing.",
            **{"report-status": "Draft"},
        )
        sw_test_report = self._item(
            "report",
            "Software Test Report",
            "Consolidated software verification results per IEC 62304. "
            "Unit test, integration test, and system test results with "
            "coverage metrics (100% MC/DC for Class C modules).",
            **{"report-status": "Draft"},
        )

        self._compose(section_verification, ver_report, sw_test_report)

        # ==============================================================
        # DESIGN VALIDATION (under Validation section)
        # ==============================================================
        val_report = self._item(
            "report",
            "Validation Report",
            "Results from design validation including pre-clinical bench testing, "
            "animal study results, and clinical investigation data.",
            **{"report-status": "Draft"},
        )
        biocompat_report = self._item(
            "report",
            "Biocompatibility Test Report",
            "Results of ISO 10993 biological evaluation: cytotoxicity, "
            "sensitisation, irritation, systemic toxicity, genotoxicity, "
            "implantation, and chronic toxicity studies.",
            **{"report-status": "Draft"},
        )

        self._compose(section_validation, val_report, biocompat_report)

        # ==============================================================
        # CYBERSECURITY (under Cybersecurity section)
        # ==============================================================
        threat_assessment = self._item(
            "analysis",
            "Cybersecurity Threat Assessment",
            "STRIDE-based threat assessment for the PM-500 communication "
            "interfaces: near-field RF telemetry, BLE programmer link, "
            "and remote monitoring uplink.",
            **{"method": "Other",
               "standard-reference": "AAMI TIR57, IEC 81001-5-1"},
        )

        self._compose(section_cybersecurity, threat_assessment)

        # ==============================================================
        # SYSTEM-LEVEL REQUIREMENTS (in sys_req_spec)
        # ==============================================================
        req_pacing_output = self._item(
            "requirement",
            "Pacing Output Range",
            "The pulse generator shall deliver pacing pulses with amplitude "
            "0.25 V to 7.5 V and pulse width 0.1 ms to 1.5 ms, independently "
            "configurable for atrial and ventricular channels.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_sensing = self._item(
            "requirement",
            "Sensing Sensitivity",
            "The device shall sense intrinsic cardiac signals with configurable "
            "sensitivity: atrial 0.25 mV to 4.0 mV, ventricular 1.0 mV to "
            "12.0 mV. Sensing must reject T-waves and far-field signals.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_battery_life = self._item(
            "requirement",
            "Battery Longevity",
            "The device shall provide a minimum of 10 years of operation at "
            "nominal settings (dual-chamber DDD mode, 60 bpm base rate, "
            "2.5 V output, 0.4 ms pulse width, 500 Ω impedance).",
            **{"priority": "Critical",
               "verification-method": "Analysis"},
        )
        req_eri = self._item(
            "requirement",
            "Elective Replacement Indicator",
            "The device shall provide an Elective Replacement Indicator (ERI) "
            "when remaining battery capacity falls below a threshold ensuring "
            "≥ 6 months of continued operation at programmed settings. The "
            "device shall switch to VVI backup pacing at End of Service (EOS).",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_rate_response = self._item(
            "requirement",
            "Rate-Responsive Pacing",
            "The device shall support rate-responsive pacing (DDDR mode) "
            "using an accelerometer-based activity sensor, with programmable "
            "lower rate 40–100 bpm and upper sensor rate 100–180 bpm.",
            **{"priority": "High",
               "verification-method": "Test"},
        )
        req_emc = self._item(
            "requirement",
            "Electromagnetic Compatibility",
            "The device shall maintain safe operation when exposed to "
            "electromagnetic fields per IEC 60601-1-2. The device shall not "
            "deliver inappropriate therapy or inhibit required pacing during "
            "EMI exposure up to specified immunity levels.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_mri_conditional = self._item(
            "requirement",
            "MRI Conditional Labelling",
            "The device shall support an MRI-conditional mode that, when "
            "programmed prior to MR scan, ensures patient safety during "
            "1.5 T and 3.0 T MRI under specified conditions (SAR limits, "
            "gradient slew rate). Pacing shall revert to asynchronous mode "
            "to prevent inhibition from MRI-induced signals.",
            **{"priority": "High",
               "verification-method": "Test"},
        )
        req_hermeticity = self._item(
            "requirement",
            "Hermetic Seal Integrity",
            "The titanium enclosure shall maintain hermeticity with a helium "
            "leak rate ≤ 1 × 10⁻⁹ atm·cc/sec throughout the device lifetime. "
            "The header-case seal shall withstand implant stresses without "
            "degradation.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_biocompat = self._item(
            "requirement",
            "Biocompatibility",
            "All patient-contacting materials (titanium case, epoxy header, "
            "silicone seals, connector contacts) shall be biocompatible per "
            "ISO 10993-1 for long-term implantation (> 30 days). Materials "
            "shall not elicit cytotoxic, sensitising, or irritating responses.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_defibrillation = self._item(
            "requirement",
            "Defibrillation Protection",
            "The device shall withstand external defibrillation shocks up to "
            "360 J (monophasic) and 200 J (biphasic) without permanent damage "
            "to the pulse generator. The device shall resume programmed "
            "operation within 5 seconds after defibrillation.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )

        self._compose(sys_req_spec, req_pacing_output, req_sensing, req_battery_life,
                       req_eri, req_rate_response, req_emc, req_mri_conditional,
                       req_hermeticity, req_biocompat, req_defibrillation)

        # ==============================================================
        # SOFTWARE REQUIREMENTS (in sw_req_spec)
        # ==============================================================
        req_sw_sensing_algo = self._item(
            "requirement",
            "Cardiac Signal Sensing Algorithm",
            "The firmware shall implement digital bandpass filtering (10–100 Hz) "
            "and adaptive threshold sensing with automatic sensitivity adjustment. "
            "The algorithm shall correctly classify ≥ 99.5% of intrinsic events "
            "and reject ≥ 99% of far-field and noise artefacts.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_sw_pacing_engine = self._item(
            "requirement",
            "Pacing Timing Engine",
            "The firmware shall implement DDD/DDDR timing cycles with "
            "programmable AV delay (50–300 ms), PVARP (150–500 ms), and "
            "ventricular blanking (15–100 ms). Timing precision shall be "
            "≤ 1 ms for all intervals.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_sw_arrhythmia = self._item(
            "requirement",
            "Mode Switch on Atrial Tachyarrhythmia",
            "The firmware shall detect sustained atrial tachyarrhythmia "
            "(rate > programmable threshold, default 180 bpm, for > N "
            "consecutive beats) and automatically switch to DDIR/VVIR "
            "mode to prevent tracking. Mode switch shall occur within "
            "≤ 2 seconds of detection.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_sw_diagnostics = self._item(
            "requirement",
            "Diagnostic Data Logging",
            "The firmware shall record pacing/sensing event histograms, "
            "lead impedance trends, battery voltage trends, arrhythmia "
            "episodes (with stored EGMs), and mode switch events. Minimum "
            "storage: 60 episodes with 10 seconds of EGM each.",
            **{"priority": "High",
               "verification-method": "Test"},
        )
        req_sw_telemetry = self._item(
            "requirement",
            "Telemetry Communication Protocol",
            "The firmware shall support bidirectional telemetry at ≥ 200 kbps "
            "for programming and interrogation sessions. Communication shall "
            "use authenticated and encrypted links per the cybersecurity "
            "requirements. Telemetry range: 5–10 cm (near-field).",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_sw_watchdog = self._item(
            "requirement",
            "Safety Watchdog and Backup Pacing",
            "The firmware shall implement an independent hardware watchdog timer "
            "with a ≤ 1.5 second timeout. If the main therapy task fails to "
            "service the watchdog, the system shall revert to VVI backup pacing "
            "at 70 bpm with fixed 5.0 V output within ≤ 2 seconds.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )

        self._compose(sw_req_spec, req_sw_sensing_algo, req_sw_pacing_engine,
                       req_sw_arrhythmia, req_sw_diagnostics, req_sw_telemetry,
                       req_sw_watchdog)

        # Derive software reqs from system reqs
        self._derives(req_sw_sensing_algo, req_sensing)
        self._derives(req_sw_pacing_engine, req_pacing_output)
        self._derives(req_sw_arrhythmia, req_sensing)
        self._derives(req_sw_telemetry, req_pacing_output)
        self._derives(req_sw_watchdog, req_pacing_output)

        # ==============================================================
        # CYBERSECURITY REQUIREMENTS (in cybersec_req_spec)
        # ==============================================================
        req_sec_auth = self._item(
            "requirement",
            "Telemetry Authentication",
            "The device shall authenticate the clinical programmer before "
            "accepting any programming commands. Authentication shall use a "
            "challenge-response protocol with device-unique keys. Failed "
            "authentication attempts shall be logged.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_sec_encrypt = self._item(
            "requirement",
            "Telemetry Encryption",
            "All telemetry data containing patient health information or "
            "device parameters shall be encrypted using AES-128 or stronger. "
            "Key exchange shall use ECDH with NIST P-256 or equivalent.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_sec_integrity = self._item(
            "requirement",
            "Firmware Integrity Verification",
            "The device shall verify firmware integrity at boot using a "
            "cryptographic hash (SHA-256 minimum). If integrity verification "
            "fails, the device shall enter safe mode (VVI backup pacing) "
            "and log the failure.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_sec_update = self._item(
            "requirement",
            "Secure Firmware Update",
            "Firmware updates shall be digitally signed by the manufacturer. "
            "The device shall verify the signature before applying any update. "
            "Updates shall not interrupt ongoing therapy; the update process "
            "shall be atomic (complete or roll back).",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_sec_audit = self._item(
            "requirement",
            "Security Event Logging",
            "The device shall log security-relevant events including: "
            "authentication attempts (success/failure), programming session "
            "start/end, firmware update attempts, and integrity check failures. "
            "Logs shall be non-volatile and accessible during interrogation.",
            **{"priority": "High",
               "verification-method": "Test"},
        )

        self._compose(cybersec_req_spec, req_sec_auth, req_sec_encrypt,
                       req_sec_integrity, req_sec_update, req_sec_audit)

        # ==============================================================
        # REQUIREMENT DECOMPOSITION — Sensing
        # ==============================================================
        req_sense_filter = self._item(
            "requirement",
            "Bandpass Filter — 10 to 100 Hz",
            "The sensing front-end shall implement a digital bandpass filter "
            "with -3 dB corners at 10 Hz and 100 Hz (±10%) to reject "
            "baseline wander and high-frequency noise.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_sense_threshold = self._item(
            "requirement",
            "Adaptive Threshold — 75% Decay",
            "After each sensed event, the detection threshold shall decay "
            "from 75% of the measured amplitude with a programmable time "
            "constant (150–500 ms) to the programmed floor sensitivity.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_sense_refractory = self._item(
            "requirement",
            "Refractory Period — Noise Rejection",
            "A post-sense refractory period (programmable 100–400 ms) shall "
            "blank the sensing channel to prevent T-wave and after-potential "
            "oversensing.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        self._refines(req_sw_sensing_algo, req_sense_filter, req_sense_threshold, req_sense_refractory)

        # ==============================================================
        # FAILURE MODES — Hardware FMEA
        # ==============================================================
        fm_output_open = self._item(
            "failure-mode",
            "Output Stage Open Circuit",
            "Loss of pacing output due to open-circuit failure in the output "
            "capacitor or switching transistor. Patient impact: loss of pacing "
            "therapy — life-threatening for pacemaker-dependent patients.",
            **{"severity": "Critical"},
        )
        fm_output_short = self._item(
            "failure-mode",
            "Output Stage Short to Ground",
            "Continuous current drain through output stage short circuit. "
            "Results in rapid battery depletion and loss of therapy. May "
            "also cause tissue damage at the electrode-myocardium interface.",
            **{"severity": "Critical"},
        )
        fm_sensing_loss = self._item(
            "failure-mode",
            "Loss of Cardiac Sensing",
            "Failure to detect intrinsic cardiac activity due to amplifier "
            "failure or ADC malfunction. Results in asynchronous pacing with "
            "risk of R-on-T stimulation and ventricular fibrillation.",
            **{"severity": "Critical"},
        )
        fm_battery_premature = self._item(
            "failure-mode",
            "Premature Battery Depletion",
            "Battery reaches EOS earlier than predicted due to internal "
            "short, elevated self-discharge, or excessive current drain. "
            "Patient impact: unexpected loss of therapy.",
            **{"severity": "Critical"},
        )
        fm_telemetry_failure = self._item(
            "failure-mode",
            "Telemetry Communication Failure",
            "Inability to interrogate or programme the device due to RF "
            "front-end failure. Device continues pacing at last programmed "
            "settings but cannot be reprogrammed non-invasively.",
            **{"severity": "High"},
        )
        fm_header_leak = self._item(
            "failure-mode",
            "Header Seal Breach",
            "Ingress of body fluids through degraded header seal. Causes "
            "current leakage, corrosion of internal components, and "
            "progressive loss of device function.",
            **{"severity": "Critical"},
        )

        self._compose(hw_fmea, fm_output_open, fm_output_short, fm_sensing_loss,
                       fm_battery_premature, fm_telemetry_failure, fm_header_leak)

        # Failure causes
        fc_capacitor_aging = self._item(
            "failure-cause",
            "Output Capacitor Dielectric Degradation",
            "Age-related degradation of tantalum capacitor dielectric leading "
            "to increased ESR and eventual open-circuit failure.",
            **{"category": "Manufacturing"},
        )
        fc_mosfet_breakdown = self._item(
            "failure-cause",
            "MOSFET Gate Oxide Breakdown",
            "Time-dependent dielectric breakdown of the output MOSFET gate "
            "oxide under sustained electric field stress.",
            **{"category": "Design"},
        )
        fc_amplifier_drift = self._item(
            "failure-cause",
            "Sense Amplifier Offset Drift",
            "Progressive drift of the sense amplifier input offset voltage "
            "due to ionic contamination or radiation damage, reducing "
            "effective sensitivity below the programmed threshold.",
            **{"category": "Environmental"},
        )
        fc_cell_defect = self._item(
            "failure-cause",
            "Battery Cell Manufacturing Defect",
            "Lithium-iodine cell with internal defect (contamination, "
            "separator pinhole) causing elevated self-discharge rate.",
            **{"category": "Manufacturing"},
        )
        fc_seal_fatigue = self._item(
            "failure-cause",
            "Epoxy-Titanium Bond Fatigue",
            "Cyclic thermal and mechanical stress at the epoxy-titanium "
            "interface leading to micro-crack propagation and eventual "
            "seal breach.",
            **{"category": "Environmental"},
        )

        self._compose(hw_fmea, fc_capacitor_aging, fc_mosfet_breakdown,
                       fc_amplifier_drift, fc_cell_defect, fc_seal_fatigue)
        self._causes(fc_capacitor_aging, fm_output_open)
        self._causes(fc_mosfet_breakdown, fm_output_short)
        self._causes(fc_amplifier_drift, fm_sensing_loss)
        self._causes(fc_cell_defect, fm_battery_premature)
        self._causes(fc_seal_fatigue, fm_header_leak)

        # Link failure modes to challenged requirements
        self._mitigates(fm_output_open, req_pacing_output)
        self._mitigates(fm_output_short, req_pacing_output, req_battery_life)
        self._mitigates(fm_sensing_loss, req_sensing)
        self._mitigates(fm_battery_premature, req_battery_life, req_eri)
        self._mitigates(fm_header_leak, req_hermeticity)

        # ==============================================================
        # FAILURE MODES — Software FMEA
        # ==============================================================
        fm_sw_timing = self._item(
            "failure-mode",
            "Pacing Timing Violation",
            "Firmware timing error causing AV delay, blanking period, or "
            "refractory period outside specified bounds. May result in "
            "competitive pacing, undersensing, or pacemaker-mediated "
            "tachycardia.",
            **{"severity": "Critical"},
        )
        fm_sw_mode_switch = self._item(
            "failure-mode",
            "Failure to Mode-Switch",
            "Software fails to detect atrial tachyarrhythmia and continues "
            "tracking, resulting in ventricular pacing at dangerously high "
            "rates (pacemaker-mediated tachycardia).",
            **{"severity": "Critical"},
        )
        fm_sw_watchdog = self._item(
            "failure-mode",
            "Watchdog Failure to Trip",
            "Both the main therapy task and the watchdog supervisor fail "
            "simultaneously (common-cause failure), resulting in no pacing "
            "output with no automatic recovery.",
            **{"severity": "Critical"},
        )
        fm_sw_memory = self._item(
            "failure-mode",
            "Parameter Memory Corruption",
            "Corruption of programmed therapy parameters in non-volatile "
            "memory (e.g., due to SEU or write failure). Device operates "
            "with incorrect pacing parameters.",
            **{"severity": "Critical"},
        )

        self._compose(sw_fmea, fm_sw_timing, fm_sw_mode_switch, fm_sw_watchdog, fm_sw_memory)

        fc_sw_race = self._item(
            "failure-cause",
            "Task Scheduling Race Condition",
            "Race condition between the sensing ISR and the pacing timer "
            "task causing AV interval miscalculation.",
            **{"category": "Software"},
        )
        fc_sw_threshold = self._item(
            "failure-cause",
            "Detection Threshold Algorithm Error",
            "Incorrect threshold adaptation logic during rapid atrial rates "
            "causes under-counting of atrial events.",
            **{"category": "Software"},
        )
        fc_sw_stack = self._item(
            "failure-cause",
            "Stack Overflow in Therapy Task",
            "Unbounded recursion or excessive local variable allocation "
            "causing stack overflow and corruption of the therapy task "
            "context, freezing both therapy and watchdog.",
            **{"category": "Software"},
        )
        fc_sw_eeprom = self._item(
            "failure-cause",
            "EEPROM Write Interrupted by Reset",
            "Power-on reset during EEPROM parameter write leaves parameter "
            "block in inconsistent state.",
            **{"category": "Software"},
        )

        self._compose(sw_fmea, fc_sw_race, fc_sw_threshold, fc_sw_stack, fc_sw_eeprom)
        self._causes(fc_sw_race, fm_sw_timing)
        self._causes(fc_sw_threshold, fm_sw_mode_switch)
        self._causes(fc_sw_stack, fm_sw_watchdog)
        self._causes(fc_sw_eeprom, fm_sw_memory)

        # ==============================================================
        # RISKS
        # ==============================================================
        risk_oversensing = self._item(
            "risk",
            "Electromagnetic Interference Causing Oversensing",
            "Patient exposure to strong electromagnetic fields (MRI, "
            "electrosurgery, theft-detection systems) causes oversensing "
            "and inappropriate pacing inhibition in a pacemaker-dependent "
            "patient, leading to syncope or asystole.",
            **{"severity": "Critical",
               "likelihood": "Possible",
               "mitigation": "EMI-resistant sensing filters, programmable EMI "
                             "rejection mode, MRI-conditional design, patient "
                             "labelling and education"},
        )
        risk_lead_dislodge = self._item(
            "risk",
            "Lead Dislodgement Post-Implant",
            "Atrial or ventricular lead tip displaces from the myocardium "
            "within the first weeks after implantation, resulting in loss "
            "of capture and/or sensing. Requires surgical lead repositioning.",
            **{"severity": "High",
               "likelihood": "Possible",
               "mitigation": "Active-fixation lead design, automatic capture "
                             "management algorithm, high-output safety margin, "
                             "post-implant threshold testing protocol"},
        )
        risk_infection = self._item(
            "risk",
            "Device Pocket Infection",
            "Bacterial infection of the pacemaker pocket site. Can progress "
            "to lead endocarditis if untreated, requiring complete system "
            "extraction — a high-risk procedure.",
            **{"severity": "Critical",
               "likelihood": "Unlikely",
               "mitigation": "Antimicrobial envelope, strict sterile implant "
                             "technique, perioperative antibiotics, smooth "
                             "titanium surface finish to resist biofilm"},
        )
        risk_cyber_attack = self._item(
            "risk",
            "Unauthorised Wireless Reprogramming",
            "A malicious actor intercepts or spoofs the telemetry link to "
            "alter therapy parameters (e.g., set output to 0 V or maximum "
            "rate), potentially causing harm or death.",
            **{"severity": "Critical",
               "likelihood": "Rare",
               "mitigation": "Authenticated telemetry, proximity requirement "
                             "(near-field only), encrypted communication, "
                             "anomalous command rejection, security event logging"},
        )
        risk_premature_eos = self._item(
            "risk",
            "Premature End of Service",
            "Device reaches EOS significantly earlier than predicted battery "
            "longevity, requiring unplanned generator replacement surgery. "
            "Patient safety risk if ERI notification is missed.",
            **{"severity": "High",
               "likelihood": "Unlikely",
               "mitigation": "Conservative battery capacity derating, redundant "
                             "ERI/EOS detection, remote monitoring alerts, "
                             "accelerated life testing during verification"},
        )
        risk_sw_anomaly = self._item(
            "risk",
            "Software Anomaly During Therapy Delivery",
            "Firmware defect causes incorrect pacing behaviour (wrong rate, "
            "wrong output, failure to pace). Given Class C software classification, "
            "this is a life-threatening risk for dependent patients.",
            **{"severity": "Critical",
               "likelihood": "Unlikely",
               "mitigation": "IEC 62304 Class C processes, 100% MC/DC coverage, "
                             "independent hardware watchdog with backup pacing, "
                             "formal code review, static analysis (MISRA C)"},
        )
        risk_recall = self._item(
            "risk",
            "Field Safety Corrective Action (Recall)",
            "Post-market detection of a systematic defect requiring field "
            "corrective action. For implantable devices, software updates "
            "can mitigate some issues, but hardware defects may require "
            "surgical explant.",
            **{"severity": "Critical",
               "likelihood": "Rare",
               "mitigation": "Design for remote software update capability, "
                             "comprehensive pre-market verification, robust "
                             "post-market surveillance, complaint trending"},
        )

        self._compose(risk_mgmt_file, risk_oversensing, risk_lead_dislodge,
                       risk_infection, risk_cyber_attack, risk_premature_eos,
                       risk_sw_anomaly, risk_recall)

        # Link risks to challenged requirements
        self._mitigates(risk_oversensing, req_emc, req_sensing)
        self._mitigates(risk_cyber_attack, req_sec_auth, req_sec_encrypt)
        self._mitigates(risk_premature_eos, req_battery_life, req_eri)
        self._mitigates(risk_sw_anomaly, req_sw_pacing_engine, req_sw_watchdog)

        # ==============================================================
        # THREATS & VULNERABILITIES (Cybersecurity)
        # ==============================================================
        threat_replay = self._item(
            "threat",
            "Telemetry Replay Attack",
            "Attacker captures legitimate telemetry session traffic and "
            "replays programming commands to alter device settings. Requires "
            "proximity to the patient during a programming session.",
            **{"threat-level": "High",
               "attack-vector": "Adjacent",
               "threat-agent": "Skilled individual with SDR equipment"},
        )
        threat_firmware_tamper = self._item(
            "threat",
            "Malicious Firmware Injection",
            "Attacker exploits the firmware update mechanism to install "
            "modified firmware that alters therapy delivery or exfiltrates "
            "patient data.",
            **{"threat-level": "Critical",
               "attack-vector": "Adjacent",
               "threat-agent": "Nation-state actor or sophisticated attacker"},
        )
        threat_dos = self._item(
            "threat",
            "Telemetry Denial of Service",
            "Attacker floods the telemetry interface with spurious requests, "
            "preventing legitimate programmer communication during a clinical "
            "session. Does not directly affect therapy delivery.",
            **{"threat-level": "Medium",
               "attack-vector": "Adjacent",
               "threat-agent": "Disgruntled individual with RF equipment"},
        )
        threat_data_exfil = self._item(
            "threat",
            "Patient Data Exfiltration",
            "Attacker eavesdrops on unencrypted telemetry to extract patient "
            "health information (pacing history, arrhythmia episodes, device "
            "parameters).",
            **{"threat-level": "High",
               "attack-vector": "Adjacent",
               "threat-agent": "Eavesdropper with RF receiver"},
        )

        vuln_no_replay_protect = self._item(
            "vulnerability",
            "Lack of Replay Protection in Telemetry Protocol",
            "Telemetry protocol does not include nonce or timestamp validation, "
            "allowing captured commands to be replayed.",
            **{"severity": "High",
               "attack-feasibility": "Medium",
               "component": "Telemetry protocol stack"},
        )
        vuln_unsigned_fw = self._item(
            "vulnerability",
            "Unsigned Firmware Update Package",
            "Firmware update mechanism accepts update packages without "
            "cryptographic signature verification.",
            **{"severity": "Critical",
               "attack-feasibility": "Medium",
               "component": "Bootloader"},
        )
        vuln_unencrypted_telem = self._item(
            "vulnerability",
            "Unencrypted Telemetry Data Transmission",
            "Patient health data and device parameters transmitted in "
            "cleartext over the telemetry link.",
            **{"severity": "High",
               "attack-feasibility": "High",
               "component": "Telemetry protocol stack"},
        )
        vuln_no_rate_limit = self._item(
            "vulnerability",
            "No Rate Limiting on Telemetry Requests",
            "Telemetry interface processes all incoming requests without "
            "rate limiting or session management.",
            **{"severity": "Medium",
               "attack-feasibility": "High",
               "component": "Telemetry RF front-end"},
        )

        self._compose(threat_assessment, threat_replay, threat_firmware_tamper,
                       threat_dos, threat_data_exfil,
                       vuln_no_replay_protect, vuln_unsigned_fw,
                       vuln_unencrypted_telem, vuln_no_rate_limit)

        self._exploits(threat_replay, vuln_no_replay_protect)
        self._exploits(threat_firmware_tamper, vuln_unsigned_fw)
        self._exploits(threat_dos, vuln_no_rate_limit)
        self._exploits(threat_data_exfil, vuln_unencrypted_telem)

        # Mitigations
        mit_auth_protocol = self._item(
            "mitigation",
            "Challenge-Response Authentication Protocol",
            "Implement mutual authentication using ECDSA challenge-response "
            "with device-unique keys stored in secure element. Includes "
            "nonce to prevent replay attacks.",
            **{"control-type": "Preventive",
               "implementation-status": "In Progress"},
        )
        mit_fw_signing = self._item(
            "mitigation",
            "Firmware Code Signing with Secure Boot",
            "All firmware images signed with manufacturer ECDSA key. "
            "Bootloader verifies signature chain before executing any code. "
            "Fuse-locked root of trust in hardware.",
            **{"control-type": "Preventive",
               "implementation-status": "Implemented"},
        )
        mit_encryption = self._item(
            "mitigation",
            "AES-128-CCM Telemetry Encryption",
            "All telemetry data encrypted using AES-128 in CCM mode providing "
            "both confidentiality and authenticity. Session keys derived via "
            "ECDH key exchange.",
            **{"control-type": "Preventive",
               "implementation-status": "In Progress"},
        )
        mit_rate_limit = self._item(
            "mitigation",
            "Telemetry Request Rate Limiting",
            "Implement connection rate limiting and session management in the "
            "RF front-end. Maximum 3 concurrent sessions, with exponential "
            "back-off on authentication failure.",
            **{"control-type": "Preventive",
               "implementation-status": "Planned"},
        )

        self._compose(threat_assessment, mit_auth_protocol, mit_fw_signing,
                       mit_encryption, mit_rate_limit)
        self._mitigates(mit_auth_protocol, vuln_no_replay_protect)
        self._mitigates(mit_fw_signing, vuln_unsigned_fw)
        self._mitigates(mit_encryption, vuln_unencrypted_telem)
        self._mitigates(mit_rate_limit, vuln_no_rate_limit)

        # ==============================================================
        # TEST CASES — System Verification
        # ==============================================================
        tc_pacing_range = self._item(
            "test-case",
            "Pacing Output Range Verification",
            "Verify pacing pulse amplitude and width across full programmable "
            "range on both atrial and ventricular channels.",
            **{"test-steps": "1. Connect device to electronic load (500 Ω)\n"
                             "2. Programme each amplitude/width combination\n"
                             "3. Measure output on oscilloscope\n"
                             "4. Verify within ±5% of programmed value",
               "expected-result": "All amplitude/width combinations within ±5% tolerance"},
        )
        tc_sensing_threshold = self._item(
            "test-case",
            "Sensing Sensitivity Verification",
            "Verify sensing thresholds across full programmable range using "
            "calibrated test signals injected via the lead connector.",
            **{"test-steps": "1. Connect signal generator to lead port\n"
                             "2. Inject calibrated sine wave at cardiac frequency\n"
                             "3. Sweep amplitude from 0.1 mV to 20 mV\n"
                             "4. Verify sense marker at each sensitivity setting",
               "expected-result": "Sense marker triggered at programmed threshold ±10%"},
        )
        tc_battery_longevity = self._item(
            "test-case",
            "Battery Longevity Analysis",
            "Analytical verification of battery longevity using measured "
            "current drain data and battery discharge model.",
            **{"test-steps": "1. Measure current drain at nominal settings\n"
                             "2. Measure current drain at max settings\n"
                             "3. Apply battery discharge model with derating\n"
                             "4. Calculate projected longevity",
               "expected-result": "Projected longevity ≥ 10 years at nominal settings"},
        )
        tc_eri_eos = self._item(
            "test-case",
            "ERI / EOS Threshold Verification",
            "Verify ERI and EOS triggers at correct battery voltage thresholds "
            "and that VVI backup pacing activates at EOS.",
            **{"test-steps": "1. Simulate battery voltage ramp-down\n"
                             "2. Monitor for ERI indication\n"
                             "3. Continue ramp to EOS threshold\n"
                             "4. Verify VVI backup mode activation",
               "expected-result": "ERI at specified voltage, VVI backup at EOS within 2s"},
        )
        tc_emc = self._item(
            "test-case",
            "EMC Immunity Testing",
            "Verify device maintains safe operation during exposure to "
            "electromagnetic fields per IEC 60601-1-2.",
            **{"test-steps": "1. Configure device in DDD mode at nominal settings\n"
                             "2. Apply conducted immunity (IEC 61000-4-6)\n"
                             "3. Apply radiated immunity (IEC 61000-4-3)\n"
                             "4. Apply ESD (IEC 61000-4-2)\n"
                             "5. Monitor pacing output throughout",
               "expected-result": "No pacing inhibition, no inappropriate output, no reset"},
        )
        tc_mri = self._item(
            "test-case",
            "MRI Conditional Mode Verification",
            "Verify device operates safely in MRI-conditional mode during "
            "simulated MRI exposure.",
            **{"test-steps": "1. Programme MRI-conditional mode\n"
                             "2. Expose to 1.5 T and 3.0 T static fields\n"
                             "3. Apply gradient and RF fields per labelling conditions\n"
                             "4. Measure temperature rise, force, torque\n"
                             "5. Verify asynchronous pacing maintained",
               "expected-result": "Temperature rise < 2°C, stable pacing, no reset"},
        )
        tc_defib = self._item(
            "test-case",
            "Defibrillation Withstand Test",
            "Verify device survives external defibrillation and resumes "
            "normal operation.",
            **{"test-steps": "1. Connect device to defibrillation test fixture\n"
                             "2. Apply 360 J monophasic shock\n"
                             "3. Apply 200 J biphasic shock\n"
                             "4. Interrogate device after each shock\n"
                             "5. Verify programmed settings preserved",
               "expected-result": "Device resumes programmed operation within 5 seconds"},
        )
        tc_hermeticity = self._item(
            "test-case",
            "Hermetic Seal Leak Test",
            "Verify helium leak rate of the titanium enclosure.",
            **{"test-steps": "1. Place device in helium bombing chamber (5 atm, 2 hrs)\n"
                             "2. Transfer to helium leak detector within 1 minute\n"
                             "3. Measure fine leak rate\n"
                             "4. Repeat after thermal cycling (−40°C to +70°C, 100 cycles)",
               "expected-result": "Leak rate ≤ 1 × 10⁻⁹ atm·cc/sec before and after cycling"},
        )
        tc_biocompat = self._item(
            "test-case",
            "Biocompatibility Test Suite",
            "ISO 10993 biological evaluation for all patient-contacting materials.",
            **{"test-steps": "1. Cytotoxicity (ISO 10993-5) — L929 cell line\n"
                             "2. Sensitisation (ISO 10993-10) — Guinea pig maximisation\n"
                             "3. Irritation (ISO 10993-23) — In vitro reconstructed tissue\n"
                             "4. Systemic toxicity (ISO 10993-11)\n"
                             "5. Implantation (ISO 10993-6) — 26-week rabbit study",
               "expected-result": "All endpoints within acceptance criteria per ISO 10993"},
        )

        # Software verification tests
        tc_sw_sensing = self._item(
            "test-case",
            "Sensing Algorithm Validation — Annotated ECG Database",
            "Verify sensing algorithm performance against annotated ECG "
            "database with known event classifications.",
            **{"test-steps": "1. Load MIT-BIH annotated ECG database\n"
                             "2. Process each record through sensing algorithm\n"
                             "3. Compare detected events with annotations\n"
                             "4. Calculate sensitivity and specificity",
               "expected-result": "Sensitivity ≥ 99.5%, specificity ≥ 99.0%"},
        )
        tc_sw_timing = self._item(
            "test-case",
            "Pacing Timing Precision — All Modes",
            "Verify timing intervals (AV delay, PVARP, blanking) across all "
            "programmable values in all supported modes.",
            **{"test-steps": "1. Programme each mode (DDD, DDDR, VVI, AAI)\n"
                             "2. Set each timing parameter to min, nominal, max\n"
                             "3. Measure actual intervals on oscilloscope\n"
                             "4. Compare to programmed values",
               "expected-result": "All intervals within ±1 ms of programmed value"},
        )
        tc_sw_mode_switch = self._item(
            "test-case",
            "Mode Switch Response Time",
            "Verify mode switch activates within specification during "
            "simulated atrial tachyarrhythmia.",
            **{"test-steps": "1. Pace device in DDD mode at 70 bpm\n"
                             "2. Inject simulated atrial flutter at 300 bpm\n"
                             "3. Measure time from onset to mode switch\n"
                             "4. Verify ventricular rate drops to sensor rate",
               "expected-result": "Mode switch within ≤ 2 seconds of detection criteria met"},
        )
        tc_sw_watchdog = self._item(
            "test-case",
            "Watchdog Backup Pacing Activation",
            "Verify hardware watchdog triggers VVI backup pacing when main "
            "firmware task is halted.",
            **{"test-steps": "1. Run device in normal DDD mode\n"
                             "2. Inject debug command to halt therapy task\n"
                             "3. Measure time to VVI backup activation\n"
                             "4. Verify backup pacing parameters (70 bpm, 5.0 V)",
               "expected-result": "VVI backup within ≤ 2 seconds, correct parameters"},
        )
        tc_sw_mcdc = self._item(
            "test-case",
            "MC/DC Structural Coverage — Class C Modules",
            "Verify 100% Modified Condition/Decision Coverage for all "
            "IEC 62304 Class C software modules.",
            **{"test-steps": "1. Execute full unit test suite with coverage instrumentation\n"
                             "2. Generate MC/DC coverage report\n"
                             "3. Analyse gaps and add targeted tests\n"
                             "4. Re-run until 100% MC/DC achieved",
               "expected-result": "100% MC/DC coverage for all Class C modules"},
        )

        # Security tests
        tc_sec_auth = self._item(
            "test-case",
            "Telemetry Authentication Verification",
            "Verify that unauthenticated programming commands are rejected.",
            **{"test-steps": "1. Attempt programming without authentication\n"
                             "2. Attempt programming with invalid credentials\n"
                             "3. Attempt replay of captured authentication\n"
                             "4. Verify all rejected and logged",
               "expected-result": "All unauthorised attempts rejected, events logged"},
        )
        tc_sec_fw_sign = self._item(
            "test-case",
            "Firmware Signature Verification",
            "Verify that unsigned or tampered firmware is rejected.",
            **{"test-steps": "1. Attempt update with unsigned firmware image\n"
                             "2. Attempt update with modified signed image\n"
                             "3. Attempt update with valid signed image\n"
                             "4. Verify only valid image accepted",
               "expected-result": "Only correctly signed firmware accepted; others rejected"},
        )
        tc_sec_encrypt = self._item(
            "test-case",
            "Telemetry Encryption Verification",
            "Verify telemetry data is encrypted and cannot be read by "
            "passive eavesdropper.",
            **{"test-steps": "1. Capture telemetry RF traffic with SDR\n"
                             "2. Attempt to decode patient data from capture\n"
                             "3. Verify encryption negotiation occurs\n"
                             "4. Confirm captured data is indistinguishable from random",
               "expected-result": "No patient data recoverable from captured traffic"},
        )

        # Validation tests
        tc_val_bench = self._item(
            "test-case",
            "Pre-Clinical Bench Validation — Simulated Use",
            "Validate device performance in anatomical heart simulator under "
            "simulated clinical scenarios.",
            **{"test-steps": "1. Install device in heart simulator with physiological loads\n"
                             "2. Simulate normal sinus rhythm → verify inhibition\n"
                             "3. Simulate complete heart block → verify DDD pacing\n"
                             "4. Simulate atrial fibrillation → verify mode switch\n"
                             "5. Simulate lead dislodgement → verify autocapture response",
               "expected-result": "Correct device response in all simulated scenarios"},
        )
        tc_val_animal = self._item(
            "test-case",
            "Pre-Clinical Animal Study — Ovine Model",
            "Validate chronic device performance and biocompatibility in "
            "an ovine model over 26 weeks.",
            **{"test-steps": "1. Implant device in 6 sheep (dual-chamber)\n"
                             "2. Weekly threshold and impedance measurements\n"
                             "3. Histopathological examination at explant\n"
                             "4. Assess capsule formation and tissue response",
               "expected-result": "Stable thresholds, no adverse tissue reaction, minimal fibrosis"},
        )

        # Compose test cases into reports
        self._compose(ver_report, tc_pacing_range, tc_sensing_threshold,
                       tc_battery_longevity, tc_eri_eos, tc_emc, tc_mri,
                       tc_defib, tc_hermeticity, tc_biocompat)
        self._compose(sw_test_report, tc_sw_sensing, tc_sw_timing,
                       tc_sw_mode_switch, tc_sw_watchdog, tc_sw_mcdc,
                       tc_sec_auth, tc_sec_fw_sign, tc_sec_encrypt)
        self._compose(val_report, tc_val_bench, tc_val_animal)

        # Verification links
        self._verifies(tc_pacing_range, req_pacing_output)
        self._verifies(tc_sensing_threshold, req_sensing)
        self._verifies(tc_battery_longevity, req_battery_life)
        self._verifies(tc_eri_eos, req_eri)
        self._verifies(tc_emc, req_emc)
        self._verifies(tc_mri, req_mri_conditional)
        self._verifies(tc_defib, req_defibrillation)
        self._verifies(tc_hermeticity, req_hermeticity)
        self._verifies(tc_biocompat, req_biocompat)
        self._verifies(tc_sw_sensing, req_sw_sensing_algo)
        self._verifies(tc_sw_timing, req_sw_pacing_engine)
        self._verifies(tc_sw_mode_switch, req_sw_arrhythmia)
        self._verifies(tc_sw_watchdog, req_sw_watchdog)
        self._verifies(tc_sw_mcdc, req_sw_sensing_algo, req_sw_pacing_engine, req_sw_arrhythmia)
        self._verifies(tc_sec_auth, req_sec_auth)
        self._verifies(tc_sec_fw_sign, req_sec_integrity, req_sec_update)
        self._verifies(tc_sec_encrypt, req_sec_encrypt)

        # ==============================================================
        # TRACEABILITY MATRICES
        # ==============================================================

        # 1. System Requirements Traceability Matrix
        self._matrix(
            name="System RTM",
            description=(
                "Traces system-level requirements to their verifying "
                "test cases — the core design verification matrix."
            ),
            columns=[
                {
                    "label": "System Requirement",
                    "seed_item_type_slug": "requirement",
                    "seed_container": sys_req_spec,
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

        # 2. Software Requirements Traceability
        self._matrix(
            name="Software Requirements Traceability",
            description=(
                "Traces software requirements to system requirements "
                "(derives_from) and verifying test cases."
            ),
            columns=[
                {
                    "label": "Software Requirement",
                    "seed_item_type_slug": "requirement",
                    "seed_container": sw_req_spec,
                },
                {
                    "label": "Derived From",
                    "relation_name": "derives_from",
                    "direction": MatrixSource.Direction.OUTGOING,
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

        # 3. Hardware FMEA Matrix
        self._matrix(
            name="Hardware FMEA Matrix",
            description=(
                "Traces hardware failure modes to their root causes "
                "and challenged requirements."
            ),
            columns=[
                {
                    "label": "Failure Mode",
                    "seed_item_type_slug": "failure-mode",
                    "seed_container": hw_fmea,
                },
                {
                    "label": "Caused By",
                    "relation_name": "causes",
                    "direction": MatrixSource.Direction.INCOMING,
                },
                {
                    "label": "Challenges Requirement",
                    "relation_name": "mitigates",
                    "direction": MatrixSource.Direction.OUTGOING,
                },
            ],
        )

        # 4. Software FMEA Matrix
        self._matrix(
            name="Software FMEA Matrix",
            description=(
                "Traces software failure modes to their root causes "
                "and challenged requirements."
            ),
            columns=[
                {
                    "label": "Failure Mode",
                    "seed_item_type_slug": "failure-mode",
                    "seed_container": sw_fmea,
                },
                {
                    "label": "Caused By",
                    "relation_name": "causes",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

        # 5. Risk Assessment Matrix
        self._matrix(
            name="Risk Assessment Matrix",
            description=(
                "Traces identified risks to the requirements they challenge."
            ),
            columns=[
                {
                    "label": "Risk",
                    "seed_item_type_slug": "risk",
                    "seed_container": risk_mgmt_file,
                },
                {
                    "label": "Challenges Requirement",
                    "relation_name": "mitigates",
                    "direction": MatrixSource.Direction.OUTGOING,
                },
            ],
        )

        # 6. Cybersecurity Threat Assessment Matrix
        self._matrix(
            name="Cybersecurity Threat Matrix",
            description=(
                "Traces threats to exploited vulnerabilities and "
                "their mitigations."
            ),
            columns=[
                {
                    "label": "Threat",
                    "seed_item_type_slug": "threat",
                    "seed_container": threat_assessment,
                },
                {
                    "label": "Exploits Vulnerability",
                    "relation_name": "exploits",
                    "direction": MatrixSource.Direction.OUTGOING,
                },
                {
                    "label": "Mitigations",
                    "relation_name": "mitigates",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

        # 7. Requirement Decomposition Matrix
        self._matrix(
            name="Requirement Decomposition Matrix",
            description=(
                "Shows how system requirements are decomposed into "
                "lower-level software requirements."
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
                    "direction": MatrixSource.Direction.OUTGOING,
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

    # ------------------------------------------------------------------
    # Financial Risk Management example data
    # ------------------------------------------------------------------

    def _build_finance(self):
        # ==============================================================
        # TOP-LEVEL PROGRAMME
        # ==============================================================
        programme = self._item(
            "project",
            "TRP-4000 Trading Risk Platform",
            "Top-level programme for the TRP-4000 trading risk management "
            "platform. Covers market risk, credit risk, operational risk, "
            "and model validation for an investment bank's trading desk. "
            "Standards: Basel III/IV, FRTB, BCBS 239, MiFID II, Dodd-Frank.",
            **{"standard-reference": "Basel III/IV, FRTB, BCBS 239, MiFID II, Dodd-Frank"},
        )

        # ==============================================================
        # PLANS
        # ==============================================================
        model_risk_plan = self._item(
            "plan",
            "Model Risk Management Plan",
            "Framework for model validation, governance, and independent "
            "review per SR 11-7/SS1/19. Defines model tiering, validation "
            "frequency, ongoing monitoring, and model risk reporting.",
            **{"phase": "Approved",
               "standard-reference": "SR 11-7, SS1/19, TRIM"},
        )
        mrp_purpose = self._item(
            "information",
            "Purpose",
            "This plan establishes the model risk management framework for "
            "all quantitative models used in the trading risk platform. It "
            "ensures independent validation, ongoing monitoring, and governance "
            "of models that impact capital calculations, risk limits, and "
            "regulatory reporting.",
        )
        mrp_scope = self._item(
            "information",
            "Scope",
            "Covers all Tier 1 (material) and Tier 2 (significant) models "
            "including VaR, ES, CVA/DVA/FVA, Greeks engines, stress testing "
            "models, and regulatory capital calculators. Tier 3 models are "
            "subject to self-assessment with periodic review.",
        )
        mrp_governance = self._item(
            "information",
            "Governance Structure",
            "Model Risk Committee meets monthly to review validation findings, "
            "approve new models, and assess model risk appetite. Independent "
            "Model Validation team reports to CRO, not to front-office.",
        )
        self._compose(model_risk_plan, mrp_purpose, mrp_scope, mrp_governance)

        market_risk_plan = self._item(
            "plan",
            "Market Risk Management Plan",
            "VaR methodology, stress testing framework, limit hierarchy, and "
            "FRTB compliance roadmap. Defines daily risk reporting, escalation "
            "procedures, and back-testing requirements.",
            **{"phase": "Approved",
               "standard-reference": "Basel III CRR2, FRTB"},
        )
        mkrp_purpose = self._item(
            "information",
            "Purpose",
            "This plan defines the market risk measurement, monitoring, and "
            "control framework for all trading book positions. It ensures "
            "compliance with Basel III internal models approach and FRTB "
            "standardised and internal models requirements.",
        )
        mkrp_methodology = self._item(
            "information",
            "Risk Measurement Methodology",
            "Market risk is measured using historical simulation VaR (99%, 10-day) "
            "for internal risk management and Expected Shortfall (97.5%, varying "
            "liquidity horizons) for FRTB IMA. P&L attribution test and "
            "backtesting determine desk eligibility for IMA.",
        )
        mkrp_limits = self._item(
            "information",
            "Limit Framework",
            "Three-tier limit hierarchy: (1) firm-wide VaR limit set by Board, "
            "(2) desk-level VaR and sensitivity limits set by CRO, (3) trader-level "
            "notional and Greeks limits set by desk heads. All limits enforced "
            "pre-trade with intraday monitoring.",
        )
        self._compose(market_risk_plan, mkrp_purpose, mkrp_methodology, mkrp_limits)

        ops_risk_plan = self._item(
            "plan",
            "Operational Risk Management Plan",
            "RCSA methodology, loss event tracking, KRI monitoring framework, "
            "and scenario analysis for operational risk capital calculation.",
            **{"phase": "Approved",
               "standard-reference": "Basel III Pillar 2, BCBS 195"},
        )
        orp_purpose = self._item(
            "information",
            "Purpose",
            "This plan establishes the operational risk framework for the "
            "trading risk platform, covering risk and control self-assessment, "
            "loss event capture, key risk indicator monitoring, and scenario "
            "analysis for capital quantification.",
        )
        orp_scope = self._item(
            "information",
            "Scope",
            "Covers front-office trading operations, middle-office risk "
            "management, technology infrastructure, and regulatory reporting. "
            "Includes people risk, process risk, systems risk, and external "
            "event risk across all asset classes.",
        )
        self._compose(ops_risk_plan, orp_purpose, orp_scope)

        reg_reporting_plan = self._item(
            "plan",
            "Regulatory Reporting Plan",
            "Common Reporting (COREP), Pillar 3 disclosure, trade reporting "
            "under MiFIR/EMIR, and transaction reporting requirements.",
            **{"phase": "Review",
               "standard-reference": "CRR2, MiFIR, EMIR"},
        )
        rrp_purpose = self._item(
            "information",
            "Purpose",
            "This plan defines the regulatory reporting framework including "
            "data sourcing, calculation methodology, quality assurance, and "
            "submission procedures for all prudential and transaction reports.",
        )
        rrp_scope = self._item(
            "information",
            "Scope",
            "Covers COREP own funds and capital requirements, large exposures, "
            "leverage ratio, liquidity (LCR/NSFR), Pillar 3 disclosures, "
            "MiFIR transaction reporting, and EMIR trade reporting.",
        )
        self._compose(reg_reporting_plan, rrp_purpose, rrp_scope)

        bc_plan = self._item(
            "plan",
            "Business Continuity Plan",
            "DR/BC procedures for trading systems, recovery time objectives, "
            "failover procedures, and crisis management for the risk platform.",
            **{"phase": "Approved"},
        )
        bcp_purpose = self._item(
            "information",
            "Purpose",
            "This plan ensures continuity of critical trading risk functions "
            "during disruptive events. Defines RTO/RPO targets, failover "
            "procedures, and communication protocols.",
        )
        bcp_scenarios = self._item(
            "information",
            "Disruption Scenarios",
            "Covers data centre failure, network outage, market data feed "
            "loss, key person unavailability, cyber incident, and pandemic "
            "scenarios. Each scenario has defined response procedures and "
            "recovery playbooks.",
        )
        self._compose(bc_plan, bcp_purpose, bcp_scenarios)

        data_gov_plan = self._item(
            "plan",
            "Data Governance Plan",
            "Data lineage, quality controls, and BCBS 239 compliance for "
            "risk data aggregation and reporting.",
            **{"phase": "Approved",
               "standard-reference": "BCBS 239"},
        )
        dgp_purpose = self._item(
            "information",
            "Purpose",
            "This plan establishes data governance standards for risk data "
            "aggregation and reporting, ensuring accuracy, completeness, "
            "timeliness, and adaptability per BCBS 239 principles.",
        )
        dgp_lineage = self._item(
            "information",
            "Data Lineage Framework",
            "End-to-end data lineage from trade capture through risk "
            "calculation to regulatory reporting. Automated lineage tracking "
            "with impact analysis for upstream changes.",
        )
        dgp_quality = self._item(
            "information",
            "Data Quality Controls",
            "Automated data quality checks at each processing stage: "
            "completeness, accuracy, timeliness, and consistency. Data "
            "quality scorecards published daily with break resolution SLAs.",
        )
        self._compose(data_gov_plan, dgp_purpose, dgp_lineage, dgp_quality)

        self._compose(programme, model_risk_plan, market_risk_plan,
                       ops_risk_plan, reg_reporting_plan, bc_plan,
                       data_gov_plan)

        # ==============================================================
        # SPECIFICATIONS
        # ==============================================================
        sys_req_spec = self._item(
            "specification",
            "System Requirements Specification",
            "Functional and non-functional requirements for the TRP-4000 "
            "trading risk management platform. Covers all risk calculation "
            "engines, limit management, regulatory reporting, and data "
            "infrastructure.",
            **{"baseline": "SRS-BL-3"},
        )
        market_risk_spec = self._item(
            "specification",
            "Market Risk Engine Specification",
            "Detailed specification for VaR models, Expected Shortfall "
            "calculation, P&L attribution, Greeks computation, and stress "
            "testing engine.",
            **{"baseline": "MRE-BL-2"},
        )
        credit_risk_spec = self._item(
            "specification",
            "Credit Risk Engine Specification",
            "Specification for CVA/DVA/FVA computation, counterparty "
            "exposure profiling, wrong-way risk modelling, and collateral "
            "management calculations.",
            **{"baseline": "CRE-BL-1"},
        )
        reg_calc_spec = self._item(
            "specification",
            "Regulatory Calculation Specification",
            "Capital charge calculations under SA-TB and IMA approaches, "
            "Default Risk Charge (DRC), Residual Risk Add-On (RRAO), and "
            "CVA capital charge.",
            **{"baseline": "RCS-BL-2",
               "standard-reference": "CRR2 Art. 325"},
        )
        data_arch_spec = self._item(
            "specification",
            "Data Architecture Specification",
            "Trade data model, market data feed integration, risk factor "
            "taxonomy, reference data management, and data warehouse "
            "architecture.",
            **{"baseline": "DAS-BL-1",
               "standard-reference": "BCBS 239"},
        )

        self._compose(programme, sys_req_spec, market_risk_spec,
                       credit_risk_spec, reg_calc_spec, data_arch_spec)

        # ==============================================================
        # ANALYSES
        # ==============================================================
        var_validation = self._item(
            "analysis",
            "Model Validation Report — VaR",
            "Independent validation of the historical simulation VaR model "
            "including backtesting analysis (Kupiec POF, Christoffersen "
            "independence), P&L attribution test, and sensitivity analysis "
            "to model parameters.",
            **{"method": "Other"},
        )
        cva_validation = self._item(
            "analysis",
            "Model Validation Report — CVA",
            "Validation of the Monte Carlo CVA/DVA model including "
            "convergence analysis, wrong-way risk assessment, exposure "
            "profile benchmarking, and hedging effectiveness evaluation.",
            **{"method": "Other"},
        )
        ops_risk_assessment = self._item(
            "analysis",
            "Operational Risk Assessment",
            "Risk and Control Self-Assessment across front-office, "
            "middle-office, and technology functions. Key scenarios: "
            "fat-finger trades, market data feed failures, model errors, "
            "and regulatory reporting failures.",
            **{"method": "FMEA"},
        )
        frtb_impact = self._item(
            "analysis",
            "FRTB Impact Analysis",
            "Impact assessment of Fundamental Review of the Trading Book "
            "rules on capital requirements. Includes desk-level P&L "
            "attribution test results, SA vs IMA comparison, and "
            "implementation gap analysis.",
            **{"method": "Other"},
        )

        self._compose(programme, var_validation, cva_validation,
                       ops_risk_assessment, frtb_impact)

        # ==============================================================
        # REPORTS
        # ==============================================================
        stress_report = self._item(
            "report",
            "Stress Testing Report",
            "Results of regulatory and internal stress scenarios applied "
            "to the current trading book. Includes historical replay "
            "(2008 GFC, 2020 COVID, 2022 LDI crisis) and hypothetical "
            "scenarios (rates shock, credit spread widening, FX dislocation).",
            **{"report-date": "2025-12-15",
               "status": "Final"},
        )
        model_inventory = self._item(
            "report",
            "Model Inventory Report",
            "Complete inventory of quantitative models with Tier 1/2/3 "
            "classification, validation status, model risk ratings, "
            "last validation date, and identified limitations.",
            **{"report-date": "2025-11-30",
               "status": "Final"},
        )
        icaap = self._item(
            "report",
            "ICAAP Submission",
            "Internal Capital Adequacy Assessment Process document for "
            "regulatory submission. Covers Pillar 2A capital requirements, "
            "stress testing capital adequacy, and capital planning.",
            **{"report-date": "2026-01-15",
               "status": "Draft"},
        )
        pillar3_report = self._item(
            "report",
            "Pillar 3 Disclosure Report",
            "Public disclosure of risk metrics, capital ratios, risk "
            "management practices, and remuneration policies per CRR2 "
            "Part Eight requirements.",
            **{"report-date": "2025-12-31",
               "status": "Under Review"},
        )

        self._compose(programme, stress_report, model_inventory,
                       icaap, pillar3_report)

        # ==============================================================
        # REQUIREMENTS — System Requirements Specification
        # ==============================================================
        req_var_compute = self._item(
            "requirement",
            "Portfolio VaR Computation",
            "The platform shall compute portfolio VaR at 99% confidence "
            "level within 15 minutes for up to 500,000 positions.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_realtime_pnl = self._item(
            "requirement",
            "Real-Time P&L Computation",
            "The platform shall support real-time P&L computation with "
            "latency not exceeding 500ms per position update.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_pretrade_limits = self._item(
            "requirement",
            "Pre-Trade Limit Enforcement",
            "Risk limits shall be enforced pre-trade with sub-millisecond "
            "latency for all asset classes.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_audit_trail = self._item(
            "requirement",
            "Limit Breach Audit Trail",
            "The system shall maintain a complete audit trail of all limit "
            "breaches, overrides, and approvals with timestamps, user IDs, "
            "and justification text.",
            **{"priority": "High",
               "verification-method": "Inspection"},
        )
        req_reg_reports = self._item(
            "requirement",
            "Regulatory Report Generation",
            "All regulatory reports shall be generated and submitted within "
            "T+1 of the reporting date.",
            **{"priority": "High",
               "verification-method": "Test"},
        )

        self._compose(sys_req_spec, req_var_compute, req_realtime_pnl,
                       req_pretrade_limits, req_audit_trail, req_reg_reports)

        # ==============================================================
        # REQUIREMENTS — Market Risk Engine Specification
        # ==============================================================
        req_var_hist_sim = self._item(
            "requirement",
            "VaR Historical Simulation",
            "VaR shall be calculated using historical simulation with a "
            "minimum 2-year lookback period and 500 scenarios.",
            **{"priority": "High",
               "verification-method": "Test"},
        )
        req_es_frtb = self._item(
            "requirement",
            "Expected Shortfall — FRTB",
            "Expected Shortfall shall be computed at 97.5% confidence for "
            "FRTB compliance with liquidity-adjusted horizons per risk "
            "factor category.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_greeks = self._item(
            "requirement",
            "Sensitivity Computation",
            "The system shall compute sensitivities (delta, gamma, vega, "
            "rho) for all linear and non-linear products across all "
            "asset classes.",
            **{"priority": "High",
               "verification-method": "Test"},
        )
        req_stress_scenarios = self._item(
            "requirement",
            "Stress Scenario Framework",
            "Stress scenarios shall include both historical (2008 GFC, "
            "2020 COVID, 2022 LDI crisis) and hypothetical scenarios "
            "with user-defined shock magnitudes.",
            **{"priority": "High",
               "verification-method": "Analysis"},
        )

        self._compose(market_risk_spec, req_var_hist_sim, req_es_frtb,
                       req_greeks, req_stress_scenarios)

        # ==============================================================
        # REQUIREMENTS — Credit Risk Engine Specification
        # ==============================================================
        req_cva_mc = self._item(
            "requirement",
            "CVA Monte Carlo Simulation",
            "CVA shall be computed using Monte Carlo simulation with a "
            "minimum of 10,000 paths and variance reduction techniques.",
            **{"priority": "High",
               "verification-method": "Test"},
        )
        req_wwr = self._item(
            "requirement",
            "Wrong-Way Risk Modelling",
            "Wrong-way risk shall be modelled with correlation between "
            "counterparty credit quality and exposure, using copula-based "
            "or structural approaches.",
            **{"priority": "High",
               "verification-method": "Analysis"},
        )
        req_exposure_profiles = self._item(
            "requirement",
            "Counterparty Exposure Profiles",
            "Counterparty exposure profiles (EPE, ENE, PFE) shall be "
            "generated for all netting sets with daily granularity out "
            "to the longest maturity.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )

        self._compose(credit_risk_spec, req_cva_mc, req_wwr,
                       req_exposure_profiles)

        # ==============================================================
        # REQUIREMENTS — Regulatory Calculation Specification
        # ==============================================================
        req_sa_tb = self._item(
            "requirement",
            "SA-TB Capital Charges",
            "Capital charges under SA-TB shall be computed per CRR2 "
            "Articles 325a-325az, covering delta, vega, and curvature "
            "risk charges across all risk classes.",
            **{"priority": "Critical",
               "verification-method": "Test"},
        )
        req_drc = self._item(
            "requirement",
            "Default Risk Charge",
            "DRC charges shall reflect jump-to-default risk for all "
            "credit-sensitive positions including bonds, CDS, and "
            "securitisations.",
            **{"priority": "High",
               "verification-method": "Test"},
        )
        req_rrao = self._item(
            "requirement",
            "Residual Risk Add-On",
            "RRAO shall capture residual risks not covered by delta, "
            "vega, and curvature charges, including gap risk, correlation "
            "risk, and behavioural risks.",
            **{"priority": "Medium",
               "verification-method": "Analysis"},
        )

        self._compose(reg_calc_spec, req_sa_tb, req_drc, req_rrao)

        # ==============================================================
        # REQUIREMENT DERIVATION
        # ==============================================================
        self._derives(req_var_hist_sim, req_var_compute)
        self._derives(req_es_frtb, req_var_compute)
        self._derives(req_greeks, req_realtime_pnl)
        self._derives(req_cva_mc, req_var_compute)
        self._derives(req_wwr, req_var_compute)
        self._derives(req_exposure_profiles, req_pretrade_limits)
        self._derives(req_sa_tb, req_reg_reports)
        self._derives(req_drc, req_reg_reports)
        self._derives(req_rrao, req_reg_reports)

        # ==============================================================
        # REQUIREMENT DECOMPOSITION (refines)
        # ==============================================================
        req_var_perf_gpu = self._item(
            "requirement",
            "GPU-Accelerated VaR Computation",
            "The VaR engine shall leverage GPU acceleration to achieve "
            "full portfolio revaluation within the 15-minute SLA for "
            "portfolios exceeding 100,000 positions.",
            **{"priority": "High",
               "verification-method": "Test"},
        )
        req_var_incremental = self._item(
            "requirement",
            "Incremental VaR Computation",
            "The system shall support incremental VaR calculation for "
            "what-if analysis, computing the VaR impact of a proposed "
            "trade within 5 seconds.",
            **{"priority": "High",
               "verification-method": "Test"},
        )
        req_limit_hierarchy = self._item(
            "requirement",
            "Hierarchical Limit Aggregation",
            "Limits shall aggregate hierarchically from trader to desk "
            "to business unit to firm level, with real-time utilisation "
            "tracking at each level.",
            **{"priority": "High",
               "verification-method": "Test"},
        )

        self._compose(sys_req_spec, req_var_perf_gpu, req_var_incremental,
                       req_limit_hierarchy)
        self._refines(req_var_compute, req_var_perf_gpu, req_var_incremental)
        self._refines(req_pretrade_limits, req_limit_hierarchy)

        # ==============================================================
        # RISKS — Risk Register
        # ==============================================================
        risk_register = self._item(
            "analysis",
            "Risk Register",
            "Consolidated risk register for the Trading Risk Platform "
            "covering model risk, market risk, operational risk, technology "
            "risk, regulatory risk, and cyber risk.",
            **{"method": "Other"},
        )
        self._compose(programme, risk_register)

        risk_var_underest = self._item(
            "risk",
            "Model Risk — VaR Underestimation",
            "VaR model systematically underestimates tail risk due to "
            "model specification error, insufficient lookback period, "
            "or failure to capture regime changes. Results in inadequate "
            "capital buffers and unexpected large losses.",
            **{"severity": "Critical",
               "likelihood": "Possible",
               "mitigation": "Independent model validation, daily backtesting with "
                             "traffic-light framework, regulatory multiplier buffer, "
                             "supplementary stressed VaR calculation"},
        )
        risk_liquidity = self._item(
            "risk",
            "Liquidity Risk — Concentrated Positions",
            "Large concentrated positions in illiquid instruments cannot "
            "be unwound within the assumed liquidity horizon, leading to "
            "realised losses exceeding VaR estimates.",
            **{"severity": "High",
               "likelihood": "Likely",
               "mitigation": "Position concentration limits, liquidity horizons per "
                             "risk factor, bid-ask spread monitoring, liquidity "
                             "stress testing"},
        )
        risk_fat_finger = self._item(
            "risk",
            "Operational Risk — Fat-Finger Trade Entry",
            "Erroneous trade entry with incorrect quantity, price, or "
            "direction causes immediate market impact and P&L loss. "
            "May trigger cascading limit breaches across desks.",
            **{"severity": "High",
               "likelihood": "Possible",
               "mitigation": "Pre-trade limit checks, four-eyes principle for "
                             "large trades, automated reasonableness checks, "
                             "order size caps"},
        )
        risk_data_feed = self._item(
            "risk",
            "Technology Risk — Market Data Feed Failure",
            "Primary market data feed failure causes stale prices in "
            "risk calculations, leading to incorrect VaR, wrong limit "
            "utilisation, and potentially missed limit breaches.",
            **{"severity": "Critical",
               "likelihood": "Unlikely",
               "mitigation": "Dual feed providers, stale data detection with "
                             "configurable staleness thresholds, automatic "
                             "fallback to secondary feed"},
        )
        risk_frtb_gaps = self._item(
            "risk",
            "Regulatory Risk — FRTB Implementation Gaps",
            "Incomplete or incorrect implementation of FRTB rules results "
            "in regulatory capital miscalculation, potential supervisory "
            "add-ons, and reputational damage.",
            **{"severity": "High",
               "likelihood": "Possible",
               "mitigation": "Comprehensive gap analysis, phased implementation "
                             "plan, regulatory dialogue, parallel running of old "
                             "and new approaches"},
        )
        risk_large_exposure = self._item(
            "risk",
            "Counterparty Risk — Large Exposure Breach",
            "Counterparty exposure exceeds regulatory large exposure "
            "limit due to market movements or failed collateral calls, "
            "resulting in regulatory breach notification.",
            **{"severity": "Critical",
               "likelihood": "Unlikely",
               "mitigation": "Real-time exposure monitoring, early warning "
                             "triggers at 80% of limit, automated collateral "
                             "calls, close-out netting enforcement"},
        )
        risk_cyber = self._item(
            "risk",
            "Cyber Risk — Trading System Compromise",
            "Unauthorised access to trading or risk systems enables "
            "manipulation of positions, limits, or risk calculations. "
            "Could result in undetected losses or data exfiltration.",
            **{"severity": "Critical",
               "likelihood": "Unlikely",
               "mitigation": "Network segmentation, privileged access management, "
                             "SOC monitoring, regular penetration testing, "
                             "insider threat programme"},
        )
        risk_data_quality = self._item(
            "risk",
            "Data Quality Risk — Incorrect Position Data",
            "Incorrect or incomplete position data propagates to risk "
            "calculations, producing misleading risk metrics and "
            "potentially masking limit breaches.",
            **{"severity": "High",
               "likelihood": "Possible",
               "mitigation": "Automated reconciliation between trading and risk "
                             "systems, data quality scorecards, break resolution "
                             "SLAs, T+0 position certification"},
        )

        self._compose(risk_register, risk_var_underest, risk_liquidity,
                       risk_fat_finger, risk_data_feed, risk_frtb_gaps,
                       risk_large_exposure, risk_cyber, risk_data_quality)

        # Link risks to challenged requirements
        self._mitigates(risk_var_underest, req_var_compute, req_var_hist_sim)
        self._mitigates(risk_liquidity, req_pretrade_limits)
        self._mitigates(risk_fat_finger, req_pretrade_limits, req_audit_trail)
        self._mitigates(risk_data_feed, req_realtime_pnl, req_var_compute)
        self._mitigates(risk_frtb_gaps, req_sa_tb, req_es_frtb)
        self._mitigates(risk_large_exposure, req_exposure_profiles)
        self._mitigates(risk_data_quality, req_reg_reports)

        # ==============================================================
        # FAILURE MODES — Operational Risk Assessment
        # ==============================================================
        fm_var_low = self._item(
            "failure-mode",
            "VaR Model Produces Systematically Low Estimates",
            "Model specification error or stale calibration causes VaR "
            "to systematically underestimate tail risk. Backtesting "
            "exceptions accumulate, potentially triggering regulatory "
            "capital multiplier increase.",
            **{"severity": "Critical"},
        )
        fm_stale_data = self._item(
            "failure-mode",
            "Market Data Feed Delivers Stale Prices",
            "Primary data feed continues to deliver prices that are not "
            "updating, without signalling an error. Stale prices propagate "
            "through risk calculations, producing incorrect VaR, Greeks, "
            "and limit utilisation figures.",
            **{"severity": "High"},
        )
        fm_limit_bypass = self._item(
            "failure-mode",
            "Risk Limit Enforcement Bypassed During High Volatility",
            "System overload during high-volatility market events causes "
            "the pre-trade limit check service to time out, and trades "
            "are routed through a bypass path without limit validation.",
            **{"severity": "Critical"},
        )
        fm_netting_error = self._item(
            "failure-mode",
            "Incorrect Netting Set Assignment",
            "Trades assigned to wrong netting sets due to master agreement "
            "mapping errors, inflating or deflating counterparty exposure "
            "calculations and regulatory capital.",
            **{"severity": "High"},
        )
        fm_batch_timeout = self._item(
            "failure-mode",
            "Batch Risk Calculation Fails to Complete Before Market Open",
            "End-of-day batch risk calculation exceeds the overnight "
            "processing window, resulting in traders starting the day "
            "without updated risk figures and limit utilisation.",
            **{"severity": "High"},
        )
        fm_trade_booking = self._item(
            "failure-mode",
            "Trade Booking Error Propagates to Risk Calculations",
            "Incorrect trade attributes (notional, maturity, strike) "
            "entered in the booking system flow through to risk "
            "calculations without detection, producing incorrect "
            "risk metrics for the affected desk.",
            **{"severity": "Medium"},
        )

        self._compose(ops_risk_assessment, fm_var_low, fm_stale_data,
                       fm_limit_bypass, fm_netting_error, fm_batch_timeout,
                       fm_trade_booking)

        # Failure causes
        fc_regime_change = self._item(
            "failure-cause",
            "Regime Change Not Captured in Lookback Window",
            "Structural market regime change (e.g., shift from low-vol to "
            "high-vol environment) occurs outside the VaR lookback window, "
            "causing the model to underweight tail scenarios.",
            **{"category": "Design"},
        )
        fc_vendor_outage = self._item(
            "failure-cause",
            "Primary Market Data Vendor Outage",
            "Market data vendor experiences system failure but continues "
            "to serve last known prices without error indication, causing "
            "silent data staleness.",
            **{"category": "Environmental"},
        )
        fc_concurrency = self._item(
            "failure-cause",
            "Concurrency Bottleneck Under Peak Load",
            "Limit check microservice cannot scale horizontally fast enough "
            "during market stress events, causing request queue overflow "
            "and timeout-based bypass activation.",
            **{"category": "Software"},
        )
        fc_manual_netting = self._item(
            "failure-cause",
            "Manual Netting Set Maintenance Process",
            "Netting set assignments are maintained manually in a reference "
            "data system, leading to stale or incorrect mappings when new "
            "master agreements are negotiated.",
            **{"category": "Human Error"},
        )
        fc_batch_capacity = self._item(
            "failure-cause",
            "Insufficient Batch Compute Capacity",
            "Batch risk calculation infrastructure not scaled to handle "
            "growing portfolio size, causing processing time to exceed "
            "the overnight batch window.",
            **{"category": "Design"},
        )
        fc_no_validation = self._item(
            "failure-cause",
            "Lack of Automated Trade Validation Rules",
            "Booking system does not enforce automated reasonableness "
            "checks on trade attributes, allowing obviously incorrect "
            "values to pass through.",
            **{"category": "Software"},
        )

        self._compose(ops_risk_assessment, fc_regime_change, fc_vendor_outage,
                       fc_concurrency, fc_manual_netting, fc_batch_capacity,
                       fc_no_validation)

        self._causes(fc_regime_change, fm_var_low)
        self._causes(fc_vendor_outage, fm_stale_data)
        self._causes(fc_concurrency, fm_limit_bypass)
        self._causes(fc_manual_netting, fm_netting_error)
        self._causes(fc_batch_capacity, fm_batch_timeout)
        self._causes(fc_no_validation, fm_trade_booking)

        # Link failure modes to challenged requirements
        self._mitigates(fm_var_low, req_var_compute)
        self._mitigates(fm_stale_data, req_realtime_pnl)
        self._mitigates(fm_limit_bypass, req_pretrade_limits)
        self._mitigates(fm_netting_error, req_exposure_profiles)
        self._mitigates(fm_batch_timeout, req_reg_reports)
        self._mitigates(fm_trade_booking, req_audit_trail)

        # ==============================================================
        # THREATS & VULNERABILITIES — Cybersecurity
        # ==============================================================
        threat_assessment = self._item(
            "analysis",
            "Cybersecurity Threat Assessment",
            "Threat assessment for the Trading Risk Platform covering "
            "insider threats, external cyber threats, and vulnerabilities "
            "in the risk calculation and reporting infrastructure.",
            **{"method": "Other"},
        )
        self._compose(programme, threat_assessment)

        threat_insider = self._item(
            "threat",
            "Insider Trading via Risk System Access",
            "Authorised user with access to the risk system exploits "
            "knowledge of firm-wide positions and risk limits to conduct "
            "insider trading or front-running.",
            **{"threat-level": "High",
               "attack-vector": "Local",
               "threat-agent": "Rogue trader"},
        )
        threat_limit_override = self._item(
            "threat",
            "Market Manipulation Through Limit Override",
            "Authorised user with elevated access overrides risk limits "
            "to build up positions beyond approved thresholds, potentially "
            "concealing losses or manipulating markets.",
            **{"threat-level": "High",
               "attack-vector": "Local",
               "threat-agent": "Authorised user with elevated access"},
        )
        threat_strategy_exfil = self._item(
            "threat",
            "Data Exfiltration of Proprietary Trading Strategies",
            "State-sponsored actor or competitive intelligence operation "
            "exfiltrates proprietary trading strategies, risk models, "
            "and position data from the risk platform.",
            **{"threat-level": "Critical",
               "attack-vector": "Network",
               "threat-agent": "State-sponsored actor / competitive intelligence"},
        )
        threat_ransomware = self._item(
            "threat",
            "Ransomware Targeting Risk Calculation Infrastructure",
            "Organised cybercrime group deploys ransomware that encrypts "
            "risk calculation infrastructure, preventing the firm from "
            "computing risk metrics and regulatory reports.",
            **{"threat-level": "Critical",
               "attack-vector": "Network",
               "threat-agent": "Organised cybercrime"},
        )
        threat_reg_manipulation = self._item(
            "threat",
            "Regulatory Data Manipulation",
            "Internal actor manipulates regulatory reporting data to "
            "conceal losses, reduce reported capital requirements, or "
            "avoid regulatory scrutiny.",
            **{"threat-level": "High",
               "attack-vector": "Local",
               "threat-agent": "Internal actor attempting to conceal losses"},
        )

        # Vulnerabilities
        vuln_shared_accounts = self._item(
            "vulnerability",
            "Shared Privileged Accounts for Risk Engine Administration",
            "Risk engine infrastructure administered via shared privileged "
            "accounts without individual accountability, enabling "
            "unattributable system changes.",
            **{"severity": "High",
               "attack-feasibility": "High",
               "component": "Risk Engine Infrastructure"},
        )
        vuln_unencrypted_feeds = self._item(
            "vulnerability",
            "Unencrypted Market Data Feeds on Internal Network",
            "Market data feeds transmitted unencrypted on the internal "
            "network, allowing interception and potential manipulation "
            "of pricing data.",
            **{"severity": "Medium",
               "attack-feasibility": "Medium",
               "component": "Market Data Distribution"},
        )
        vuln_legacy_modules = self._item(
            "vulnerability",
            "Legacy Risk Calculation Modules Without Input Validation",
            "Legacy risk calculation modules accept unvalidated inputs, "
            "enabling injection of malformed data that could corrupt "
            "risk calculations or cause denial of service.",
            **{"severity": "High",
               "attack-feasibility": "Medium",
               "component": "Risk Calculation Engine"},
        )
        vuln_network_segmentation = self._item(
            "vulnerability",
            "Insufficient Segregation Between Trading and Risk Systems",
            "Trading and risk systems share network segments without "
            "adequate access controls, allowing lateral movement from "
            "compromised trading terminals to risk infrastructure.",
            **{"severity": "High",
               "attack-feasibility": "High",
               "component": "Network Architecture"},
        )
        vuln_weak_auth = self._item(
            "vulnerability",
            "Weak Authentication for Regulatory Reporting Portal",
            "Regulatory reporting portal uses single-factor authentication, "
            "enabling credential theft and unauthorised submission or "
            "modification of regulatory data.",
            **{"severity": "Medium",
               "attack-feasibility": "High",
               "component": "Regulatory Reporting"},
        )

        self._compose(threat_assessment, threat_insider, threat_limit_override,
                       threat_strategy_exfil, threat_ransomware,
                       threat_reg_manipulation,
                       vuln_shared_accounts, vuln_unencrypted_feeds,
                       vuln_legacy_modules, vuln_network_segmentation,
                       vuln_weak_auth)

        self._exploits(threat_insider, vuln_shared_accounts)
        self._exploits(threat_limit_override, vuln_shared_accounts)
        self._exploits(threat_strategy_exfil, vuln_network_segmentation, vuln_unencrypted_feeds)
        self._exploits(threat_ransomware, vuln_legacy_modules, vuln_network_segmentation)
        self._exploits(threat_reg_manipulation, vuln_weak_auth)

        # Mitigations
        mit_pam = self._item(
            "mitigation",
            "Privileged Access Management (PAM) for Risk Systems",
            "Implement enterprise PAM solution for all risk system "
            "administration. Individual accountability, session recording, "
            "just-in-time access provisioning, and automatic credential "
            "rotation.",
            **{"control-type": "Preventive",
               "implementation-status": "In Progress"},
        )
        mit_feed_encryption = self._item(
            "mitigation",
            "End-to-End Encryption for Market Data Feeds",
            "Deploy TLS 1.3 encryption for all market data feeds on "
            "internal network, with mutual authentication between "
            "publisher and subscriber endpoints.",
            **{"control-type": "Preventive",
               "implementation-status": "Planned"},
        )
        mit_input_validation = self._item(
            "mitigation",
            "Input Validation and Parameterised Queries for Risk Engine",
            "Add comprehensive input validation, parameterised queries, "
            "and schema enforcement to all risk calculation engine "
            "interfaces. Include fuzzing in CI/CD pipeline.",
            **{"control-type": "Preventive",
               "implementation-status": "Implemented"},
        )
        mit_microsegmentation = self._item(
            "mitigation",
            "Network Micro-Segmentation Between Trading and Risk Domains",
            "Implement zero-trust network micro-segmentation between "
            "trading, risk, and regulatory reporting zones with explicit "
            "allow-listing of required data flows.",
            **{"control-type": "Preventive",
               "implementation-status": "In Progress"},
        )
        mit_mfa = self._item(
            "mitigation",
            "Multi-Factor Authentication for Regulatory Reporting",
            "Enforce hardware-token MFA for all access to regulatory "
            "reporting systems, with step-up authentication for "
            "submission actions.",
            **{"control-type": "Preventive",
               "implementation-status": "Implemented"},
        )
        mit_anomaly_detection = self._item(
            "mitigation",
            "Real-Time Anomaly Detection for Trading Pattern Surveillance",
            "Deploy machine-learning-based anomaly detection for trading "
            "patterns, limit override patterns, and data access patterns. "
            "Alerts routed to compliance and security operations.",
            **{"control-type": "Detective",
               "implementation-status": "Verified"},
        )

        self._compose(threat_assessment, mit_pam, mit_feed_encryption,
                       mit_input_validation, mit_microsegmentation,
                       mit_mfa, mit_anomaly_detection)

        self._mitigates(mit_pam, vuln_shared_accounts)
        self._mitigates(mit_feed_encryption, vuln_unencrypted_feeds)
        self._mitigates(mit_input_validation, vuln_legacy_modules)
        self._mitigates(mit_microsegmentation, vuln_network_segmentation)
        self._mitigates(mit_mfa, vuln_weak_auth)
        self._mitigates(mit_anomaly_detection, risk_cyber, risk_fat_finger)

        # ==============================================================
        # TEST CASES
        # ==============================================================
        tc_var_accuracy = self._item(
            "test-case",
            "VaR 99% Confidence Level Accuracy",
            "Verify VaR calculation accuracy against a known portfolio "
            "with analytic solution.",
            **{"test-steps": "1. Construct benchmark portfolio with known analytic VaR\n"
                             "2. Load portfolio into risk engine\n"
                             "3. Run historical simulation VaR calculation\n"
                             "4. Compare result to analytic solution",
               "expected-result": "Calculated VaR within 1% of analytic result"},
        )
        tc_var_perf = self._item(
            "test-case",
            "VaR Computation Performance",
            "Verify full portfolio VaR computation completes within "
            "the 15-minute SLA.",
            **{"test-steps": "1. Load production-representative portfolio of 500,000 positions\n"
                             "2. Trigger full revaluation VaR calculation\n"
                             "3. Measure wall-clock time to completion\n"
                             "4. Record resource utilisation metrics",
               "expected-result": "Complete within 15 minutes with margin"},
        )
        tc_pnl_attrib = self._item(
            "test-case",
            "P&L Attribution Test",
            "Verify risk-theoretical P&L explains actual P&L within "
            "FRTB thresholds.",
            **{"test-steps": "1. Calculate risk-theoretical P&L using sensitivities\n"
                             "2. Obtain actual P&L from front-office system\n"
                             "3. Compare for 5 consecutive trading days\n"
                             "4. Compute Spearman correlation and Kolmogorov-Smirnov test",
               "expected-result": "Unexplained P&L ratio < 10%, correlation > 0.8"},
        )
        tc_pretrade_latency = self._item(
            "test-case",
            "Pre-Trade Limit Check Latency",
            "Verify pre-trade limit check latency under load.",
            **{"test-steps": "1. Configure limit check service with production parameters\n"
                             "2. Submit 10,000 order requests concurrently\n"
                             "3. Measure response time for each request\n"
                             "4. Calculate 99th percentile latency",
               "expected-result": "99th percentile latency < 1ms"},
        )
        tc_stress_gfc = self._item(
            "test-case",
            "Stress Scenario — 2008 GFC Replay",
            "Verify stress testing engine correctly applies historical "
            "2008 GFC market moves.",
            **{"test-steps": "1. Load current production portfolio\n"
                             "2. Apply 2008 GFC historical scenario shocks\n"
                             "3. Compute stressed P&L and capital impact\n"
                             "4. Compare with expected results from reference model",
               "expected-result": "P&L impact within 5% of reference model"},
        )
        tc_cva_convergence = self._item(
            "test-case",
            "CVA Monte Carlo Convergence",
            "Verify CVA calculation convergence with increasing path count.",
            **{"test-steps": "1. Select representative netting set\n"
                             "2. Run CVA with 10,000 paths\n"
                             "3. Run CVA with 50,000 paths\n"
                             "4. Run CVA with 100,000 paths\n"
                             "5. Compare results at each level",
               "expected-result": "Results converge within 2% at 10,000 paths"},
        )
        tc_sa_tb = self._item(
            "test-case",
            "Regulatory Capital SA-TB Calculation",
            "Verify SA-TB capital charge calculation against regulator's "
            "benchmark portfolio.",
            **{"test-steps": "1. Load BCBS benchmark portfolio\n"
                             "2. Compute SA-TB capital charges\n"
                             "3. Compare with regulator's reference results\n"
                             "4. Investigate any discrepancies",
               "expected-result": "Match regulator's reference calculation within 0.1%"},
        )
        tc_audit_trail = self._item(
            "test-case",
            "Audit Trail Completeness",
            "Verify all limit breaches are captured in the audit trail.",
            **{"test-steps": "1. Configure test limit framework with known thresholds\n"
                             "2. Trigger 100 limit breaches across all limit types\n"
                             "3. Query audit trail for breach records\n"
                             "4. Verify completeness and data integrity",
               "expected-result": "100% capture rate with timestamps, user IDs, and justifications"},
        )
        tc_data_failover = self._item(
            "test-case",
            "Market Data Failover",
            "Verify automatic failover to secondary market data feed.",
            **{"test-steps": "1. Establish normal operation with primary feed\n"
                             "2. Simulate primary feed failure\n"
                             "3. Measure time to automatic switch\n"
                             "4. Verify data continuity and quality on secondary",
               "expected-result": "Automatic switch to secondary feed within 5 seconds"},
        )
        tc_wwr = self._item(
            "test-case",
            "Wrong-Way Risk Detection",
            "Verify system correctly identifies wrong-way risk in "
            "constructed test portfolio.",
            **{"test-steps": "1. Construct portfolio with known wrong-way risk exposure\n"
                             "2. Run CVA with and without wrong-way risk modelling\n"
                             "3. Verify system flags elevated exposure correlation\n"
                             "4. Compare CVA uplift to expected range",
               "expected-result": "System flags wrong-way risk, CVA uplift within expected range"},
        )
        tc_drc = self._item(
            "test-case",
            "FRTB DRC Calculation",
            "Verify Default Risk Charge calculation for credit portfolio.",
            **{"test-steps": "1. Load credit portfolio with known DRC\n"
                             "2. Compute DRC using production engine\n"
                             "3. Compare with reference implementation\n"
                             "4. Validate issuer-level and portfolio-level results",
               "expected-result": "Match reference implementation within 0.5%"},
        )
        tc_eod_batch = self._item(
            "test-case",
            "End-of-Day Batch Processing",
            "Verify full EOD risk calculations complete within the "
            "batch window.",
            **{"test-steps": "1. Trigger full EOD batch with production-sized portfolio\n"
                             "2. Monitor all calculation stages\n"
                             "3. Verify all outputs generated correctly\n"
                             "4. Measure total elapsed time",
               "expected-result": "Complete within 4-hour batch window"},
        )

        # Compose test cases into their parent containers
        self._compose(stress_report, tc_stress_gfc)
        self._compose(var_validation, tc_var_accuracy, tc_var_perf, tc_pnl_attrib)
        self._compose(cva_validation, tc_cva_convergence, tc_wwr)

        sys_verification = self._item(
            "report",
            "System Verification Report",
            "Consolidated verification report tracking system-level test "
            "execution and results for the TRP-4000 platform. Covers "
            "pre-trade checks, regulatory calculations, data failover, "
            "batch processing, and audit trail verification.",
            **{"report-date": "2026-01-31",
               "status": "Draft"},
        )
        self._compose(programme, sys_verification)
        self._compose(sys_verification, tc_pretrade_latency, tc_sa_tb,
                       tc_audit_trail, tc_data_failover, tc_drc,
                       tc_eod_batch)

        # Verification links
        self._verifies(tc_var_accuracy, req_var_compute, req_var_hist_sim)
        self._verifies(tc_var_perf, req_var_compute, req_var_perf_gpu)
        self._verifies(tc_pnl_attrib, req_es_frtb)
        self._verifies(tc_pretrade_latency, req_pretrade_limits)
        self._verifies(tc_stress_gfc, req_stress_scenarios)
        self._verifies(tc_cva_convergence, req_cva_mc)
        self._verifies(tc_sa_tb, req_sa_tb)
        self._verifies(tc_audit_trail, req_audit_trail)
        self._verifies(tc_data_failover, req_realtime_pnl)
        self._verifies(tc_wwr, req_wwr)
        self._verifies(tc_drc, req_drc)
        self._verifies(tc_eod_batch, req_reg_reports)

        # ==============================================================
        # TRACEABILITY MATRICES
        # ==============================================================

        # 1. Requirements Verification Matrix
        self._matrix(
            name="Requirements Verification Matrix",
            description=(
                "Traces system requirements to their verifying test cases — "
                "the core verification traceability matrix."
            ),
            columns=[
                {
                    "label": "System Requirement",
                    "seed_item_type_slug": "requirement",
                    "seed_container": sys_req_spec,
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

        # 2. Market Risk Requirements Traceability
        self._matrix(
            name="Market Risk Requirements Traceability",
            description=(
                "Traces market risk requirements to parent system "
                "requirements and verifying test cases."
            ),
            columns=[
                {
                    "label": "Market Risk Requirement",
                    "seed_item_type_slug": "requirement",
                    "seed_container": market_risk_spec,
                },
                {
                    "label": "Derived From",
                    "relation_name": "derives_from",
                    "direction": MatrixSource.Direction.OUTGOING,
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

        # 3. Risk Register Matrix
        self._matrix(
            name="Risk Register Matrix",
            description=(
                "Traces identified risks to the requirements they challenge."
            ),
            columns=[
                {
                    "label": "Risk",
                    "seed_item_type_slug": "risk",
                    "seed_container": risk_register,
                },
                {
                    "label": "Challenges Requirement",
                    "relation_name": "mitigates",
                    "direction": MatrixSource.Direction.OUTGOING,
                },
            ],
        )

        # 4. Operational FMEA Matrix
        self._matrix(
            name="Operational FMEA Matrix",
            description=(
                "Traces operational failure modes to their root causes."
            ),
            columns=[
                {
                    "label": "Failure Mode",
                    "seed_item_type_slug": "failure-mode",
                    "seed_container": ops_risk_assessment,
                },
                {
                    "label": "Caused By",
                    "relation_name": "causes",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

        # 5. Cybersecurity Threat Matrix
        self._matrix(
            name="Cybersecurity Threat Matrix",
            description=(
                "Traces threats to exploited vulnerabilities and "
                "their mitigations."
            ),
            columns=[
                {
                    "label": "Threat",
                    "seed_item_type_slug": "threat",
                    "seed_container": threat_assessment,
                },
                {
                    "label": "Exploits Vulnerability",
                    "relation_name": "exploits",
                    "direction": MatrixSource.Direction.OUTGOING,
                },
                {
                    "label": "Mitigations",
                    "relation_name": "mitigates",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

        # 6. Model Validation Traceability
        self._matrix(
            name="Model Validation Traceability",
            description=(
                "Traces regulatory calculation requirements to parent "
                "requirements and verifying test cases."
            ),
            columns=[
                {
                    "label": "Regulatory Requirement",
                    "seed_item_type_slug": "requirement",
                    "seed_container": reg_calc_spec,
                },
                {
                    "label": "Derived From",
                    "relation_name": "derives_from",
                    "direction": MatrixSource.Direction.OUTGOING,
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

        # 7. Capital Requirements Decomposition
        self._matrix(
            name="Capital Requirements Decomposition",
            description=(
                "Shows how system requirements are decomposed into "
                "lower-level requirements and their verification."
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
                    "direction": MatrixSource.Direction.OUTGOING,
                },
                {
                    "label": "Verifying Test Cases",
                    "relation_name": "verifies",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

    # ------------------------------------------------------------------
    # DoD RFP Sales vault schema
    # ------------------------------------------------------------------

    def _setup_dod_sales_schema(self, admin):
        """
        Create item types, custom fields, custom relation types, and
        document templates for the DoD RFP Sales vault.  Populates
        ``self._types`` and ``self._relations``.
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
            ("Opportunity", "opportunity", "A DoD contract opportunity or pursuit.", "target"),
            ("RFP Requirement", "rfp-requirement", "A requirement extracted from the Request for Proposal.", "file-text"),
            ("Proposal Section", "proposal-section", "A section or volume of the proposal response.", "book-open"),
            ("Compliance Response", "compliance-response", "A response demonstrating compliance with an RFP requirement.", "check-square"),
            ("Win Theme", "win-theme", "A discriminating theme that differentiates our proposal.", "flag"),
            ("Competitor", "competitor", "A known competitor for this opportunity.", "swords"),
            ("Past Performance", "past-performance", "A past performance citation demonstrating relevant experience.", "award"),
            ("Pricing Element", "pricing-element", "A Contract Line Item Number (CLIN) or pricing component.", "dollar-sign"),
            ("Risk", "risk", "A risk to the pursuit or proposal.", "alert-triangle"),
            ("Action Item", "action-item", "A trackable action item for the capture or proposal team.", "circle-check"),
            ("Gate Review", "gate-review", "A formal colour-team review gate.", "door-open"),
            ("Question", "question", "A question submitted to the contracting officer.", "help-circle"),
            ("Demo Scenario", "demo-scenario", "A demonstration scenario for oral presentations or tech demos.", "presentation"),
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
            # opportunity
            ("opportunity", "Contract Value", "contract-value", "text", False, {}),
            ("opportunity", "NAICS Code", "naics-code", "text", False, {}),
            ("opportunity", "Set-Aside", "set-aside", "choice", False, {"choices": ["Full & Open", "Small Business", "8(a)", "SDVOSB", "HUBZone"]}),
            ("opportunity", "Due Date", "due-date", "date", False, {}),
            ("opportunity", "Contracting Office", "contracting-office", "text", False, {}),
            # rfp-requirement
            ("rfp-requirement", "Section Reference", "section-reference", "text", False, {}),
            ("rfp-requirement", "Priority", "priority", "choice", False, {"choices": ["Mandatory", "Desirable", "Optional"]}),
            # proposal-section
            ("proposal-section", "Volume", "volume", "choice", False, {"choices": ["Technical", "Management", "Past Performance", "Cost-Price", "Executive Summary"]}),
            ("proposal-section", "Page Limit", "page-limit", "text", False, {}),
            ("proposal-section", "Author", "author", "text", False, {}),
            ("proposal-section", "Status", "status", "choice", False, {"choices": ["Not Started", "Draft", "Review", "Final"]}),
            # compliance-response
            ("compliance-response", "Compliance Level", "compliance-level", "choice", False, {"choices": ["Full", "Partial", "Non-Compliant"]}),
            ("compliance-response", "Explanation", "explanation", "text", False, {}),
            # win-theme
            ("win-theme", "Theme Category", "theme-category", "choice", False, {"choices": ["Technical", "Management", "Past Performance", "Cost", "Risk"]}),
            # competitor
            ("competitor", "Strength", "strength", "text", False, {}),
            ("competitor", "Weakness", "weakness", "text", False, {}),
            ("competitor", "Win Probability", "win-probability", "choice", False, {"choices": ["Low", "Medium", "High"]}),
            # past-performance
            ("past-performance", "Contract Number", "contract-number", "text", False, {}),
            ("past-performance", "Agency", "agency", "text", False, {}),
            ("past-performance", "Contract Value", "contract-value", "text", False, {}),
            ("past-performance", "Period of Performance", "period-of-performance", "text", False, {}),
            ("past-performance", "CPARS Rating", "cpars-rating", "choice", False, {"choices": ["Exceptional", "Very Good", "Satisfactory", "Marginal", "Unsatisfactory"]}),
            # pricing-element
            ("pricing-element", "CLIN Number", "clin-number", "text", False, {}),
            ("pricing-element", "CLIN Type", "clin-type", "choice", False, {"choices": ["FFP", "T&M", "CPFF", "CPIF", "IDIQ"]}),
            ("pricing-element", "Value", "value", "text", False, {}),
            # risk
            ("risk", "Severity", "severity", "choice", False, {"choices": ["Low", "Medium", "High", "Critical"]}),
            ("risk", "Likelihood", "likelihood", "choice", False, {"choices": ["Low", "Medium", "High"]}),
            ("risk", "Risk Area", "risk-area", "choice", False, {"choices": ["Technical", "Schedule", "Cost", "Competitive", "Compliance"]}),
            # action-item
            ("action-item", "Owner", "owner", "text", False, {}),
            ("action-item", "Due Date", "due-date", "date", False, {}),
            ("action-item", "Status", "status", "choice", False, {"choices": ["Open", "In Progress", "Complete", "Blocked"]}),
            # gate-review
            ("gate-review", "Review Type", "review-type", "choice", False, {"choices": ["Pink Team", "Red Team", "Gold Team", "Final Review"]}),
            ("gate-review", "Review Date", "review-date", "date", False, {}),
            ("gate-review", "Outcome", "outcome", "choice", False, {"choices": ["Pass", "Pass with Comments", "Major Rewrite", "Not Conducted"]}),
            # question
            ("question", "Submitted Date", "submitted-date", "date", False, {}),
            ("question", "Response Status", "response-status", "choice", False, {"choices": ["Draft", "Submitted", "Answered", "Withdrawn"]}),
            # demo-scenario
            ("demo-scenario", "Duration", "duration", "text", False, {}),
            ("demo-scenario", "Status", "status", "choice", False, {"choices": ["Planned", "Rehearsed", "Ready"]}),
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
                "name": "responds_to",
                "forward_label": "responds to",
                "reverse_label": "is responded to by",
                "description": "A proposal section responds to an RFP requirement.",
                "source_item_type": self._types["proposal-section"],
                "target_item_type": self._types["rfp-requirement"],
            },
            {
                "kind": "trace",
                "name": "evidenced_by",
                "forward_label": "is evidenced by",
                "reverse_label": "provides evidence for",
                "description": "A compliance response is evidenced by a past performance citation.",
                "source_item_type": self._types["compliance-response"],
                "target_item_type": self._types["past-performance"],
            },
            {
                "kind": "trace",
                "name": "demonstrates",
                "forward_label": "demonstrates",
                "reverse_label": "is demonstrated by",
                "description": "A demo scenario demonstrates an RFP requirement.",
                "source_item_type": self._types["demo-scenario"],
                "target_item_type": self._types["rfp-requirement"],
            },
            {
                "kind": "trace",
                "name": "counters",
                "forward_label": "counters",
                "reverse_label": "is countered by",
                "description": "A win theme counters a competitor's position.",
                "source_item_type": self._types["win-theme"],
                "target_item_type": self._types["competitor"],
            },
            {
                "kind": "trace",
                "name": "prices",
                "forward_label": "prices",
                "reverse_label": "is priced by",
                "description": "A pricing element prices an RFP requirement.",
                "source_item_type": self._types["pricing-element"],
                "target_item_type": self._types["rfp-requirement"],
            },
            {
                "kind": "trace",
                "name": "mitigates",
                "forward_label": "mitigates",
                "reverse_label": "is mitigated by",
                "description": "An action or control mitigates a risk.",
                "source_item_type": None,
                "target_item_type": None,
            },
            {
                "kind": "trace",
                "name": "clarifies",
                "forward_label": "clarifies",
                "reverse_label": "is clarified by",
                "description": "A question clarifies an RFP requirement.",
                "source_item_type": self._types["question"],
                "target_item_type": self._types["rfp-requirement"],
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
                "rfp-requirement",
                "{{heading}} {{title}}\n\n"
                "| Field | Value |\n"
                "|---|---|\n"
                "| **Section Reference** | {{section-reference}} |\n"
                "| **Priority** | {{priority}} |\n"
                "| **Status** | {{status}} |\n"
                "| **Version** | {{current_version}} |\n\n"
                "{{description}}\n",
            ),
            (
                "compliance-response",
                "{{heading}} {{title}}\n\n"
                "**Compliance Level:** {{compliance-level}}\n\n"
                "**Explanation:** {{explanation}}\n\n"
                "{{description}}\n",
            ),
            (
                "risk",
                "{{heading}} {{title}}\n\n"
                "**Severity:** {{severity}} | **Likelihood:** {{likelihood}} | "
                "**Risk Area:** {{risk-area}}\n\n"
                "{{description}}\n",
            ),
            (
                "gate-review",
                "{{heading}} {{title}}\n\n"
                "**Review Type:** {{review-type}} | **Outcome:** {{outcome}} | "
                "**Review Date:** {{review-date}}\n\n"
                "{{description}}\n",
            ),
            (
                "information",
                "{{heading}} {{title}}\n\n{{description}}\n",
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
    # DoD RFP Sales example data
    # ------------------------------------------------------------------

    def _build_dod_rfp(self):
        # ==============================================================
        # OPPORTUNITY
        # ==============================================================
        opp = self._item(
            "opportunity",
            "NGCC Pursuit \u2014 Next-Gen Command & Control",
            "Pursuit of the $250M NGCC contract for the U.S. Joint Force "
            "Command. The programme delivers a next-generation command and "
            "control system integrating joint mission planning, common "
            "operating picture, multi-domain sensor fusion, and tactical "
            "communications across all service branches. Full & Open "
            "competition under FAR 15; best-value trade-off evaluation.",
            **{
                "contract-value": "$250,000,000",
                "naics-code": "541512",
                "set-aside": "Full & Open",
                "contracting-office": "PEO C3T, Aberdeen Proving Ground",
            },
        )

        # ==============================================================
        # RFP REQUIREMENTS (18)
        # ==============================================================
        rfp_001 = self._item(
            "rfp-requirement",
            "RFP-001: Joint Mission Planning",
            "The system shall provide collaborative joint mission planning "
            "capability supporting course-of-action development, wargaming, "
            "and order generation across all echelons from Division to Squad.",
            **{"section-reference": "SOW 3.1.1", "priority": "Mandatory"},
        )
        rfp_002 = self._item(
            "rfp-requirement",
            "RFP-002: Common Operating Picture Display",
            "The system shall render a common operating picture aggregating "
            "blue-force tracks, hostile tracks, and environmental overlays "
            "with sub-second refresh rates and MIL-STD-2525D symbology.",
            **{"section-reference": "SOW 3.1.2", "priority": "Mandatory"},
        )
        rfp_003 = self._item(
            "rfp-requirement",
            "RFP-003: Multi-Domain Sensor Fusion",
            "The system shall fuse sensor data from space, air, land, sea, "
            "and cyber domains using a publish-subscribe architecture with "
            "automated correlation and track management.",
            **{"section-reference": "SOW 3.1.3", "priority": "Mandatory"},
        )
        rfp_004 = self._item(
            "rfp-requirement",
            "RFP-004: Tactical Communications Gateway",
            "The system shall provide a tactical communications gateway "
            "supporting SATCOM, HF, VHF/UHF, and wideband data links with "
            "automatic link management and bandwidth optimisation.",
            **{"section-reference": "SOW 3.2.1", "priority": "Mandatory"},
        )
        rfp_005 = self._item(
            "rfp-requirement",
            "RFP-005: Link 16/JREAP Integration",
            "The system shall interface with Link 16 tactical data link "
            "via MIDS-JTRS terminals and support JREAP-C encapsulation "
            "for beyond-line-of-sight relay over IP networks.",
            **{"section-reference": "SOW 3.2.2", "priority": "Mandatory"},
        )
        rfp_006 = self._item(
            "rfp-requirement",
            "RFP-006: Coalition Partner Data Sharing",
            "The system shall support coalition data sharing with Five Eyes "
            "and NATO partners via cross-domain solutions with configurable "
            "release policies and automated downgrade guards.",
            **{"section-reference": "SOW 3.2.3", "priority": "Desirable"},
        )
        rfp_007 = self._item(
            "rfp-requirement",
            "RFP-007: RMF Authorization (NIST 800-53 Rev 5)",
            "The contractor shall achieve Risk Management Framework "
            "authorization to operate (ATO) at Impact Level 5, implementing "
            "all applicable NIST SP 800-53 Rev 5 security controls.",
            **{"section-reference": "SOW 3.3.1", "priority": "Mandatory"},
        )
        rfp_008 = self._item(
            "rfp-requirement",
            "RFP-008: Zero Trust Architecture Implementation",
            "The system shall implement a zero-trust security architecture "
            "per DoD Zero Trust Reference Architecture v2.0, with continuous "
            "authentication, micro-segmentation, and least-privilege access.",
            **{"section-reference": "SOW 3.3.2", "priority": "Mandatory"},
        )
        rfp_009 = self._item(
            "rfp-requirement",
            "RFP-009: STIG Compliance & Continuous Monitoring",
            "All system components shall comply with applicable DISA STIGs "
            "and support continuous monitoring via ACAS vulnerability scanning "
            "and HBSS endpoint protection integration.",
            **{"section-reference": "SOW 3.3.3", "priority": "Mandatory"},
        )
        rfp_010 = self._item(
            "rfp-requirement",
            "RFP-010: Role-Based Access with Identity Federation",
            "The system shall implement role-based access control federated "
            "with DoD Identity, Credential, and Access Management (ICAM) "
            "services, supporting CAC/PIV authentication and SAML 2.0.",
            **{"section-reference": "SOW 3.3.4", "priority": "Desirable"},
        )
        rfp_011 = self._item(
            "rfp-requirement",
            "RFP-011: System Availability 99.99% Uptime",
            "The system shall achieve 99.99% operational availability "
            "measured across a rolling 12-month period, with automatic "
            "failover completing within 30 seconds of fault detection.",
            **{"section-reference": "SOW 3.4.1", "priority": "Mandatory"},
        )
        rfp_012 = self._item(
            "rfp-requirement",
            "RFP-012: Disconnected/Degraded/Intermittent Operations",
            "The system shall maintain mission-critical functionality during "
            "disconnected, degraded, and intermittent (D-DIL) communications "
            "using local caching, store-and-forward, and mesh networking.",
            **{"section-reference": "SOW 3.4.2", "priority": "Mandatory"},
        )
        rfp_013 = self._item(
            "rfp-requirement",
            "RFP-013: Scalability to 10,000 Concurrent Users",
            "The system shall support a minimum of 10,000 concurrent users "
            "across geographically distributed sites with no degradation in "
            "response time beyond the thresholds specified in CDRL A001.",
            **{"section-reference": "SOW 3.4.3", "priority": "Desirable"},
        )
        rfp_014 = self._item(
            "rfp-requirement",
            "RFP-014: CDRL A001 \u2014 System Design Document",
            "The contractor shall deliver a System Design Document per "
            "DI-MISC-81183B describing the system architecture, interface "
            "definitions, database design, and security architecture.",
            **{"section-reference": "DI-MISC-81183B", "priority": "Mandatory"},
        )
        rfp_015 = self._item(
            "rfp-requirement",
            "RFP-015: CDRL A002 \u2014 Software Test Report",
            "The contractor shall deliver a Software Test Report per "
            "DI-IPSC-81439A documenting test procedures, results, deficiency "
            "reports, and regression test outcomes for each build.",
            **{"section-reference": "DI-IPSC-81439A", "priority": "Mandatory"},
        )
        rfp_016 = self._item(
            "rfp-requirement",
            "RFP-016: CDRL A003 \u2014 Cybersecurity Assessment Report",
            "The contractor shall deliver a Cybersecurity Assessment Report "
            "per DI-MGMT-82163 including vulnerability scan results, STIG "
            "compliance status, and plan of action and milestones (POA&M).",
            **{"section-reference": "DI-MGMT-82163", "priority": "Mandatory"},
        )
        rfp_017 = self._item(
            "rfp-requirement",
            "RFP-017: Training Program \u2014 Operator & Administrator",
            "The contractor shall develop and deliver a training programme "
            "for system operators and administrators, including instructor-led "
            "training, computer-based training, and job aids.",
            **{"section-reference": "SOW 3.5.1", "priority": "Mandatory"},
        )
        rfp_018 = self._item(
            "rfp-requirement",
            "RFP-018: Technology Refresh Plan",
            "The contractor shall deliver a technology refresh plan addressing "
            "hardware obsolescence, software currency, and COTS upgrade "
            "cycles over the 10-year programme lifecycle.",
            **{"section-reference": "SOW 3.6.1", "priority": "Desirable"},
        )

        # ==============================================================
        # PROPOSAL VOLUMES & SECTIONS
        # ==============================================================
        vol_i = self._item(
            "proposal-section",
            "Vol I \u2014 Technical Approach",
            "Technical volume describing the system architecture, design "
            "approach, and technical solution for the NGCC programme.",
            **{"volume": "Technical", "page-limit": "200", "author": "Chief Engineer", "status": "Draft"},
        )
        vol_ii = self._item(
            "proposal-section",
            "Vol II \u2014 Management Approach",
            "Management volume describing programme management, risk "
            "management, staffing, and integrated master schedule.",
            **{"volume": "Management", "page-limit": "100", "author": "Program Manager", "status": "Draft"},
        )
        vol_iii = self._item(
            "proposal-section",
            "Vol III \u2014 Past Performance",
            "Past performance volume presenting relevant contract citations "
            "demonstrating capability and experience.",
            **{"volume": "Past Performance", "page-limit": "50", "author": "BD Manager", "status": "Review"},
        )
        vol_iv = self._item(
            "proposal-section",
            "Vol IV \u2014 Cost/Price",
            "Cost/price volume with basis of estimate, CLIN pricing, and "
            "supporting cost data per DFARS 252.215-7010.",
            **{"volume": "Cost-Price", "page-limit": "No Limit", "author": "Pricing Manager", "status": "Not Started"},
        )
        self._compose(opp, vol_i, vol_ii, vol_iii, vol_iv)

        # -- Vol I sub-sections -------------------------------------------
        sec_1_1 = self._item(
            "proposal-section",
            "1.1 System Architecture Overview",
            "Describes the overall system architecture including service-oriented "
            "design, microservices decomposition, containerised deployment on "
            "IL-5 cloud, and the integration backbone.",
            **{"volume": "Technical", "author": "Solution Architect", "status": "Draft"},
        )
        sec_1_2 = self._item(
            "proposal-section",
            "1.2 Mission Planning & COA Development",
            "Details the joint mission planning capability including course-of-action "
            "development, collaborative planning tools, wargaming engine, and "
            "automated order generation.",
            **{"volume": "Technical", "author": "Mission Planning Lead", "status": "Draft"},
        )
        sec_1_3 = self._item(
            "proposal-section",
            "1.3 Common Operating Picture & Sensor Fusion",
            "Describes the COP rendering engine, multi-domain sensor fusion "
            "algorithms, track correlation and management, and MIL-STD-2525D "
            "symbology implementation.",
            **{"volume": "Technical", "author": "COP Lead Engineer", "status": "Draft"},
        )
        sec_1_4 = self._item(
            "proposal-section",
            "1.4 Communications & Interoperability",
            "Covers the tactical communications gateway, Link 16/JREAP "
            "integration, SATCOM interfaces, and coalition data sharing "
            "with cross-domain solutions.",
            **{"volume": "Technical", "author": "Comms Lead", "status": "Not Started"},
        )
        sec_1_5 = self._item(
            "proposal-section",
            "1.5 Cybersecurity & RMF Compliance",
            "Details the zero-trust architecture, RMF authorization approach, "
            "STIG compliance strategy, continuous monitoring, and identity "
            "federation with DoD ICAM.",
            **{"volume": "Technical", "author": "Cyber Lead", "status": "Draft"},
        )
        sec_1_6 = self._item(
            "proposal-section",
            "1.6 CDRL Management Approach",
            "Describes the approach for delivering all CDRLs including the "
            "System Design Document, Software Test Report, and Cybersecurity "
            "Assessment Report per the specified DIDs.",
            **{"volume": "Technical", "author": "Systems Engineer", "status": "Not Started"},
        )
        self._compose(vol_i, sec_1_1, sec_1_2, sec_1_3, sec_1_4, sec_1_5, sec_1_6)

        # -- Vol II sub-sections ------------------------------------------
        sec_2_1 = self._item(
            "proposal-section",
            "2.1 Program Management Approach",
            "Describes the programme management framework including EVM, "
            "agile/hybrid methodology, governance structure, and customer "
            "reporting cadence.",
            **{"volume": "Management", "author": "Program Manager", "status": "Draft"},
        )
        sec_2_2 = self._item(
            "proposal-section",
            "2.2 Risk Management",
            "Details the risk management process including identification, "
            "assessment, mitigation planning, tracking, and reporting aligned "
            "with DoD Risk, Issue, and Opportunity management guidance.",
            **{"volume": "Management", "author": "Risk Manager", "status": "Draft"},
        )
        sec_2_3 = self._item(
            "proposal-section",
            "2.3 Staffing & Key Personnel",
            "Presents the organisational structure, key personnel qualifications, "
            "and staffing plan for the NGCC programme across all phases.",
            **{"volume": "Management", "author": "HR Manager", "status": "Not Started"},
        )
        sec_2_4 = self._item(
            "proposal-section",
            "2.4 Integrated Master Schedule",
            "Provides the integrated master schedule showing all programme "
            "milestones, deliverables, reviews, and critical path analysis "
            "across the system development lifecycle.",
            **{"volume": "Management", "author": "Scheduler", "status": "Not Started"},
        )
        self._compose(vol_ii, sec_2_1, sec_2_2, sec_2_3, sec_2_4)

        # ==============================================================
        # COMPLIANCE RESPONSES (18)
        # ==============================================================
        cr_001 = self._item(
            "compliance-response",
            "CR-001: Joint Mission Planning Compliance",
            "Full compliance. Our proven JADC2 mission planning engine supports "
            "collaborative COA development across all echelons with automated "
            "order generation and wargaming capability.",
            **{"compliance-level": "Full", "explanation": "Demonstrated on JADC2 Integration contract with identical mission planning requirements."},
        )
        cr_002 = self._item(
            "compliance-response",
            "CR-002: Common Operating Picture Compliance",
            "Full compliance. Our COP engine renders MIL-STD-2525D symbology "
            "with sub-second refresh rates and supports configurable map "
            "layers, overlays, and track filters.",
            **{"compliance-level": "Full", "explanation": "COP engine delivered on GCCS-J Modernization with 200ms average refresh rate."},
        )
        cr_003 = self._item(
            "compliance-response",
            "CR-003: Multi-Domain Sensor Fusion Compliance",
            "Full compliance. Our sensor fusion engine uses a publish-subscribe "
            "architecture with automated track correlation across space, air, "
            "land, sea, and cyber domains.",
            **{"compliance-level": "Full", "explanation": "Multi-domain fusion demonstrated on JADC2 programme with 15 sensor types."},
        )
        cr_004 = self._item(
            "compliance-response",
            "CR-004: Tactical Communications Gateway Compliance",
            "Full compliance. Our tactical gateway supports SATCOM, HF, "
            "VHF/UHF, and wideband links with automatic link management "
            "and dynamic bandwidth allocation.",
            **{"compliance-level": "Full", "explanation": "Gateway fielded on AFATDS programme supporting 8 simultaneous link types."},
        )
        cr_005 = self._item(
            "compliance-response",
            "CR-005: Link 16/JREAP Integration Compliance",
            "Full compliance. Our Link 16 interface supports MIDS-JTRS "
            "terminals and JREAP-C encapsulation tested in joint exercises.",
            **{"compliance-level": "Full", "explanation": "Link 16 integration verified during Talisman Sabre 2023 joint exercise."},
        )
        cr_006 = self._item(
            "compliance-response",
            "CR-006: Coalition Data Sharing Compliance",
            "Full compliance. Our cross-domain solution supports Five Eyes "
            "and NATO data sharing with configurable release policies.",
            **{"compliance-level": "Full", "explanation": "Coalition data sharing delivered on NATO ACCS Interface Development contract."},
        )
        cr_007 = self._item(
            "compliance-response",
            "CR-007: RMF Authorization Compliance",
            "Full compliance. Our RMF team has achieved 12 ATOs in the past "
            "five years including IL-5 and IL-6 environments.",
            **{"compliance-level": "Full", "explanation": "ATO achieved on GCCS-J Modernization within 9 months of RMF initiation."},
        )
        cr_008 = self._item(
            "compliance-response",
            "CR-008: Zero Trust Architecture Compliance",
            "Full compliance. Our zero-trust implementation follows DoD ZTA "
            "Reference Architecture v2.0 with continuous authentication and "
            "micro-segmentation.",
            **{"compliance-level": "Full", "explanation": "Zero-trust architecture piloted on JADC2 programme per DoD CIO guidance."},
        )
        cr_009 = self._item(
            "compliance-response",
            "CR-009: STIG Compliance Compliance",
            "Full compliance. All components are STIG-hardened with automated "
            "compliance scanning via ACAS and HBSS integration.",
            **{"compliance-level": "Full", "explanation": "100% STIG compliance maintained on GCCS-J with zero Category I findings."},
        )
        cr_010 = self._item(
            "compliance-response",
            "CR-010: Identity Federation Compliance",
            "Full compliance. RBAC federated with DoD ICAM supporting "
            "CAC/PIV and SAML 2.0 single sign-on.",
            **{"compliance-level": "Full", "explanation": "ICAM integration delivered on JADC2 with 5,000+ federated users."},
        )
        cr_011 = self._item(
            "compliance-response",
            "CR-011: System Availability Compliance",
            "Full compliance. Our architecture achieves 99.99% availability "
            "through active-active clustering with 15-second failover.",
            **{"compliance-level": "Full", "explanation": "99.995% availability demonstrated on GCCS-J over 24-month measurement period."},
        )
        cr_012 = self._item(
            "compliance-response",
            "CR-012: D-DIL Operations Compliance",
            "Full compliance. Store-and-forward and mesh networking capabilities "
            "maintain mission-critical functions during D-DIL conditions.",
            **{"compliance-level": "Full", "explanation": "D-DIL operations tested during AFATDS field exercise with 72-hour disconnected operation."},
        )
        cr_013 = self._item(
            "compliance-response",
            "CR-013: Scalability Compliance",
            "Partial compliance. Architecture supports 10,000 users but "
            "requires phased deployment with horizontal scaling. Full "
            "compliance achieved by IOC+6 months.",
            **{"compliance-level": "Partial", "explanation": "Current architecture tested to 7,500 concurrent users; horizontal scaling upgrade planned for Phase 2."},
        )
        cr_014 = self._item(
            "compliance-response",
            "CR-014: System Design Document Compliance",
            "Full compliance. SDD will be delivered per DI-MISC-81183B "
            "format with architecture views, interface specifications, and "
            "database design.",
            **{"compliance-level": "Full", "explanation": "SDD template and process proven on 4 prior DoD programmes."},
        )
        cr_015 = self._item(
            "compliance-response",
            "CR-015: Software Test Report Compliance",
            "Full compliance. STR will be delivered per DI-IPSC-81439A "
            "with automated test execution reports from CI/CD pipeline.",
            **{"compliance-level": "Full", "explanation": "Automated STR generation from DevSecOps pipeline demonstrated on JADC2."},
        )
        cr_016 = self._item(
            "compliance-response",
            "CR-016: Cybersecurity Assessment Report Compliance",
            "Full compliance. CAR will be delivered per DI-MGMT-82163 "
            "including automated vulnerability scan results and POA&M.",
            **{"compliance-level": "Full", "explanation": "CAR process automated via continuous monitoring pipeline on GCCS-J."},
        )
        cr_017 = self._item(
            "compliance-response",
            "CR-017: Training Program Compliance",
            "Partial compliance. ILT and CBT will be provided; VR-based "
            "training module requires additional development time beyond "
            "the baseline schedule.",
            **{"compliance-level": "Partial", "explanation": "ILT/CBT training programme delivered on AFATDS; VR module is new development."},
        )
        cr_018 = self._item(
            "compliance-response",
            "CR-018: Technology Refresh Plan Compliance",
            "Full compliance. Technology refresh plan will address hardware "
            "obsolescence, COTS currency, and open-standards migration over "
            "the 10-year lifecycle.",
            **{"compliance-level": "Full", "explanation": "Tech refresh methodology proven across 5 prior long-duration DoD programmes."},
        )
        self._compose(
            opp, cr_001, cr_002, cr_003, cr_004, cr_005, cr_006,
            cr_007, cr_008, cr_009, cr_010, cr_011, cr_012,
            cr_013, cr_014, cr_015, cr_016, cr_017, cr_018,
        )

        # ==============================================================
        # PAST PERFORMANCE CITATIONS (4)
        # ==============================================================
        pp_jadc2 = self._item(
            "past-performance",
            "JADC2 Integration \u2014 U.S. Army PEO C3T",
            "Joint All-Domain Command and Control integration programme "
            "delivering mission planning, COP, and sensor fusion capabilities "
            "to the U.S. Army. Achieved full operational capability on schedule "
            "with zero critical deficiencies at IOT&E.",
            **{
                "contract-number": "W56KGZ-19-C-0042",
                "agency": "U.S. Army PEO C3T",
                "contract-value": "$89,000,000",
                "period-of-performance": "2019\u20132024",
                "cpars-rating": "Exceptional",
            },
        )
        pp_gccs = self._item(
            "past-performance",
            "GCCS-J Modernization \u2014 DISA",
            "Modernization of the Global Command and Control System \u2014 Joint, "
            "migrating from legacy monolithic architecture to microservices-based "
            "cloud deployment with zero-trust security architecture.",
            **{
                "contract-number": "HC1028-17-D-0003",
                "agency": "DISA",
                "contract-value": "$142,000,000",
                "period-of-performance": "2017\u20132023",
                "cpars-rating": "Very Good",
            },
        )
        pp_afatds = self._item(
            "past-performance",
            "AFATDS Fire Control Upgrade \u2014 U.S. Army PEO M&S",
            "Upgrade of the Advanced Field Artillery Tactical Data System "
            "adding multi-domain fire control, Link 16 integration, and "
            "tactical communications gateway with D-DIL operations capability.",
            **{
                "contract-number": "W58RGZ-20-C-0118",
                "agency": "U.S. Army PEO M&S",
                "contract-value": "$67,000,000",
                "period-of-performance": "2020\u20132025",
                "cpars-rating": "Exceptional",
            },
        )
        pp_nato = self._item(
            "past-performance",
            "NATO ACCS Interface Development \u2014 NATO C3 Agency",
            "Development of the interface layer between the NATO Air Command "
            "and Control System and national C2 systems, enabling Five Eyes "
            "and NATO coalition data sharing with cross-domain guard.",
            **{
                "contract-number": "NATO-IFB-CO-15671-ACCS",
                "agency": "NATO C3 Agency",
                "contract-value": "$34,000,000",
                "period-of-performance": "2021\u20132024",
                "cpars-rating": "Very Good",
            },
        )
        self._compose(vol_iii, pp_jadc2, pp_gccs, pp_afatds, pp_nato)

        # ==============================================================
        # PRICING ELEMENTS (6 CLINs)
        # ==============================================================
        clin_0001 = self._item(
            "pricing-element",
            "CLIN 0001: System Design & Development",
            "Firm-fixed-price effort covering system architecture design, "
            "software development, hardware integration, and initial system "
            "build through CDR.",
            **{"clin-number": "0001", "clin-type": "FFP", "value": "$78,000,000"},
        )
        clin_0002 = self._item(
            "pricing-element",
            "CLIN 0002: System Integration & Test",
            "Firm-fixed-price effort for system integration, developmental "
            "testing, operational testing support, and cybersecurity "
            "assessment through ATO.",
            **{"clin-number": "0002", "clin-type": "FFP", "value": "$52,000,000"},
        )
        clin_0003 = self._item(
            "pricing-element",
            "CLIN 0003: Cybersecurity Assessment & RMF Package",
            "Firm-fixed-price effort for RMF body of evidence development, "
            "security control assessment, penetration testing, and ATO "
            "package preparation.",
            **{"clin-number": "0003", "clin-type": "FFP", "value": "$18,000,000"},
        )
        clin_0004 = self._item(
            "pricing-element",
            "CLIN 0004: Training & Deployment",
            "Time-and-materials effort for operator and administrator "
            "training development, instructor-led training delivery, and "
            "site deployment across CONUS and OCONUS locations.",
            **{"clin-number": "0004", "clin-type": "T&M", "value": "$24,000,000"},
        )
        clin_0005 = self._item(
            "pricing-element",
            "CLIN 0005: Sustainment & Operations Support",
            "Cost-plus-fixed-fee effort for 5-year sustainment including "
            "help desk, software maintenance, hardware refresh, and "
            "operations support at government facilities.",
            **{"clin-number": "0005", "clin-type": "CPFF", "value": "$65,000,000"},
        )
        clin_0006 = self._item(
            "pricing-element",
            "CLIN 0006: Data Rights & Technical Data Packages",
            "Firm-fixed-price for delivery of technical data packages, "
            "unlimited government purpose rights for all developed software, "
            "and COTS license transfers.",
            **{"clin-number": "0006", "clin-type": "FFP", "value": "$13,000,000"},
        )
        self._compose(vol_iv, clin_0001, clin_0002, clin_0003, clin_0004, clin_0005, clin_0006)

        # ==============================================================
        # WIN THEMES (5)
        # ==============================================================
        wt_jadc2 = self._item(
            "win-theme",
            "Proven JADC2 Integration at Scale",
            "Our team has delivered the only operational JADC2 integration "
            "at theatre scale, fusing 15 sensor types across 4 domains with "
            "proven mission planning and COP capabilities.",
            **{"theme-category": "Technical"},
        )
        wt_zt = self._item(
            "win-theme",
            "Zero-Trust Cyber Architecture \u2014 RMF Day-One Ready",
            "Our zero-trust architecture has achieved ATO in under 9 months "
            "on two prior programmes, reducing cyber risk and accelerating "
            "time to fielding.",
            **{"theme-category": "Technical"},
        )
        wt_devsecops = self._item(
            "win-theme",
            "Agile DevSecOps with Continuous ATO",
            "Our DevSecOps pipeline delivers continuous ATO through automated "
            "security scanning, STIG compliance checking, and vulnerability "
            "management integrated into every sprint.",
            **{"theme-category": "Management"},
        )
        wt_coalition = self._item(
            "win-theme",
            "Coalition Interoperability \u2014 Five Eyes & NATO Proven",
            "Our NATO ACCS integration provides proven Five Eyes and NATO "
            "coalition data sharing with cross-domain guard and configurable "
            "release policies.",
            **{"theme-category": "Past Performance"},
        )
        wt_cost = self._item(
            "win-theme",
            "20% Lower Lifecycle Cost via Open Standards",
            "Our open-standards architecture reduces vendor lock-in and "
            "enables competitive sustainment, delivering 20% lower total "
            "cost of ownership over the 10-year programme lifecycle.",
            **{"theme-category": "Cost"},
        )
        self._compose(opp, wt_jadc2, wt_zt, wt_devsecops, wt_coalition, wt_cost)

        # ==============================================================
        # COMPETITORS (3)
        # ==============================================================
        comp_raytheon = self._item(
            "competitor",
            "Raytheon \u2014 ELCAN C2 Suite",
            "Raytheon is the incumbent on the predecessor programme with "
            "deep customer relationships at PEO C3T. Their ELCAN C2 suite "
            "is fielded but aging.",
            **{
                "strength": "Incumbent on predecessor programme with established customer relationships and fielded baseline.",
                "weakness": "Legacy monolithic architecture with high technical debt; 18-month ATO timeline on last programme.",
                "win-probability": "High",
            },
        )
        comp_l3 = self._item(
            "competitor",
            "L3Harris \u2014 C4ISR Command Platform",
            "L3Harris brings strong tactical radio integration from their "
            "JTRS programme and a modern C4ISR platform with good sensor "
            "fusion capabilities.",
            **{
                "strength": "Strong tactical radio integration from JTRS programme; good sensor fusion capabilities.",
                "weakness": "Limited coalition interoperability experience; no prior cross-domain solution deployment at scale.",
                "win-probability": "Medium",
            },
        )
        comp_palantir = self._item(
            "competitor",
            "Palantir \u2014 Gotham Defense",
            "Palantir offers a modern data fabric and AI/ML analytics engine "
            "with strong data integration capabilities, but limited DoD C2 "
            "programme-of-record experience.",
            **{
                "strength": "Modern data fabric and AI/ML analytics engine with rapid integration capabilities.",
                "weakness": "No prior DoD C2 programme of record; limited understanding of DoD acquisition process and CDRL requirements.",
                "win-probability": "Low",
            },
        )
        self._compose(opp, comp_raytheon, comp_l3, comp_palantir)

        # ==============================================================
        # GATE REVIEWS (3)
        # ==============================================================
        gr_pink = self._item(
            "gate-review",
            "Pink Team \u2014 Outline Review",
            "Pink team review of proposal outlines, compliance matrix, "
            "and win theme assignments. Focus on completeness and "
            "responsiveness to all RFP requirements.",
            **{"review-type": "Pink Team", "outcome": "Pass with Comments"},
        )
        gr_red = self._item(
            "gate-review",
            "Red Team \u2014 Full Draft Review",
            "Red team review of the full proposal draft by independent "
            "reviewers simulating the government evaluation team. Scored "
            "against Section M evaluation criteria.",
            **{"review-type": "Red Team", "outcome": "Not Conducted"},
        )
        gr_gold = self._item(
            "gate-review",
            "Gold Team \u2014 Final Review",
            "Gold team final review of the production-ready proposal "
            "focusing on compliance, pricing consistency, and executive "
            "summary quality.",
            **{"review-type": "Gold Team", "outcome": "Not Conducted"},
        )
        self._compose(opp, gr_pink, gr_red, gr_gold)

        # ==============================================================
        # DEMO SCENARIOS (4)
        # ==============================================================
        ds_001 = self._item(
            "demo-scenario",
            "DS-001: Joint Mission Planning Workflow",
            "End-to-end demonstration of joint mission planning including "
            "situation assessment, COA development with wargaming, collaborative "
            "planning across echelons, and automated order generation.",
            **{"duration": "45 minutes", "status": "Rehearsed"},
        )
        ds_002 = self._item(
            "demo-scenario",
            "DS-002: COP Multi-Sensor Fusion",
            "Real-time demonstration of common operating picture with multi-domain "
            "sensor fusion showing track correlation from satellite imagery, "
            "radar, SIGINT, and ground sensors on a unified display.",
            **{"duration": "30 minutes", "status": "Planned"},
        )
        ds_003 = self._item(
            "demo-scenario",
            "DS-003: Degraded Communications Failover",
            "Demonstration of D-DIL operations capability showing automatic "
            "failover from SATCOM to mesh networking, store-and-forward "
            "message handling, and graceful reconnection with data sync.",
            **{"duration": "30 minutes", "status": "Planned"},
        )
        ds_004 = self._item(
            "demo-scenario",
            "DS-004: Cyber Incident Response",
            "Demonstration of zero-trust security response including threat "
            "detection via continuous monitoring, automatic micro-segmentation "
            "isolation, and recovery with forensic logging.",
            **{"duration": "20 minutes", "status": "Planned"},
        )
        self._compose(opp, ds_001, ds_002, ds_003, ds_004)

        # ==============================================================
        # QUESTIONS (3)
        # ==============================================================
        q_001 = self._item(
            "question",
            "Q-001: JREAP-C vs JREAP-A Profile Requirement",
            "Request for clarification on whether the SOW 3.2.2 Link 16/JREAP "
            "requirement mandates JREAP-C only or also requires JREAP-A "
            "support for legacy system interoperability.",
            **{"response-status": "Submitted"},
        )
        q_002 = self._item(
            "question",
            "Q-002: GFE Availability for Link 16 Terminals",
            "Request for clarification on whether Link 16 MIDS-JTRS terminals "
            "will be provided as government-furnished equipment or must be "
            "included in the contractor's cost proposal.",
            **{"response-status": "Submitted"},
        )
        q_003 = self._item(
            "question",
            "Q-003: IL-5 vs IL-6 Cloud Hosting Requirement",
            "Request for clarification on the required impact level for "
            "cloud hosting. SOW 3.4.1 references IL-5 but the Cybersecurity "
            "Assessment Report CDRL implies IL-6 for classified data.",
            **{"response-status": "Draft"},
        )
        self._compose(opp, q_001, q_002, q_003)

        # ==============================================================
        # RISKS (5)
        # ==============================================================
        risk_001 = self._item(
            "risk",
            "R-001: Competitor Incumbency Advantage",
            "Raytheon's incumbent status on the predecessor programme gives "
            "them established customer relationships and deep understanding "
            "of operational requirements that may bias the evaluation.",
            **{"severity": "High", "likelihood": "High", "risk-area": "Competitive"},
        )
        risk_002 = self._item(
            "risk",
            "R-002: RMF Authorization Timeline Risk",
            "The RMF authorization process may take longer than planned due "
            "to evolving NIST 800-53 Rev 5 control requirements and limited "
            "assessor availability at the authorizing official's office.",
            **{"severity": "High", "likelihood": "Medium", "risk-area": "Schedule"},
        )
        risk_003 = self._item(
            "risk",
            "R-003: COTS License Cost Escalation",
            "Key COTS components (database, middleware, monitoring tools) may "
            "experience licence cost increases during the 10-year programme "
            "lifecycle, eroding the cost basis of estimate.",
            **{"severity": "Medium", "likelihood": "Medium", "risk-area": "Cost"},
        )
        risk_004 = self._item(
            "risk",
            "R-004: Coalition Data-Sharing Policy Delays",
            "Changes in coalition data-sharing agreements or cross-domain "
            "solution accreditation policies may delay the coalition "
            "interoperability capability delivery.",
            **{"severity": "Medium", "likelihood": "Low", "risk-area": "Technical"},
        )
        risk_005 = self._item(
            "risk",
            "R-005: Key Personnel Availability",
            "Critical key personnel identified in the proposal may become "
            "unavailable due to competing programme demands or attrition "
            "before contract award.",
            **{"severity": "Low", "likelihood": "Low", "risk-area": "Schedule"},
        )
        self._compose(opp, risk_001, risk_002, risk_003, risk_004, risk_005)

        # ==============================================================
        # ACTION ITEMS (5)
        # ==============================================================
        ai_001 = self._item(
            "action-item",
            "AI-001: Complete RMF Body of Evidence for ATO Package",
            "Compile and review the full RMF body of evidence including "
            "security control assessment results, vulnerability scan reports, "
            "and plan of action and milestones for the ATO package.",
            **{"owner": "Cyber Lead", "status": "In Progress"},
        )
        ai_002 = self._item(
            "action-item",
            "AI-002: Secure Teaming Agreement with SubCo for Link 16 Expertise",
            "Finalise the teaming agreement with SubCo Inc. to provide Link 16 "
            "subject matter experts and MIDS-JTRS integration capability for "
            "the proposal and programme execution.",
            **{"owner": "BD Manager", "status": "Complete"},
        )
        ai_003 = self._item(
            "action-item",
            "AI-003: Rehearse Gold Team Demo Scenarios End-to-End",
            "Conduct full end-to-end rehearsals of all four demonstration "
            "scenarios with the solution team to ensure smooth delivery "
            "during the Gold Team review.",
            **{"owner": "Solution Architect", "status": "Open"},
        )
        ai_004 = self._item(
            "action-item",
            "AI-004: Finalize Basis of Estimate for CLIN 0001",
            "Complete the bottom-up basis of estimate for CLIN 0001 System "
            "Design & Development including labour hours, material costs, "
            "and subcontractor pricing.",
            **{"owner": "Pricing Manager", "status": "In Progress"},
        )
        ai_005 = self._item(
            "action-item",
            "AI-005: Obtain CEO Commitment Letter for Past Performance Volume",
            "Secure the CEO commitment letter confirming corporate backing, "
            "key personnel availability, and facility clearance for inclusion "
            "in the Past Performance volume.",
            **{"owner": "Capture Manager", "status": "Complete"},
        )
        self._compose(opp, ai_001, ai_002, ai_003, ai_004, ai_005)

        # ==============================================================
        # TRACE RELATIONS — responds_to
        # ==============================================================
        self._responds_to(sec_1_1, rfp_001, rfp_011, rfp_013)
        self._responds_to(sec_1_2, rfp_001, rfp_002)
        self._responds_to(sec_1_3, rfp_002, rfp_003)
        self._responds_to(sec_1_4, rfp_004, rfp_005, rfp_006)
        self._responds_to(sec_1_5, rfp_007, rfp_008, rfp_009, rfp_010)
        self._responds_to(sec_1_6, rfp_014, rfp_015, rfp_016)
        self._responds_to(sec_2_1, rfp_017, rfp_018)
        self._responds_to(sec_2_4, rfp_011, rfp_012)

        # ==============================================================
        # TRACE RELATIONS — evidenced_by
        # ==============================================================
        # C2-related compliance responses evidenced by JADC2 and GCCS-J
        self._evidenced_by(cr_001, pp_jadc2)
        self._evidenced_by(cr_002, pp_gccs)
        self._evidenced_by(cr_003, pp_jadc2)
        self._evidenced_by(cr_004, pp_afatds)
        self._evidenced_by(cr_005, pp_jadc2)
        self._evidenced_by(cr_006, pp_nato)
        self._evidenced_by(cr_007, pp_gccs)
        self._evidenced_by(cr_008, pp_jadc2)
        self._evidenced_by(cr_009, pp_gccs)
        self._evidenced_by(cr_010, pp_jadc2)
        self._evidenced_by(cr_011, pp_gccs)
        self._evidenced_by(cr_012, pp_afatds)
        self._evidenced_by(cr_013, pp_gccs)
        self._evidenced_by(cr_014, pp_jadc2)
        self._evidenced_by(cr_015, pp_jadc2)
        self._evidenced_by(cr_016, pp_gccs)
        self._evidenced_by(cr_017, pp_afatds)
        self._evidenced_by(cr_018, pp_nato)

        # ==============================================================
        # TRACE RELATIONS — demonstrates
        # ==============================================================
        self._demonstrates(ds_001, rfp_001, rfp_002)
        self._demonstrates(ds_002, rfp_002, rfp_003)
        self._demonstrates(ds_003, rfp_004, rfp_012)
        self._demonstrates(ds_004, rfp_007, rfp_008, rfp_009)

        # ==============================================================
        # TRACE RELATIONS — counters
        # ==============================================================
        # JADC2 theme counters Palantir (no prior C2 PoR)
        self._counters(wt_jadc2, comp_palantir)
        # Zero-Trust counters Raytheon (legacy architecture, slow ATO)
        self._counters(wt_zt, comp_raytheon)
        # DevSecOps counters Raytheon (legacy monolithic)
        self._counters(wt_devsecops, comp_raytheon)
        # Coalition counters L3Harris (limited coalition interop)
        self._counters(wt_coalition, comp_l3)
        # Cost counters all (open standards vs vendor lock-in)
        self._counters(wt_cost, comp_raytheon)
        self._counters(wt_cost, comp_l3)

        # ==============================================================
        # TRACE RELATIONS — prices
        # ==============================================================
        self._prices(clin_0001, rfp_001, rfp_002, rfp_003)
        self._prices(clin_0002, rfp_011, rfp_012, rfp_013)
        self._prices(clin_0003, rfp_007, rfp_008, rfp_009)
        self._prices(clin_0004, rfp_017)
        self._prices(clin_0005, rfp_011, rfp_018)
        self._prices(clin_0006, rfp_014, rfp_015, rfp_016)

        # ==============================================================
        # TRACE RELATIONS — clarifies
        # ==============================================================
        self._clarifies(q_001, rfp_005)
        self._clarifies(q_002, rfp_005)
        self._clarifies(q_003, rfp_011)

        # ==============================================================
        # TRACE RELATIONS — mitigates
        # ==============================================================
        self._mitigates(ai_001, risk_002)
        self._mitigates(ai_002, risk_004)
        self._mitigates(ai_004, risk_003)

        # ==============================================================
        # MATRICES (5)
        # ==============================================================

        # 1. RFP Compliance Matrix
        self._matrix(
            name="RFP Compliance Matrix",
            description=(
                "Traces each RFP requirement to the proposal sections that "
                "respond to it and the demo scenarios that demonstrate it."
            ),
            columns=[
                {
                    "label": "RFP Requirement",
                    "seed_item_type_slug": "rfp-requirement",
                },
                {
                    "label": "Proposal Sections",
                    "relation_name": "responds_to",
                    "direction": MatrixSource.Direction.INCOMING,
                },
                {
                    "label": "Demo Scenarios",
                    "relation_name": "demonstrates",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

        # 2. Past Performance Traceability
        self._matrix(
            name="Past Performance Traceability",
            description=(
                "Traces each compliance response to the past performance "
                "citation that provides evidence."
            ),
            columns=[
                {
                    "label": "Compliance Response",
                    "seed_item_type_slug": "compliance-response",
                },
                {
                    "label": "Evidenced By",
                    "relation_name": "evidenced_by",
                    "direction": MatrixSource.Direction.OUTGOING,
                },
            ],
        )

        # 3. Competitive Win Theme Matrix
        self._matrix(
            name="Competitive Win Theme Matrix",
            description=(
                "Maps each win theme to the competitors it is designed "
                "to counter."
            ),
            columns=[
                {
                    "label": "Win Theme",
                    "seed_item_type_slug": "win-theme",
                },
                {
                    "label": "Counters Competitor",
                    "relation_name": "counters",
                    "direction": MatrixSource.Direction.OUTGOING,
                },
            ],
        )

        # 4. Pricing to Requirements Traceability
        self._matrix(
            name="Pricing to Requirements Traceability",
            description=(
                "Traces each pricing element (CLIN) to the RFP requirements "
                "it prices."
            ),
            columns=[
                {
                    "label": "Pricing Element",
                    "seed_item_type_slug": "pricing-element",
                },
                {
                    "label": "Prices Requirement",
                    "relation_name": "prices",
                    "direction": MatrixSource.Direction.OUTGOING,
                },
            ],
        )

        # 5. Risk Mitigation Matrix
        self._matrix(
            name="Risk Mitigation Matrix",
            description=(
                "Traces each risk to the action items that mitigate it."
            ),
            columns=[
                {
                    "label": "Risk",
                    "seed_item_type_slug": "risk",
                },
                {
                    "label": "Mitigated By",
                    "relation_name": "mitigates",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

    def _setup_enterprise_sales_schema(self, admin):
        """
        Create item types, custom fields, custom relation types, and
        document templates for the Enterprise Software Deal vault.
        Populates ``self._types`` and ``self._relations``.
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
            ("Opportunity", "opportunity", "A top-level sales opportunity or deal.", "target"),
            ("Stakeholder", "stakeholder", "A key person involved in the buying decision.", "users"),
            ("Customer Requirement", "customer-requirement", "A requirement stated by the customer, typically from an RFP or discovery session.", "file-text"),
            ("Solution Component", "solution-component", "A product module or capability offered to address customer needs.", "puzzle"),
            ("Proposal Section", "proposal-section", "A section of the sales proposal document.", "book-open"),
            ("Security Response", "security-response", "A response to a security or compliance questionnaire item.", "shield-check"),
            ("POC Scenario", "poc-scenario", "A proof-of-concept scenario designed to validate a customer requirement.", "play"),
            ("Objection", "objection", "A customer objection or concern raised during the sales process.", "message-circle-warning"),
            ("Talking Point", "talking-point", "A prepared response or message to address an objection or concern.", "message-square"),
            ("Competitor", "competitor", "A competing vendor or product in the deal.", "swords"),
            ("Risk", "risk", "A risk that could jeopardise the deal outcome.", "alert-triangle"),
            ("Action Item", "action-item", "A task or action to be completed by the deal team.", "circle-check"),
            ("Meeting Note", "meeting-note", "Notes from a customer or internal meeting.", "notebook-pen"),
            ("Integration", "integration", "A system integration required for the solution deployment.", "plug"),
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
            # opportunity
            ("opportunity", "ARR Value", "arr-value", "text", False, {}),
            ("opportunity", "Stage", "stage", "choice", False, {"choices": ["Discovery", "Qualification", "POC", "Proposal", "Negotiation", "Closed Won", "Closed Lost"]}),
            ("opportunity", "Close Date", "close-date", "date", False, {}),
            ("opportunity", "Industry", "industry", "text", False, {}),
            # stakeholder
            ("stakeholder", "Role", "role", "text", False, {}),
            ("stakeholder", "Disposition", "disposition", "choice", False, {"choices": ["Champion", "Supporter", "Neutral", "Skeptic", "Blocker"]}),
            ("stakeholder", "Influence Level", "influence-level", "choice", False, {"choices": ["Decision Maker", "Strong Influence", "Some Influence", "Minimal"]}),
            ("stakeholder", "Department", "department", "text", False, {}),
            # customer-requirement
            ("customer-requirement", "Category", "category", "choice", False, {"choices": ["Functional", "Security", "Integration", "Performance", "Compliance", "Support"]}),
            ("customer-requirement", "Priority", "priority", "choice", False, {"choices": ["Must Have", "Should Have", "Nice to Have"]}),
            ("customer-requirement", "Source", "source", "text", False, {}),
            # solution-component
            ("solution-component", "Module", "module", "text", False, {}),
            ("solution-component", "Availability", "availability", "choice", False, {"choices": ["GA", "Beta", "Roadmap", "Custom Dev"]}),
            # proposal-section
            ("proposal-section", "Section Number", "section-number", "text", False, {}),
            ("proposal-section", "Author", "author", "text", False, {}),
            ("proposal-section", "Status", "status", "choice", False, {"choices": ["Not Started", "Draft", "Review", "Final"]}),
            # security-response
            ("security-response", "Framework", "framework", "choice", False, {"choices": ["SOC 2 Type II", "ISO 27001", "GDPR", "PCI DSS", "NIST CSF", "Other"]}),
            ("security-response", "Compliance Status", "compliance-status", "choice", False, {"choices": ["Compliant", "Partial", "Planned", "N-A"]}),
            # poc-scenario
            ("poc-scenario", "Success Criteria", "success-criteria", "text", False, {}),
            ("poc-scenario", "Duration", "duration", "text", False, {}),
            ("poc-scenario", "Status", "status", "choice", False, {"choices": ["Planned", "In Progress", "Passed", "Failed", "Deferred"]}),
            # objection
            ("objection", "Category", "category", "choice", False, {"choices": ["Price", "Security", "Migration", "Feature Gap", "Vendor Risk", "Timeline"]}),
            ("objection", "Severity", "severity", "choice", False, {"choices": ["Deal Breaker", "Major", "Minor"]}),
            # talking-point
            ("talking-point", "Audience", "audience", "text", False, {}),
            # competitor
            ("competitor", "Product", "product", "text", False, {}),
            ("competitor", "Strength", "strength", "text", False, {}),
            ("competitor", "Weakness", "weakness", "text", False, {}),
            ("competitor", "Incumbency", "incumbency", "choice", False, {"choices": ["Incumbent", "Also Bidding", "Preferred Alternate"]}),
            # risk
            ("risk", "Severity", "severity", "choice", False, {"choices": ["Low", "Medium", "High", "Critical"]}),
            ("risk", "Likelihood", "likelihood", "choice", False, {"choices": ["Low", "Medium", "High"]}),
            ("risk", "Risk Area", "risk-area", "choice", False, {"choices": ["Technical", "Commercial", "Competitive", "Timeline", "Security"]}),
            # action-item
            ("action-item", "Owner", "owner", "text", False, {}),
            ("action-item", "Due Date", "due-date", "date", False, {}),
            ("action-item", "Status", "status", "choice", False, {"choices": ["Open", "In Progress", "Complete", "Blocked"]}),
            # meeting-note
            ("meeting-note", "Meeting Date", "meeting-date", "date", False, {}),
            ("meeting-note", "Attendees", "attendees", "text", False, {}),
            ("meeting-note", "Meeting Type", "meeting-type", "choice", False, {"choices": ["Discovery", "Demo", "Technical", "Executive", "Negotiation", "Internal"]}),
            # integration
            ("integration", "System", "system", "text", False, {}),
            ("integration", "Protocol", "protocol", "choice", False, {"choices": ["REST API", "SFTP", "JDBC", "OAuth-SAML", "Webhook", "Custom"]}),
            ("integration", "Complexity", "complexity", "choice", False, {"choices": ["Low", "Medium", "High"]}),
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
                "name": "addresses",
                "forward_label": "addresses",
                "reverse_label": "is addressed by",
                "description": "A solution component addresses a customer requirement.",
                "source_item_type": self._types["solution-component"],
                "target_item_type": self._types["customer-requirement"],
            },
            {
                "kind": "trace",
                "name": "validates",
                "forward_label": "validates",
                "reverse_label": "is validated by",
                "description": "A POC scenario validates a customer requirement.",
                "source_item_type": self._types["poc-scenario"],
                "target_item_type": self._types["customer-requirement"],
            },
            {
                "kind": "trace",
                "name": "answers",
                "forward_label": "answers",
                "reverse_label": "is answered by",
                "description": "A security response answers a customer requirement.",
                "source_item_type": self._types["security-response"],
                "target_item_type": self._types["customer-requirement"],
            },
            {
                "kind": "trace",
                "name": "counters",
                "forward_label": "counters",
                "reverse_label": "is countered by",
                "description": "A talking point counters an objection.",
                "source_item_type": self._types["talking-point"],
                "target_item_type": self._types["objection"],
            },
            {
                "kind": "trace",
                "name": "competes_with",
                "forward_label": "competes with",
                "reverse_label": "is competed by",
                "description": "A competitor competes with a solution component.",
                "source_item_type": self._types["competitor"],
                "target_item_type": self._types["solution-component"],
            },
            {
                "kind": "trace",
                "name": "mitigates",
                "forward_label": "mitigates",
                "reverse_label": "is mitigated by",
                "description": "An action or control mitigates a risk.",
                "source_item_type": None,
                "target_item_type": None,
            },
            {
                "kind": "trace",
                "name": "influences",
                "forward_label": "influences",
                "reverse_label": "is influenced by",
                "description": "A stakeholder influences a customer requirement.",
                "source_item_type": self._types["stakeholder"],
                "target_item_type": self._types["customer-requirement"],
            },
            {
                "kind": "trace",
                "name": "covers",
                "forward_label": "covers",
                "reverse_label": "is covered by",
                "description": "A proposal section covers a customer requirement.",
                "source_item_type": self._types["proposal-section"],
                "target_item_type": self._types["customer-requirement"],
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
                "customer-requirement",
                "{{heading}} {{title}}\n\n"
                "| Field | Value |\n"
                "|---|---|\n"
                "| **Category** | {{category}} |\n"
                "| **Priority** | {{priority}} |\n"
                "| **Source** | {{source}} |\n"
                "| **Status** | {{status}} |\n"
                "| **Version** | {{current_version}} |\n\n"
                "{{description}}\n",
            ),
            (
                "security-response",
                "{{heading}} {{title}}\n\n"
                "**Framework:** {{framework}} | **Compliance Status:** {{compliance-status}}\n\n"
                "{{description}}\n",
            ),
            (
                "objection",
                "{{heading}} {{title}}\n\n"
                "**Category:** {{category}} | **Severity:** {{severity}}\n\n"
                "{{description}}\n",
            ),
            (
                "stakeholder",
                "{{heading}} {{title}}\n\n"
                "**Role:** {{role}} | **Disposition:** {{disposition}} | "
                "**Influence Level:** {{influence-level}} | **Department:** {{department}}\n\n"
                "{{description}}\n",
            ),
            (
                "poc-scenario",
                "{{heading}} {{title}}\n\n"
                "**Status:** {{status}} | **Duration:** {{duration}}\n\n"
                "**Success Criteria:** {{success-criteria}}\n\n"
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
    # Enterprise Software Deal example data
    # ------------------------------------------------------------------

    def _build_enterprise_deal(self):

        # ==============================================================
        # Shorthand helpers for this vault's relation types
        # ==============================================================
        def _addresses(source, *targets):
            for t in targets:
                self._rel("addresses", source, t)

        def _validates(source, *targets):
            for t in targets:
                self._rel("validates", source, t)

        def _answers(source, *targets):
            for t in targets:
                self._rel("answers", source, t)

        def _counters(source, *targets):
            for t in targets:
                self._rel("counters", source, t)

        def _competes_with(source, *targets):
            for t in targets:
                self._rel("competes_with", source, t)

        def _mitigates(source, *targets):
            for t in targets:
                self._rel("mitigates", source, t)

        def _influences(source, *targets):
            for t in targets:
                self._rel("influences", source, t)

        def _covers(source, *targets):
            for t in targets:
                self._rel("covers", source, t)

        # ==============================================================
        # OPPORTUNITY
        # ==============================================================
        opp = self._item(
            "opportunity",
            "Meridian Analytics \u2014 Global Trust Bank",
            "Enterprise analytics platform deal with Global Trust Bank, "
            "a top-20 global financial institution. The bank is replacing "
            "its legacy BI tooling and evaluating four vendors for a "
            "five-year enterprise license covering 5,000 users across "
            "retail banking, risk, and finance divisions.",
            **{"arr-value": "$2,400,000", "stage": "POC", "industry": "Financial Services"},
        )

        # ==============================================================
        # CUSTOMER REQUIREMENTS (standalone — not composed under opp)
        # ==============================================================
        cr01 = self._item(
            "customer-requirement",
            "CR-001: Heterogeneous Data Source Connectivity",
            "The platform must connect to at least five heterogeneous data "
            "sources (relational databases, cloud warehouses, flat files, "
            "APIs, and streaming) within four hours of initial configuration.",
            **{"category": "Functional", "priority": "Must Have", "source": "RFP Section 3.1"},
        )
        cr02 = self._item(
            "customer-requirement",
            "CR-002: Sub-Second Interactive Dashboards",
            "Interactive dashboards must deliver sub-second query response "
            "times on datasets up to 500 million rows, with no pre-aggregation "
            "required for common analytical queries.",
            **{"category": "Performance", "priority": "Must Have", "source": "RFP Section 3.2"},
        )
        cr03 = self._item(
            "customer-requirement",
            "CR-003: Self-Service Report Builder",
            "Business users without SQL or technical skills must be able to "
            "create, modify, and schedule reports through a drag-and-drop "
            "interface with guided data selection.",
            **{"category": "Functional", "priority": "Must Have", "source": "RFP Section 3.3"},
        )
        cr04 = self._item(
            "customer-requirement",
            "CR-004: SSO Integration with Okta via SAML 2.0",
            "The platform must integrate with the bank's existing Okta "
            "identity provider using SAML 2.0 for single sign-on, supporting "
            "just-in-time user provisioning and group-based role mapping.",
            **{"category": "Security", "priority": "Must Have", "source": "RFP Section 4.1"},
        )
        cr05 = self._item(
            "customer-requirement",
            "CR-005: Role-Based Access Control with Row-Level Security",
            "The platform must enforce role-based access control with "
            "row-level security policies that restrict data visibility "
            "by division, region, and classification level.",
            **{"category": "Security", "priority": "Must Have", "source": "RFP Section 4.2"},
        )
        cr06 = self._item(
            "customer-requirement",
            "CR-006: SOC 2 Type II Compliance",
            "The vendor must hold a current SOC 2 Type II attestation "
            "with no critical findings, covering all infrastructure and "
            "application services used to deliver the platform.",
            **{"category": "Compliance", "priority": "Must Have", "source": "RFP Section 4.3"},
        )
        cr07 = self._item(
            "customer-requirement",
            "CR-007: ISO 27001 Certification",
            "The vendor must maintain ISO 27001 certification for its "
            "information security management system, with the scope "
            "covering product development and cloud operations.",
            **{"category": "Compliance", "priority": "Must Have", "source": "RFP Section 4.4"},
        )
        cr08 = self._item(
            "customer-requirement",
            "CR-008: Data Encryption at Rest and in Transit",
            "All data must be encrypted at rest using AES-256 and in "
            "transit using TLS 1.2 or higher. Customer-managed encryption "
            "keys must be supported for data at rest.",
            **{"category": "Security", "priority": "Must Have", "source": "RFP Section 4.5"},
        )
        cr09 = self._item(
            "customer-requirement",
            "CR-009: REST API with OpenAPI Specification",
            "The platform must expose a comprehensive REST API documented "
            "with an OpenAPI 3.0 specification, enabling embedding of "
            "dashboards and programmatic data access.",
            **{"category": "Integration", "priority": "Must Have", "source": "RFP Section 5.1"},
        )
        cr10 = self._item(
            "customer-requirement",
            "CR-010: Automated Regulatory Report Generation",
            "The platform must support automated generation of regulatory "
            "reports including Basel III capital adequacy and CCAR stress "
            "testing outputs in prescribed formats.",
            **{"category": "Functional", "priority": "Should Have", "source": "RFP Section 3.4"},
        )
        cr11 = self._item(
            "customer-requirement",
            "CR-011: Data Lineage and Audit Trail",
            "Full data lineage must be tracked from source ingestion through "
            "transformation to final dashboard output, with an immutable "
            "audit trail of all data access and modifications.",
            **{"category": "Compliance", "priority": "Must Have", "source": "RFP Section 4.6"},
        )
        cr12 = self._item(
            "customer-requirement",
            "CR-012: 5,000 Concurrent Users with Sub-3s Page Load",
            "The platform must support 5,000 concurrent users with page "
            "load times under three seconds at the 95th percentile, "
            "verified through load testing.",
            **{"category": "Performance", "priority": "Must Have", "source": "RFP Section 6.1"},
        )
        cr13 = self._item(
            "customer-requirement",
            "CR-013: 99.9% SLA with DR/BC Procedures",
            "The vendor must guarantee a 99.9% uptime SLA with documented "
            "disaster recovery and business continuity procedures, including "
            "RPO < 1 hour and RTO < 4 hours.",
            **{"category": "Performance", "priority": "Must Have", "source": "RFP Section 6.2"},
        )
        cr14 = self._item(
            "customer-requirement",
            "CR-014: On-Premises Deployment Option",
            "The platform must support a hybrid cloud deployment model "
            "with an on-premises option for sensitive data workloads, "
            "managed through the same control plane as the cloud instance.",
            **{"category": "Integration", "priority": "Should Have", "source": "RFP Section 5.2"},
        )
        cr15 = self._item(
            "customer-requirement",
            "CR-015: Predictive Analytics and ML Integration",
            "The platform must support embedded predictive analytics "
            "with the ability to train, deploy, and monitor ML models "
            "on in-platform data without requiring a separate ML tool.",
            **{"category": "Functional", "priority": "Should Have", "source": "Dr. Priya Patel"},
        )
        cr16 = self._item(
            "customer-requirement",
            "CR-016: Mobile-Responsive Dashboards",
            "Dashboards must be fully responsive on iOS and Android "
            "devices, with touch-optimised interactions and offline "
            "caching for key executive summaries.",
            **{"category": "Functional", "priority": "Nice to Have", "source": "Lisa Zhang"},
        )
        cr17 = self._item(
            "customer-requirement",
            "CR-017: Migration Tooling from Existing BI Platform",
            "The vendor must provide automated migration tooling to "
            "convert existing Looker dashboards, data models, and "
            "scheduled reports to the new platform with minimal manual effort.",
            **{"category": "Integration", "priority": "Must Have", "source": "RFP Section 5.3"},
        )
        cr18 = self._item(
            "customer-requirement",
            "CR-018: White-Labeling for Customer-Facing Reports",
            "The platform must support white-label embedding so the bank "
            "can deliver branded analytics portals to its own customers "
            "without exposing the vendor's identity.",
            **{"category": "Functional", "priority": "Nice to Have", "source": "Lisa Zhang"},
        )

        # ==============================================================
        # SOLUTION COMPONENTS (composed under opportunity)
        # ==============================================================
        sc_data_fabric = self._item(
            "solution-component",
            "Meridian Data Fabric",
            "Real-time and batch data connectors supporting 200+ sources "
            "including relational databases, cloud warehouses, flat files, "
            "APIs, and streaming platforms. Zero-code configuration with "
            "automatic schema detection.",
            **{"module": "Data Integration", "availability": "GA"},
        )
        sc_dashboard = self._item(
            "solution-component",
            "Meridian Dashboard Studio",
            "Drag-and-drop dashboard builder with 50+ visualisation types, "
            "sub-second query engine, responsive layouts, and collaborative "
            "editing. Supports parameterised filters and drill-through navigation.",
            **{"module": "Visualization", "availability": "GA"},
        )
        sc_ml = self._item(
            "solution-component",
            "Meridian ML Insights",
            "Embedded ML models and predictive analytics engine with "
            "AutoML capabilities, model versioning, and one-click deployment "
            "to production dashboards. Supports Python and R notebooks.",
            **{"module": "Analytics", "availability": "GA"},
        )
        sc_admin = self._item(
            "solution-component",
            "Meridian Admin Console",
            "SSO, RBAC, and tenant management console with support for "
            "SAML 2.0, OIDC, SCIM provisioning, row-level security policies, "
            "and granular permission templates.",
            **{"module": "Administration", "availability": "GA"},
        )
        sc_api = self._item(
            "solution-component",
            "Meridian API Gateway",
            "REST and GraphQL APIs with OpenAPI 3.0 documentation, "
            "rate limiting, API key management, and webhook support. "
            "Enables programmatic dashboard creation and data access.",
            **{"module": "Developer Platform", "availability": "GA"},
        )
        sc_embed = self._item(
            "solution-component",
            "Meridian Embedded Analytics",
            "White-label embed SDK for React, Angular, and vanilla JS. "
            "Supports iframe and native component embedding with "
            "theme customisation and domain whitelisting.",
            **{"module": "Embedding", "availability": "GA"},
        )
        sc_catalog = self._item(
            "solution-component",
            "Meridian Data Catalog",
            "Metadata management, data lineage visualisation, impact "
            "analysis, and automated data classification. Integrates "
            "with the Data Fabric for end-to-end governance.",
            **{"module": "Governance", "availability": "Beta"},
        )
        sc_compliance = self._item(
            "solution-component",
            "Meridian Compliance Module",
            "Audit trail, regulatory report templates, data retention "
            "policies, and compliance dashboards. Pre-built templates "
            "for Basel III, CCAR, and SOX reporting.",
            **{"module": "Compliance", "availability": "GA"},
        )
        self._compose(
            opp,
            sc_data_fabric, sc_dashboard, sc_ml, sc_admin,
            sc_api, sc_embed, sc_catalog, sc_compliance,
        )

        # ==============================================================
        # PROPOSAL SECTIONS (composed under opportunity)
        # ==============================================================
        ps_exec = self._item(
            "proposal-section",
            "Executive Summary",
            "High-level overview of Meridian Analytics' value proposition "
            "for Global Trust Bank, including strategic alignment, key "
            "differentiators, and expected business outcomes.",
            **{"section-number": "1", "status": "Final"},
        )
        ps_solution = self._item(
            "proposal-section",
            "Solution Overview",
            "Detailed description of the Meridian platform architecture, "
            "modules, deployment topology, and how each component maps "
            "to Global Trust Bank's stated requirements.",
            **{"section-number": "2", "status": "Final"},
        )
        ps_security = self._item(
            "proposal-section",
            "Security & Compliance",
            "Comprehensive security posture overview including certifications, "
            "encryption standards, access controls, and compliance with "
            "financial services regulations.",
            **{"section-number": "3", "status": "Review"},
        )
        ps_impl = self._item(
            "proposal-section",
            "Implementation Plan",
            "Phased implementation roadmap covering data integration, "
            "dashboard migration, SSO configuration, UAT, and production "
            "go-live with detailed milestones and resource requirements.",
            **{"section-number": "4", "status": "Draft"},
        )
        ps_pricing = self._item(
            "proposal-section",
            "Pricing & Commercial Terms",
            "Pricing structure, volume tiers, payment terms, SLA "
            "commitments, and contract options including annual and "
            "multi-year agreements.",
            **{"section-number": "5", "status": "Draft"},
        )
        self._compose(opp, ps_exec, ps_solution, ps_security, ps_impl, ps_pricing)

        # -- Solution Overview sub-items --
        info_arch = self._item(
            "information",
            "Platform Architecture",
            "Meridian Analytics is built on a cloud-native microservices "
            "architecture deployed on AWS and Azure. The platform uses a "
            "distributed query engine for sub-second performance and a "
            "multi-tenant data isolation model.",
        )
        info_modules = self._item(
            "information",
            "Module Overview",
            "The platform comprises eight integrated modules: Data Fabric, "
            "Dashboard Studio, ML Insights, Admin Console, API Gateway, "
            "Embedded Analytics, Data Catalog, and Compliance Module.",
        )
        self._compose(ps_solution, info_arch, info_modules)

        # -- Implementation Plan sub-items --
        info_timeline = self._item(
            "information",
            "Implementation Timeline",
            "The implementation follows a four-phase approach over 14 weeks: "
            "Phase 1 (Weeks 1\u20133) \u2014 Infrastructure and SSO setup; "
            "Phase 2 (Weeks 4\u20138) \u2014 Data integration and dashboard migration; "
            "Phase 3 (Weeks 9\u201311) \u2014 UAT and training; "
            "Phase 4 (Weeks 12\u201314) \u2014 Production rollout and hypercare.",
        )
        info_milestones = self._item(
            "information",
            "Key Milestones",
            "M1: Environment provisioned and SSO live (Week 3). "
            "M2: Core dashboards migrated and validated (Week 8). "
            "M3: UAT sign-off from all divisions (Week 11). "
            "M4: Production go-live with 99.9% SLA active (Week 14).",
        )
        self._compose(ps_impl, info_timeline, info_milestones)

        # ==============================================================
        # SECURITY RESPONSES (composed under Security & Compliance)
        # ==============================================================
        sec_soc2 = self._item(
            "security-response",
            "SOC 2 Type II Compliance",
            "Meridian holds a current SOC 2 Type II attestation issued "
            "by Deloitte, covering all five trust service criteria. The "
            "most recent audit completed with zero critical findings.",
            **{"framework": "SOC 2 Type II", "compliance-status": "Compliant"},
        )
        sec_iso = self._item(
            "security-response",
            "ISO 27001 Certification",
            "Meridian's ISMS is certified to ISO 27001:2022 by BSI, "
            "with scope covering product development, cloud operations, "
            "and customer support functions.",
            **{"framework": "ISO 27001", "compliance-status": "Compliant"},
        )
        sec_encrypt = self._item(
            "security-response",
            "Data Encryption Standards",
            "All data is encrypted at rest using AES-256 with customer-managed "
            "keys via AWS KMS / Azure Key Vault. Data in transit is protected "
            "by TLS 1.3 with certificate pinning for API connections.",
            **{"framework": "NIST CSF", "compliance-status": "Compliant"},
        )
        sec_sso = self._item(
            "security-response",
            "SSO via SAML 2.0 and OIDC",
            "The platform supports SAML 2.0 and OpenID Connect for SSO "
            "integration with all major identity providers including Okta, "
            "Azure AD, and Ping Identity. JIT provisioning and SCIM are supported.",
            **{"framework": "Other", "compliance-status": "Compliant"},
        )
        sec_rbac = self._item(
            "security-response",
            "RBAC with Row-Level Security",
            "Granular role-based access control with row-level security "
            "policies defined at the dataset level. Supports attribute-based "
            "rules using division, region, and classification tags.",
            **{"framework": "Other", "compliance-status": "Compliant"},
        )
        sec_pci = self._item(
            "security-response",
            "PCI DSS Alignment",
            "Meridian is aligned with PCI DSS v4.0 requirements for data "
            "handling and access control. Full PCI DSS certification is in "
            "progress with expected completion in Q3.",
            **{"framework": "PCI DSS", "compliance-status": "Partial"},
        )
        self._compose(ps_security, sec_soc2, sec_iso, sec_encrypt, sec_sso, sec_rbac, sec_pci)

        # ==============================================================
        # INTEGRATIONS (composed under Implementation Plan)
        # ==============================================================
        int_temenos = self._item(
            "integration",
            "Core Banking \u2014 Temenos T24",
            "Direct JDBC connectivity to Temenos T24 core banking system "
            "for real-time transaction data, account balances, and customer "
            "profiles. Requires VPN tunnel and database-level read replica.",
            **{"system": "Temenos T24", "protocol": "JDBC", "complexity": "High"},
        )
        int_snowflake = self._item(
            "integration",
            "Data Warehouse \u2014 Snowflake",
            "Native Snowflake connector using Snowflake's partner connect. "
            "Provides direct query pushdown for optimal performance on "
            "the bank's existing Snowflake Enterprise instance.",
            **{"system": "Snowflake", "protocol": "REST API", "complexity": "Low"},
        )
        int_okta = self._item(
            "integration",
            "Identity Provider \u2014 Okta",
            "SAML 2.0 and SCIM integration with the bank's Okta Universal "
            "Directory for SSO, automated user provisioning, and group-based "
            "role assignment.",
            **{"system": "Okta", "protocol": "OAuth-SAML", "complexity": "Medium"},
        )
        int_snow = self._item(
            "integration",
            "IT Service Management \u2014 ServiceNow",
            "REST API integration with ServiceNow for automated incident "
            "creation, change request workflows, and embedded analytics "
            "widgets within the ServiceNow portal.",
            **{"system": "ServiceNow", "protocol": "REST API", "complexity": "Low"},
        )
        int_bloomberg = self._item(
            "integration",
            "Market Data \u2014 Bloomberg Terminal",
            "Custom adapter for Bloomberg B-PIPE and SAPI data feeds, "
            "providing real-time market data ingestion for trading "
            "analytics and risk dashboards.",
            **{"system": "Bloomberg", "protocol": "Custom", "complexity": "High"},
        )
        self._compose(ps_impl, int_temenos, int_snowflake, int_okta, int_snow, int_bloomberg)

        # ==============================================================
        # POC SCENARIOS (composed under opportunity)
        # ==============================================================
        poc_pnl = self._item(
            "poc-scenario",
            "Real-Time P&L Dashboard",
            "Connect to the bank's Snowflake instance, ingest P&L data, "
            "and build an interactive profit-and-loss dashboard with "
            "sub-two-second refresh on drill-down queries.",
            **{
                "success-criteria": "Connect to Snowflake, build P&L dashboard, <2s refresh",
                "duration": "2 days",
                "status": "Passed",
            },
        )
        poc_self_service = self._item(
            "poc-scenario",
            "Self-Service Report Builder",
            "Demonstrate that a business user from the finance team can "
            "create a regulatory summary report without IT assistance "
            "using the drag-and-drop report builder.",
            **{
                "success-criteria": "Business user creates regulatory summary without IT",
                "duration": "1 day",
                "status": "Passed",
            },
        )
        poc_sso = self._item(
            "poc-scenario",
            "SSO + RBAC Enforcement",
            "Configure Okta SSO login and demonstrate row-level security "
            "filtering by division, ensuring users only see data for their "
            "assigned business unit.",
            **{
                "success-criteria": "Okta SSO login, row-level security filters by division",
                "duration": "1 day",
                "status": "In Progress",
            },
        )
        poc_reg = self._item(
            "poc-scenario",
            "Regulatory Report Automation",
            "Auto-generate a Basel III capital adequacy report from the "
            "bank's risk data warehouse, matching the prescribed regulatory "
            "output format.",
            **{
                "success-criteria": "Auto-generate Basel III capital adequacy report",
                "duration": "2 days",
                "status": "Planned",
            },
        )
        poc_api = self._item(
            "poc-scenario",
            "API Embed in Internal Portal",
            "Embed a live analytics chart into the bank's ServiceNow "
            "portal via iframe using the Meridian Embed SDK, with SSO "
            "passthrough authentication.",
            **{
                "success-criteria": "Embed live chart in ServiceNow portal via iframe",
                "duration": "1 day",
                "status": "Planned",
            },
        )
        poc_lineage = self._item(
            "poc-scenario",
            "Data Lineage & Audit Trail",
            "Trace data from the Temenos T24 source through ETL "
            "transformations in Snowflake to the final dashboard "
            "visualisation, demonstrating full lineage and audit trail.",
            **{
                "success-criteria": "Trace data from T24 source through transformations to dashboard",
                "duration": "1 day",
                "status": "Planned",
            },
        )
        self._compose(opp, poc_pnl, poc_self_service, poc_sso, poc_reg, poc_api, poc_lineage)

        # ==============================================================
        # STAKEHOLDERS (composed under opportunity)
        # ==============================================================
        sh_chen = self._item(
            "stakeholder",
            "Sarah Chen \u2014 Chief Financial Officer",
            "Executive sponsor and primary decision maker. Motivated by "
            "reducing time-to-insight for financial reporting and enabling "
            "self-service analytics across the finance organisation.",
            **{"role": "CFO", "disposition": "Champion", "influence-level": "Decision Maker", "department": "Finance"},
        )
        sh_williams = self._item(
            "stakeholder",
            "Marcus Williams \u2014 Chief Information Security Officer",
            "Key technical gatekeeper with veto authority on security and "
            "compliance matters. Requires thorough evidence of SOC 2, ISO 27001, "
            "and encryption standards before approving any vendor.",
            **{"role": "CISO", "disposition": "Blocker", "influence-level": "Strong Influence", "department": "Information Security"},
        )
        sh_patel = self._item(
            "stakeholder",
            "Dr. Priya Patel \u2014 Head of Data & Analytics",
            "Technical champion who manages the bank's existing analytics "
            "infrastructure. Advocates for modern data stack and embedded "
            "ML capabilities to replace legacy tooling.",
            **{"role": "Head of Data & Analytics", "disposition": "Supporter", "influence-level": "Strong Influence", "department": "Technology"},
        )
        sh_morrison = self._item(
            "stakeholder",
            "James Morrison \u2014 Head of Procurement",
            "Controls the commercial evaluation and contract negotiation. "
            "Focused on total cost of ownership, vendor stability, and "
            "favourable payment terms.",
            **{"role": "Head of Procurement", "disposition": "Neutral", "influence-level": "Decision Maker", "department": "Procurement"},
        )
        sh_zhang = self._item(
            "stakeholder",
            "Lisa Zhang \u2014 VP Retail Banking",
            "End-user champion representing the largest user base. Interested "
            "in mobile dashboards and customer-facing analytics for the "
            "retail banking division.",
            **{"role": "VP Retail Banking", "disposition": "Supporter", "influence-level": "Some Influence", "department": "Retail Banking"},
        )
        self._compose(opp, sh_chen, sh_williams, sh_patel, sh_morrison, sh_zhang)

        # ==============================================================
        # COMPETITORS (composed under opportunity)
        # ==============================================================
        comp_tableau = self._item(
            "competitor",
            "Tableau",
            "Market-leading visualisation platform with a large partner "
            "ecosystem. Strong in self-service analytics but expensive "
            "at scale with per-user pricing.",
            **{
                "product": "Tableau Cloud",
                "incumbency": "Also Bidding",
                "strength": "Market leader, massive ecosystem, deep visualisation library",
                "weakness": "Expensive at scale, weak real-time streaming, limited embedded ML",
            },
        )
        comp_powerbi = self._item(
            "competitor",
            "Microsoft Power BI",
            "Bundled with Microsoft 365, offering low entry cost and tight "
            "integration with the Microsoft ecosystem. Less capable on "
            "non-Microsoft data sources.",
            **{
                "product": "Power BI Premium",
                "incumbency": "Also Bidding",
                "strength": "Bundled with M365, low entry cost, familiar UI for business users",
                "weakness": "Limited on non-Microsoft data sources, weak governance and lineage",
            },
        )
        comp_looker = self._item(
            "competitor",
            "Looker",
            "Currently deployed at the bank with 200+ existing dashboards. "
            "Strong data modelling layer but uncertain roadmap following "
            "Google Cloud acquisition.",
            **{
                "product": "Looker Enterprise",
                "incumbency": "Incumbent",
                "strength": "Already deployed, 200+ existing dashboards, strong LookML modelling",
                "weakness": "Acquired by Google, uncertain roadmap, limited ML and predictive capabilities",
            },
        )
        comp_thoughtspot = self._item(
            "competitor",
            "ThoughtSpot",
            "AI-first analytics platform with natural language search. "
            "Innovative approach but limited traction in financial services "
            "with a smaller customer base.",
            **{
                "product": "ThoughtSpot One",
                "incumbency": "Also Bidding",
                "strength": "Natural language search, AI-first approach, strong search UX",
                "weakness": "Small customer base in financial services, limited regulatory reporting",
            },
        )
        self._compose(opp, comp_tableau, comp_powerbi, comp_looker, comp_thoughtspot)

        # ==============================================================
        # OBJECTIONS (composed under opportunity)
        # ==============================================================
        obj_migration = self._item(
            "objection",
            "Migration Risk from Looker",
            "The bank has 200+ Looker dashboards in production and is "
            "concerned about the effort, risk, and business disruption "
            "of migrating to a new platform.",
            **{"category": "Migration", "severity": "Major"},
        )
        obj_pricing = self._item(
            "objection",
            "Per-User Pricing Too Expensive at 5,000 Users",
            "At the stated per-user pricing, the five-year TCO for 5,000 "
            "users significantly exceeds the bank's budget allocation "
            "and competing vendor proposals.",
            **{"category": "Price", "severity": "Deal Breaker"},
        )
        obj_fedramp = self._item(
            "objection",
            "No FedRAMP Certification for Future Gov Contracts",
            "The bank's government banking division requires FedRAMP "
            "Moderate authorisation for any platform hosting government "
            "client data. Meridian does not yet hold this certification.",
            **{"category": "Feature Gap", "severity": "Minor"},
        )
        obj_vendor = self._item(
            "objection",
            "Meridian Is a Smaller Vendor \u2014 Business Continuity Concerns",
            "Procurement has flagged Meridian's smaller market presence "
            "compared to Tableau and Microsoft as a business continuity "
            "risk, citing concerns about long-term viability.",
            **{"category": "Vendor Risk", "severity": "Major"},
        )
        obj_timeline = self._item(
            "objection",
            "Implementation Timeline Exceeds Q3 Fiscal Deadline",
            "The proposed 14-week implementation timeline extends beyond "
            "the bank's Q3 fiscal year-end deadline, which is the budget "
            "commitment cutoff for this initiative.",
            **{"category": "Timeline", "severity": "Major"},
        )
        self._compose(opp, obj_migration, obj_pricing, obj_fedramp, obj_vendor, obj_timeline)

        # ==============================================================
        # TALKING POINTS (composed under opportunity)
        # ==============================================================
        tp_migration = self._item(
            "talking-point",
            "Automated Looker Migration Toolkit",
            "Meridian offers a purpose-built Looker Migration Toolkit that "
            "automatically converts LookML models, Explores, and dashboards "
            "to the Meridian format. In pilot migrations, 85% of dashboards "
            "converted without manual intervention.",
            **{"audience": "Dr. Priya Patel, James Morrison"},
        )
        tp_pricing = self._item(
            "talking-point",
            "Volume Tier Pricing at 5,000+ Users",
            "Meridian's Enterprise Volume Tier provides a 40% discount at "
            "the 5,000-user level, bringing the per-user cost below Power BI "
            "Premium when factoring in required add-ons for governance and "
            "embedded analytics.",
            **{"audience": "James Morrison, Sarah Chen"},
        )
        tp_vendor = self._item(
            "talking-point",
            "$50M Series D + 400 Enterprise Customers",
            "Meridian closed a $50M Series D led by Sequoia in Q4, reaching "
            "a $1.2B valuation. The company serves 400+ enterprise customers "
            "including 12 of the top 50 global banks, with 140% net revenue "
            "retention.",
            **{"audience": "James Morrison, Marcus Williams"},
        )
        tp_fedramp = self._item(
            "talking-point",
            "FedRAMP Moderate \u2014 In Process, Q2 Target",
            "Meridian's FedRAMP Moderate authorisation is in process with "
            "the 3PAO assessment underway. Expected authorisation by Q2, "
            "ahead of the bank's government division timeline.",
            **{"audience": "Marcus Williams"},
        )
        tp_timeline = self._item(
            "talking-point",
            "Phased Rollout: Core Dashboards Live in 8 Weeks",
            "A phased rollout plan delivers core P&L and risk dashboards "
            "in 8 weeks (within Q3), with remaining migration and advanced "
            "features completing in Phase 2 post-deadline. This meets the "
            "budget commitment requirement.",
            **{"audience": "Sarah Chen, Lisa Zhang"},
        )
        self._compose(opp, tp_migration, tp_pricing, tp_vendor, tp_fedramp, tp_timeline)

        # ==============================================================
        # RISKS (composed under opportunity)
        # ==============================================================
        risk_ciso = self._item(
            "risk",
            "CISO Blocks Deal Over SOC 2 Gap Finding",
            "Marcus Williams may block the deal if he identifies any gaps "
            "in the SOC 2 Type II report or if the bridge letter does not "
            "adequately address the Q1 remediation items.",
            **{"severity": "High", "likelihood": "High", "risk-area": "Security"},
        )
        risk_term = self._item(
            "risk",
            "Procurement Insists on 3-Year Term vs Annual",
            "James Morrison's procurement team may insist on a three-year "
            "commitment to secure volume pricing, which conflicts with "
            "Meridian's preference for annual contracts.",
            **{"severity": "Medium", "likelihood": "Medium", "risk-area": "Commercial"},
        )
        risk_poc = self._item(
            "risk",
            "POC Delayed by Bank IT Resource Constraints",
            "The bank's IT team is stretched across multiple projects and "
            "may not allocate sufficient resources for the POC environment "
            "setup, delaying the evaluation timeline.",
            **{"severity": "Medium", "likelihood": "High", "risk-area": "Timeline"},
        )
        risk_looker = self._item(
            "risk",
            "Looker Offers Aggressive Renewal Discount",
            "Google/Looker may offer an aggressive renewal discount with "
            "extended support commitments to retain the account, undermining "
            "the business case for switching to Meridian.",
            **{"severity": "High", "likelihood": "Medium", "risk-area": "Competitive"},
        )
        risk_budget = self._item(
            "risk",
            "Budget Reallocation Due to Pending M&A",
            "Rumours of a pending acquisition could trigger a company-wide "
            "budget freeze or reallocation, deferring the analytics platform "
            "decision indefinitely.",
            **{"severity": "Critical", "likelihood": "Low", "risk-area": "Commercial"},
        )
        self._compose(opp, risk_ciso, risk_term, risk_poc, risk_looker, risk_budget)

        # ==============================================================
        # ACTION ITEMS (composed under opportunity)
        # ==============================================================
        ai_exec = self._item(
            "action-item",
            "Schedule executive sponsor call \u2014 Sarah Chen + Meridian CEO",
            "Arrange a 30-minute call between Sarah Chen (CFO) and "
            "Meridian's CEO to discuss strategic partnership, long-term "
            "roadmap alignment, and executive sponsorship commitment.",
            **{"owner": "Account Executive", "status": "In Progress"},
        )
        ai_soc2 = self._item(
            "action-item",
            "Deliver SOC 2 bridge letter to Marcus Williams",
            "Send the SOC 2 Type II bridge letter addressing Q1 "
            "remediation items to Marcus Williams' security team for "
            "review prior to the next security assessment meeting.",
            **{"owner": "Security Lead", "status": "Complete"},
        )
        ai_migration = self._item(
            "action-item",
            "Prepare Looker migration assessment and effort estimate",
            "Analyse the bank's 200+ Looker dashboards, classify by "
            "complexity, and produce a detailed migration effort estimate "
            "with timeline and resource requirements.",
            **{"owner": "Solutions Engineer", "status": "In Progress"},
        )
        ai_poc = self._item(
            "action-item",
            "Run POC data connectivity test with Snowflake instance",
            "Execute the data connectivity POC against the bank's "
            "Snowflake sandbox environment to validate connector "
            "performance and query pushdown capabilities.",
            **{"owner": "Solutions Engineer", "status": "Complete"},
        )
        ai_pricing = self._item(
            "action-item",
            "Submit custom pricing model for 5,000-user tier",
            "Work with Deal Desk to model a custom volume pricing "
            "tier for 5,000 users that undercuts the competing Power BI "
            "and Tableau proposals on total cost of ownership.",
            **{"owner": "Deal Desk", "status": "Open"},
        )
        self._compose(opp, ai_exec, ai_soc2, ai_migration, ai_poc, ai_pricing)

        # ==============================================================
        # MEETING NOTES (composed under opportunity)
        # ==============================================================
        mn_discovery = self._item(
            "meeting-note",
            "Discovery Call \u2014 Initial Requirements Gathering",
            "First call with Global Trust Bank stakeholders to understand "
            "current analytics landscape, pain points with Looker, and "
            "high-level requirements for the replacement platform. Key "
            "takeaway: security and compliance are non-negotiable gates.",
            **{"meeting-date": "2026-01-15", "meeting-type": "Discovery", "attendees": "Sarah Chen, Dr. Priya Patel, Lisa Zhang"},
        )
        mn_technical = self._item(
            "meeting-note",
            "Technical Deep Dive with Data Team",
            "Deep dive into the bank's data architecture, Snowflake "
            "deployment, Temenos T24 integration requirements, and "
            "current ETL pipelines. Dr. Patel's team impressed by "
            "Data Fabric's zero-code connector approach.",
            **{"meeting-date": "2026-02-03", "meeting-type": "Technical", "attendees": "Dr. Priya Patel, 3x Data Engineers"},
        )
        mn_security = self._item(
            "meeting-note",
            "Security Review with CISO Office",
            "Formal security review with Marcus Williams and his team. "
            "Reviewed SOC 2 report, ISO 27001 certificate, encryption "
            "standards, and incident response procedures. CISO requested "
            "bridge letter for Q1 remediation items.",
            **{"meeting-date": "2026-02-18", "meeting-type": "Technical", "attendees": "Marcus Williams, 2x Security Analysts"},
        )
        mn_exec = self._item(
            "meeting-note",
            "Executive Alignment \u2014 CFO + VP Retail",
            "Executive alignment session with Sarah Chen and Lisa Zhang. "
            "Discussed phased rollout strategy, Q3 budget commitment "
            "timeline, and mobile dashboard requirements for the retail "
            "banking division.",
            **{"meeting-date": "2026-03-05", "meeting-type": "Executive", "attendees": "Sarah Chen, Lisa Zhang, Meridian CEO"},
        )
        self._compose(opp, mn_discovery, mn_technical, mn_security, mn_exec)

        # ==============================================================
        # TRACE RELATIONS
        # ==============================================================

        # Solution Components → addresses → Customer Requirements
        _addresses(sc_data_fabric, cr01, cr14)
        _addresses(sc_dashboard, cr02, cr03, cr16)
        _addresses(sc_ml, cr15)
        _addresses(sc_admin, cr04, cr05)
        _addresses(sc_api, cr09, cr18)
        _addresses(sc_embed, cr18)
        _addresses(sc_catalog, cr11)
        _addresses(sc_compliance, cr06, cr07, cr10, cr11)

        # POC Scenarios → validates → Customer Requirements
        _validates(poc_pnl, cr01, cr02)
        _validates(poc_self_service, cr03)
        _validates(poc_sso, cr04, cr05)
        _validates(poc_reg, cr10)
        _validates(poc_api, cr09, cr18)
        _validates(poc_lineage, cr11)

        # Security Responses → answers → Customer Requirements
        _answers(sec_soc2, cr06)
        _answers(sec_iso, cr07)
        _answers(sec_encrypt, cr08)
        _answers(sec_sso, cr04)
        _answers(sec_rbac, cr05)
        _answers(sec_pci, cr08)

        # Talking Points → counters → Objections (1:1)
        _counters(tp_migration, obj_migration)
        _counters(tp_pricing, obj_pricing)
        _counters(tp_vendor, obj_vendor)
        _counters(tp_fedramp, obj_fedramp)
        _counters(tp_timeline, obj_timeline)

        # Competitors → competes_with → Solution Components
        _competes_with(comp_tableau, sc_dashboard, sc_ml)
        _competes_with(comp_powerbi, sc_dashboard, sc_compliance)
        _competes_with(comp_looker, sc_dashboard, sc_catalog)
        _competes_with(comp_thoughtspot, sc_dashboard, sc_ml)

        # Stakeholders → influences → Customer Requirements
        _influences(sh_chen, cr02, cr10, cr13)
        _influences(sh_williams, cr04, cr05, cr06, cr07, cr08)
        _influences(sh_patel, cr01, cr03, cr11, cr15)
        _influences(sh_morrison, cr12, cr13, cr17)
        _influences(sh_zhang, cr03, cr16, cr18)

        # Proposal Sections → covers → Customer Requirements
        _covers(ps_exec, cr02, cr13)
        _covers(ps_solution, cr01, cr02, cr03, cr09, cr15, cr16, cr18)
        _covers(ps_security, cr04, cr05, cr06, cr07, cr08)
        _covers(ps_impl, cr14, cr17)
        _covers(ps_pricing, cr12, cr13)

        # Action Items → mitigates → Risks
        _mitigates(ai_exec, risk_looker)
        _mitigates(ai_soc2, risk_ciso)
        _mitigates(ai_migration, risk_looker)
        _mitigates(ai_poc, risk_poc)
        _mitigates(ai_pricing, risk_term)

        # ==============================================================
        # MATRICES
        # ==============================================================

        # 1. Requirements Coverage Matrix
        self._matrix(
            name="Requirements Coverage Matrix",
            description=(
                "Traces each customer requirement to the solution components "
                "that address it, POC scenarios that validate it, and proposal "
                "sections that cover it."
            ),
            columns=[
                {
                    "label": "Customer Requirement",
                    "seed_item_type_slug": "customer-requirement",
                },
                {
                    "label": "Solution Components",
                    "relation_name": "addresses",
                    "direction": MatrixSource.Direction.INCOMING,
                },
                {
                    "label": "POC Scenarios",
                    "relation_name": "validates",
                    "direction": MatrixSource.Direction.INCOMING,
                },
                {
                    "label": "Proposal Sections",
                    "relation_name": "covers",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

        # 2. POC Validation Matrix
        self._matrix(
            name="POC Validation Matrix",
            description=(
                "Maps each POC scenario to the customer requirements it validates."
            ),
            columns=[
                {
                    "label": "POC Scenario",
                    "seed_item_type_slug": "poc-scenario",
                },
                {
                    "label": "Validated Requirements",
                    "relation_name": "validates",
                    "direction": MatrixSource.Direction.OUTGOING,
                },
            ],
        )

        # 3. Security Compliance Matrix
        self._matrix(
            name="Security Compliance Matrix",
            description=(
                "Maps each security response to the customer requirements it answers."
            ),
            columns=[
                {
                    "label": "Security Response",
                    "seed_item_type_slug": "security-response",
                },
                {
                    "label": "Answered Requirements",
                    "relation_name": "answers",
                    "direction": MatrixSource.Direction.OUTGOING,
                },
            ],
        )

        # 4. Objection Handling Matrix
        self._matrix(
            name="Objection Handling Matrix",
            description=(
                "Maps each objection to the talking points that counter it."
            ),
            columns=[
                {
                    "label": "Objection",
                    "seed_item_type_slug": "objection",
                },
                {
                    "label": "Talking Points",
                    "relation_name": "counters",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )

        # 5. Competitive Landscape Matrix
        self._matrix(
            name="Competitive Landscape Matrix",
            description=(
                "Maps each competitor to the solution components they contest."
            ),
            columns=[
                {
                    "label": "Competitor",
                    "seed_item_type_slug": "competitor",
                },
                {
                    "label": "Contested Components",
                    "relation_name": "competes_with",
                    "direction": MatrixSource.Direction.OUTGOING,
                },
            ],
        )

        # 6. Risk Mitigation Matrix
        self._matrix(
            name="Risk Mitigation Matrix",
            description=(
                "Maps each risk to the action items that mitigate it."
            ),
            columns=[
                {
                    "label": "Risk",
                    "seed_item_type_slug": "risk",
                },
                {
                    "label": "Mitigating Actions",
                    "relation_name": "mitigates",
                    "direction": MatrixSource.Direction.INCOMING,
                },
            ],
        )
