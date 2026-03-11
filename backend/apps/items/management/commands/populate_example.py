"""
Management command: populate_example

Wipes all user data and items, then populates a realistic Autonomous Vehicle
System example organised around document deliverables — plans, specifications,
FMEA analyses, risk assessments, and verification & validation reports.

Item types used:
  Project, Plan, Specification, Report, Analysis, Information,
  Requirement, Risk, Test Case, Failure Mode, Failure Cause
Relation types:
  Built-in:  is_composed_of, traces_to
  Custom:    verifies, derives_from, mitigates, causes

Usage:
    python manage.py populate_example
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.items.models import CustomFieldDefinition, CustomFieldValue, DocumentTemplate, Item, ItemType
from apps.matrices.models import Matrix, MatrixColumn
from apps.relations.models import ItemRelation, RelationType

User = get_user_model()


class Command(BaseCommand):
    help = "Wipe all data and populate an Autonomous Vehicle document-deliverable example"

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
        )
        for position, col in enumerate(columns):
            if position == 0:
                MatrixColumn.objects.create(
                    matrix=matrix,
                    position=0,
                    label=col["label"],
                    seed_item_type=self._types[col["seed_item_type_slug"]],
                    seed_container=col.get("seed_container"),
                )
            else:
                MatrixColumn.objects.create(
                    matrix=matrix,
                    position=position,
                    label=col["label"],
                    relation_type=self._relations[col["relation_name"]],
                    direction=col["direction"],
                )
        return matrix

    # ------------------------------------------------------------------
    # Command entry point
    # ------------------------------------------------------------------

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Wiping existing data...")
        MatrixColumn.all_objects.all().hard_delete()
        Matrix.all_objects.all().hard_delete()
        ItemRelation.all_objects.all().hard_delete()
        CustomFieldValue.all_objects.all().hard_delete()
        from apps.items.models import ItemVersion
        ItemVersion.all_objects.all().hard_delete()
        Item.all_objects.all().hard_delete()
        DocumentTemplate.all_objects.all().hard_delete()
        CustomFieldDefinition.all_objects.all().hard_delete()
        ItemType.all_objects.all().hard_delete()
        RelationType.all_objects.filter(is_builtin=False).hard_delete()
        from apps.mailbox.models import MailboxArtifact
        MailboxArtifact.all_objects.all().hard_delete()
        User.objects.all().delete()
        self.stdout.write("  Done.\n")

        # Check built-in relation types exist
        self._relations = {r.name: r for r in RelationType.objects.all()}
        missing_rels = {"is_composed_of"} - self._relations.keys()
        if missing_rels:
            self.stderr.write(
                f"Missing relation types: {missing_rels}\n"
                "Run 'python manage.py seed_data' first."
            )
            return

        # Ensure is_composed_of has no source type constraint
        rt = self._relations["is_composed_of"]
        rt.source_item_type = None
        rt.target_item_type = None
        rt.save(update_fields=["source_item_type", "target_item_type"])

        # ------------------------------------------------------------------
        # Item types & custom fields
        # ------------------------------------------------------------------
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
                slug=slug,
                defaults={"name": name, "description": desc, "icon": icon},
            )
            self._types[slug] = obj
            status = "Created" if created else "Exists"
            self.stdout.write(f"  {status}: ItemType '{name}'")

        custom_fields = [
            # Project
            ("project", "Standard Reference", "standard-reference", "text", False, {}),
            # Plan
            ("plan", "Standard Reference", "standard-reference", "text", False, {}),
            ("plan", "Phase", "phase", "choice", False, {"choices": ["Draft", "Review", "Approved", "Superseded"]}),
            # Specification
            ("specification", "Standard Reference", "standard-reference", "text", False, {}),
            ("specification", "Baseline", "baseline", "text", False, {}),
            # Report
            ("report", "Report Date", "report-date", "date", False, {}),
            ("report", "Status", "report-status", "choice", False, {"choices": ["Draft", "Under Review", "Final", "Superseded"]}),
            # Analysis
            ("analysis", "Method", "method", "choice", False, {"choices": ["FMEA", "FTA", "HAZOP", "SOTIF", "HARA", "Other"]}),
            ("analysis", "Standard Reference", "standard-reference", "text", False, {}),
            # Requirement
            ("requirement", "Priority", "priority", "choice", False, {"choices": ["Low", "Medium", "High", "Critical"]}),
            ("requirement", "Verification Method", "verification-method", "choice", False, {"choices": ["Test", "Analysis", "Inspection", "Demonstration"]}),
            # Risk
            ("risk", "Severity", "severity", "choice", False, {"choices": ["Low", "Medium", "High", "Critical"]}),
            ("risk", "Likelihood", "likelihood", "choice", False, {"choices": ["Rare", "Unlikely", "Possible", "Likely", "Almost Certain"]}),
            ("risk", "Mitigation", "mitigation", "text", False, {}),
            # Test Case
            ("test-case", "Test Steps", "test-steps", "text", False, {}),
            ("test-case", "Expected Result", "expected-result", "text", False, {}),
            # Failure Mode
            ("failure-mode", "Severity", "severity", "choice", False, {"choices": ["Low", "Medium", "High", "Critical"]}),
            # Failure Cause
            ("failure-cause", "Category", "category", "choice", False, {"choices": ["Design", "Manufacturing", "Environmental", "Human Error", "Software"]}),
            # Threat
            ("threat", "Threat Level", "threat-level", "choice", False, {"choices": ["Low", "Medium", "High", "Critical"]}),
            ("threat", "Attack Vector", "attack-vector", "choice", False, {"choices": ["Network", "Adjacent", "Local", "Physical"]}),
            ("threat", "Threat Agent", "threat-agent", "text", False, {}),
            # Vulnerability
            ("vulnerability", "Severity", "severity", "choice", False, {"choices": ["Low", "Medium", "High", "Critical"]}),
            ("vulnerability", "Attack Feasibility", "attack-feasibility", "choice", False, {"choices": ["Low", "Medium", "High", "Very High"]}),
            ("vulnerability", "Component", "component", "text", False, {}),
            # Mitigation
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

        # ------------------------------------------------------------------
        # Custom (non-built-in) relation types
        # ------------------------------------------------------------------
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

        # ------------------------------------------------------------------
        # Users
        # ------------------------------------------------------------------
        User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin1234",
            role="admin",
        )
        self.stdout.write("Created user: admin / admin1234 (role: admin)\n")

        self._author = User.objects.create_user(
            username="demo",
            email="demo@example.com",
            password="demo1234",
            role="editor",
        )
        self.stdout.write("Created user: demo / demo1234 (role: editor)\n")

        # ------------------------------------------------------------------
        # Document templates
        # ------------------------------------------------------------------
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

        self.stdout.write("Building Autonomous Vehicle document-deliverable example...")
        self._build()
        self.stdout.write(self.style.SUCCESS(
            "\nDone. Register any account at /register to review and edit the example."
        ))

    # ------------------------------------------------------------------
    # Example data
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

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        n_items = Item.objects.count()
        n_rels = ItemRelation.objects.count()
        n_matrices = Matrix.objects.count()
        self.stdout.write(f"\n  Items created    : {n_items}")
        self.stdout.write(f"  Relations created: {n_rels}")
        self.stdout.write(f"  Matrices created : {n_matrices}")
        self.stdout.write(f"\n  Item types used:")
        from django.db.models import Count
        for row in (
            Item.objects.values("item_type__name")
            .annotate(n=Count("id"))
            .order_by("item_type__name")
        ):
            self.stdout.write(f"    {row['item_type__name']:20s} {row['n']}")
        self.stdout.write(f"\n  Relation types used:")
        for row in (
            ItemRelation.objects.values("relation_type__name")
            .annotate(n=Count("id"))
            .order_by("relation_type__name")
        ):
            self.stdout.write(f"    {row['relation_type__name']:25s} {row['n']}")
