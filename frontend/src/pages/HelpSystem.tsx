import { useState } from "react";
import { X, ChevronRight, ChevronLeft, HelpCircle, Home } from "lucide-react";
import { useLocation } from "react-router-dom";

// ── types ─────────────────────────────────────────────────────────────────────

interface HelpTopic {
  id: string;
  title: string;
  summary: string;
  content: React.ReactNode;
  subtopics?: HelpTopic[];
}

// ── shared content helpers ────────────────────────────────────────────────────

function FieldTable({ rows }: { rows: [string, string][] }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-gray-200 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
          <th className="pb-2 pr-4">Placeholder</th>
          <th className="pb-2">Description</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-100">
        {rows.map(([ph, desc]) => (
          <tr key={ph}>
            <td className="py-2 pr-4 align-top font-mono text-xs text-blue-700">{ph}</td>
            <td className="py-2 text-gray-700">{desc}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
      {children}
    </p>
  );
}

// ── help topics ───────────────────────────────────────────────────────────────

const TOPICS: HelpTopic[] = [
  // ── Item Navigator ────────────────────────────────────────────────────────
  {
    id: "navigator",
    title: "Item Navigator",
    summary: "Browse items, trace relations, and manage links.",
    content: (
      <div className="space-y-4">
        <p>
          The <strong>Item Navigator</strong> is the main view for working with a
          single item. It shows a three-column layout:
        </p>
        <ul className="list-disc space-y-1 pl-5 text-gray-700">
          <li><strong>Left panel</strong> — incoming trace relations (items that reference this one).</li>
          <li><strong>Centre panel</strong> — the item's own fields, status, and version history.</li>
          <li><strong>Right panel</strong> — outgoing trace relations (items this one references).</li>
        </ul>
        <p>
          Composition relations (parent/child) define the tree hierarchy and do
          not appear in the left/right panels — they are shown in the{" "}
          <strong>Composition Tree</strong> sidebar instead.
        </p>
      </div>
    ),
    subtopics: [
      {
        id: "navigator-suspect",
        title: "Suspect Links",
        summary: "What amber warnings on relations mean and how to resolve them.",
        content: (
          <div className="space-y-4">
            <p>
              A relation becomes <strong>suspect</strong> when one of its linked
              items is edited after the relation was last confirmed. This signals
              that the relationship may need review — the content of one side has
              changed.
            </p>
            <p>Two flags distinguish which side changed:</p>
            <ul className="list-disc space-y-1 pl-5 text-gray-700">
              <li><strong>Other changed</strong> — the remote item was edited.</li>
              <li><strong>Self changed</strong> — the current item was edited after the relation was set.</li>
            </ul>
            <p>
              Click <strong>Confirm</strong> on a suspect relation to acknowledge
              you have reviewed both sides. This records the current versions as
              confirmed and clears the amber warning.
            </p>
          </div>
        ),
      },
      {
        id: "navigator-versions",
        title: "Version History",
        summary: "How item versions work and how to compare them.",
        content: (
          <div className="space-y-4">
            <p>
              Every time an item is saved (via the item edit form or the Document
              Editor), the previous state is snapshotted as a new version. The
              version number starts at 1 and increments with every save.
            </p>
            <p>
              The version history panel in the centre column lists all past
              versions. Click any version to expand and inspect the snapshot of
              fields at that point in time.
            </p>
          </div>
        ),
      },
    ],
  },

  // ── Document Editor ───────────────────────────────────────────────────────
  {
    id: "doc-editor",
    title: "Document Editor",
    summary: "Edit an entire item subtree as a single scrollable document.",
    content: (
      <div className="space-y-4">
        <p>
          The <strong>Document Editor</strong> renders an entire subtree of your
          composition hierarchy as a single scrollable document. Each item in the
          tree appears as a card whose layout is driven by a document template
          defined for its item type.
        </p>
        <p>
          You can edit any field inline — changes are held locally until you
          press <strong>Save</strong>. The editor also lets you add new items
          between existing ones and mark items for deletion, all without touching
          the database until you explicitly save.
        </p>
        <ul className="list-disc space-y-1 pl-5 text-gray-700">
          <li><strong>Template-driven</strong> — layout comes from each item type's document template.</li>
          <li><strong>Deferred persistence</strong> — all changes are staged locally and written only on Save.</li>
          <li><strong>Conflict detection</strong> — warns if another user saved while you were editing.</li>
        </ul>
      </div>
    ),
    subtopics: [
      {
        id: "doc-editor-editing",
        title: "Editing Fields",
        summary: "Click any field to edit it inline.",
        content: (
          <div className="space-y-4">
            <p>
              Every editable field is rendered as an underlined inline widget.
              Click and type — no separate edit mode needed.
            </p>
            <ul className="list-disc space-y-1 pl-5 text-gray-700">
              <li><strong>Text / description</strong> — expanding textarea.</li>
              <li><strong>Status / choice</strong> — dropdown.</li>
              <li><strong>Date</strong> — native date picker.</li>
              <li><strong>Boolean</strong> — checkbox.</li>
            </ul>
            <p>
              When any field changes, the card header shows an amber{" "}
              <strong>modified</strong> badge. The revert icon (↺) next to it
              restores all fields of that card to the last-loaded server values.
            </p>
          </div>
        ),
      },
      {
        id: "doc-editor-adding",
        title: "Adding Items",
        summary: "Insert new items between existing ones.",
        content: (
          <div className="space-y-4">
            <p>
              Between every pair of adjacent items there is a dashed{" "}
              <strong>+ Add item</strong> strip. Click it, pick a type, and a
              new card appears with a green <strong>new</strong> badge. The card
              renders the full template so you can fill in all fields immediately.
            </p>
            <p>Insertion position follows composition tree depth rules:</p>
            <ul className="list-disc space-y-1 pl-5 text-gray-700">
              <li>If the item below is deeper, the new item becomes the <strong>first child</strong> of the item above.</li>
              <li>Otherwise it is inserted as a <strong>sibling</strong> of the item above.</li>
            </ul>
            <p>New items are only created on the server when you press Save.</p>
          </div>
        ),
      },
      {
        id: "doc-editor-deleting",
        title: "Deleting Items",
        summary: "Mark items for deletion without removing them immediately.",
        content: (
          <div className="space-y-4">
            <p>
              Click the <strong>trash icon</strong> in a card header to mark it
              for deletion. The card collapses and dims. Click the undo icon to
              cancel before saving.
            </p>
            <Note>
              <strong>Warning:</strong> Deleting a parent item removes it from
              the tree. Child items remain in the database but lose their
              composition link.
            </Note>
          </div>
        ),
      },
      {
        id: "doc-editor-saving",
        title: "Saving",
        summary: "How the Save button works and what it commits.",
        content: (
          <div className="space-y-4">
            <p>
              The Save button is enabled when there are modified items, pending
              new items, or items marked for deletion. It processes all three
              groups in sequence. If an item has a <strong>conflict</strong>{" "}
              (another user saved it while you were editing), that item is
              skipped — click <strong>Reload</strong> in the conflict banner to
              pull the latest values, then save again.
            </p>
          </div>
        ),
      },
      {
        id: "doc-editor-colors",
        title: "Card Colors",
        summary: "What the colored left border on each card means.",
        content: (
          <div className="space-y-4">
            <p>
              The left border color indicates the item's <strong>depth</strong>{" "}
              in the composition tree.
            </p>
            <div className="space-y-2">
              {[
                ["bg-blue-400", "Depth 1", "Root item"],
                ["bg-emerald-400", "Depth 2", "Direct children"],
                ["bg-violet-400", "Depth 3", "Grandchildren"],
                ["bg-amber-400", "Depth 4", ""],
                ["bg-rose-400", "Depth 5", ""],
                ["bg-teal-400", "Depth 6+", "Wraps at depth 7"],
              ].map(([bg, label, note]) => (
                <div key={label} className="flex items-center gap-3">
                  <span className={`h-4 w-1.5 flex-none rounded-full ${bg}`} />
                  <span className="w-16 text-sm font-medium text-gray-800">{label}</span>
                  {note && <span className="text-sm text-gray-500">{note}</span>}
                </div>
              ))}
            </div>
          </div>
        ),
      },
    ],
  },

  // ── Document Templates ────────────────────────────────────────────────────
  {
    id: "templates",
    title: "Document Templates",
    summary: "Define Markdown layouts for each item type.",
    content: (
      <div className="space-y-4">
        <p>
          A <strong>document template</strong> is a Markdown file with{" "}
          <code className="rounded bg-gray-100 px-1 font-mono text-sm">{"{{field}}"}</code>{" "}
          placeholders. It controls what the Document Editor renders inside each
          item card. You can define one template per item type.
        </p>
        <p>
          Select an item type on the left to open its template in the editor.
          The editor shows the current template (or the system default if none
          has been set) and a live preview of available field placeholders.
        </p>
        <p>
          Click <strong>Save</strong> to publish the template. Click{" "}
          <strong>Reset to default</strong> to remove the custom template and
          fall back to the system default.
        </p>
      </div>
    ),
    subtopics: [
      {
        id: "templates-syntax",
        title: "Template Syntax",
        summary: "How to write {{field}} placeholders in Markdown.",
        content: (
          <div className="space-y-4">
            <p>
              Write standard Markdown and insert{" "}
              <code className="rounded bg-gray-100 px-1 font-mono text-sm">{"{{slug}}"}</code>{" "}
              where you want a field to appear. The Document Editor replaces each
              placeholder with an interactive widget.
            </p>
            <pre className="overflow-x-auto rounded-md bg-gray-900 p-4 text-sm text-green-300">
{`{{heading}} {{title}}

**Status:** {{status}}  **By:** {{created_by}}

{{description}}

| Attribute | Value              |
|-----------|--------------------|
| Version   | {{current_version}} |
| Reviewed  | {{reviewed}}       |`}
            </pre>
            <p className="text-sm text-gray-500">
              GFM tables, lists, headings, bold, italic — all standard Markdown
              syntax is supported inside templates.
            </p>
          </div>
        ),
      },
      {
        id: "templates-builtin",
        title: "Built-in Fields",
        summary: "Fields available in every template regardless of item type.",
        content: (
          <FieldTable rows={[
            ["{{heading}}", "Inserts # characters matching the item's depth (e.g. ## at depth 2). Place before a title on the same line."],
            ["{{title}}", "Item title — editable inline text."],
            ["{{description}}", "Item description — editable expanding textarea."],
            ["{{status}}", "Item status — editable dropdown (Draft, Active, In Review, Approved, Archived)."],
            ["{{id}}", "Item UUID — read-only."],
            ["{{item_type}}", "Item type name — read-only."],
            ["{{current_version}}", "Current version number — read-only."],
            ["{{created_by}}", "Creator username — read-only."],
            ["{{created_at}}", "Creation timestamp — read-only."],
            ["{{updated_at}}", "Last-updated timestamp — read-only."],
          ]} />
        ),
      },
      {
        id: "templates-custom",
        title: "Custom Field Placeholders",
        summary: "Referencing item-type-specific fields by slug.",
        content: (
          <div className="space-y-4">
            <p>
              Any custom field defined on the item type can be used by its{" "}
              <strong>slug</strong>. The editor picks the appropriate widget
              automatically:
            </p>
            <FieldTable rows={[
              ["text", "Expanding textarea"],
              ["integer / decimal", "Number input"],
              ["boolean", "Checkbox"],
              ["date", "Date picker"],
              ["choice", "Dropdown with the configured choices"],
              ["mermaid", "Mermaid source textarea with live diagram preview below"],
              ["table", "Embedded relation table — renders a full TableFieldWidget (read-only in document view; annotatable inline)"],
            ]} />
            <p className="text-sm text-gray-500">
              If a placeholder slug doesn't match any field on the item type, it
              renders in grey italic as a visual reminder.
            </p>
          </div>
        ),
      },
    ],
  },

  // ── Item Types ────────────────────────────────────────────────────────────
  {
    id: "item-types",
    title: "Item Types",
    summary: "Configure the categories and custom fields for your items.",
    content: (
      <div className="space-y-4">
        <p>
          <strong>Item types</strong> are the categories your items belong to
          (e.g. Requirement, Test Case, Risk). Each type has a name, slug, and
          optional icon, and can carry any number of{" "}
          <strong>custom fields</strong>.
        </p>
        <p>
          The Item Types manager lets you create and edit types, and add or
          remove custom fields. Custom fields appear in the item detail panel
          and can be referenced in document templates.
        </p>
      </div>
    ),
    subtopics: [
      {
        id: "item-types-custom-fields",
        title: "Custom Fields",
        summary: "Adding typed fields to an item type.",
        content: (
          <div className="space-y-4">
            <p>
              Each custom field has a <strong>name</strong>, a unique{" "}
              <strong>slug</strong> (used in templates), and a{" "}
              <strong>field kind</strong>:
            </p>
            <FieldTable rows={[
              ["text", "Free-form text, stored as a string."],
              ["integer", "Whole number."],
              ["decimal", "Decimal number."],
              ["boolean", "True / false checkbox."],
              ["date", "Calendar date (ISO 8601)."],
              ["choice", "One value from a fixed list of options you define."],
              ["mermaid", "Mermaid diagram source — rendered as a live diagram in the item detail and document editor."],
              ["table", "Embedded relation table — see Table Fields below."],
            ]} />
            <p>
              Fields can be marked <strong>required</strong>, which is enforced
              when creating or editing items through the standard item form.
              Table and Mermaid fields cannot be required.
            </p>
          </div>
        ),
      },
      {
        id: "item-types-table-fields",
        title: "Table Fields",
        summary: "Embed a relation traversal table directly on an item.",
        content: (
          <div className="space-y-4">
            <p>
              A <strong>table field</strong> embeds a configurable relation
              table directly on an item. Instead of a stored value, the table
              is computed live by following relation paths from the owning item.
            </p>
            <p>
              When you add a field of kind <strong>table</strong>, you define
              its column schema using the column editor. The owning item is the
              implicit starting point — no seed column is needed.
            </p>
            <FieldTable rows={[
              ["Traversal", "Follows a relation type (outgoing or incoming) from the owning item or a prior traversal column. The first column must always be a traversal."],
              ["Item Field", "Reads a custom field value from the items in a traversal column. Choose which traversal column is the source and enter the field slug."],
              ["Annotation", "An editable free-text cell stored per row. Give it a unique slug. Annotations are not versioned."],
              ["Formula", "A numeric expression referencing other column values via $N.field-slug. Evaluated at query time."],
            ]} />
            <p>
              The table is rendered in the <strong>Item Navigator</strong> detail
              panel and in the <strong>Document Editor</strong> when the field
              slug is used as a template placeholder. It is not shown in the
              item creation form — annotations become available once the item
              exists and has relations.
            </p>
            <Note>
              Table field data is never snapshotted in item versions. Annotation
              values are stored per (item, field, row) and persist independently
              of item edits.
            </Note>
          </div>
        ),
      },
    ],
  },

  // ── Relation Types ────────────────────────────────────────────────────────
  {
    id: "relation-types",
    title: "Relation Types",
    summary: "Configure how items can be linked to each other.",
    content: (
      <div className="space-y-4">
        <p>
          <strong>Relation types</strong> define the kinds of links that can
          exist between items. Every relation type has a kind and a pair of
          labels:
        </p>
        <ul className="list-disc space-y-2 pl-5 text-gray-700">
          <li>
            <strong>Composition</strong> — defines the parent/child tree
            hierarchy. Composition relations drive the Composition Tree sidebar
            and the Document Editor. The built-in type is{" "}
            <em>is composed of</em>.
          </li>
          <li>
            <strong>Trace</strong> — horizontal links between items at any
            level. Trace relations appear in the left/right panels of the Item
            Navigator and trigger suspect-link tracking. The built-in type is{" "}
            <em>traces to</em>.
          </li>
        </ul>
        <p>
          You can restrict a relation type to specific source and target item
          types, or leave them unrestricted to allow any combination.
        </p>
        <Note>
          The two built-in relation types (<em>is composed of</em> and{" "}
          <em>traces to</em>) cannot be deleted.
        </Note>
      </div>
    ),
  },

  // ── Tables ────────────────────────────────────────────────────────────────
  {
    id: "tables",
    title: "Traceability Tables",
    summary: "Cross-reference items across multiple relation hops.",
    content: (
      <div className="space-y-4">
        <p>
          A <strong>traceability table</strong> is a configurable matrix that
          follows relation paths through your item graph. There are two kinds:
        </p>
        <ul className="list-disc space-y-2 pl-5 text-gray-700">
          <li>
            <strong>Global tables</strong> — created under the Tables menu.
            They start from a seed item type (optionally scoped to a container)
            and traverse relations across any items in the vault.
          </li>
          <li>
            <strong>Item table fields</strong> — embedded on a specific item
            type as a custom field of kind <em>table</em>. They start from
            the owning item and follow its relations. Visible in the Item
            Navigator and Document Editor.
          </li>
        </ul>
        <p>
          Both kinds share the same column schema and support all column types.
        </p>
      </div>
    ),
    subtopics: [
      {
        id: "tables-columns",
        title: "Column Types",
        summary: "Seed, traversal, item field, annotation, and formula columns.",
        content: (
          <div className="space-y-4">
            <FieldTable rows={[
              ["Seed", "Global tables only. The starting set of items — choose an item type and optionally a container to scope it."],
              ["Traversal", "Follows a relation type (outgoing or incoming) from the previous column's items. The first non-seed column must be a traversal."],
              ["Item Field", "Reads a custom field value from items in a prior traversal column. Choose the source column and the field slug."],
              ["Annotation", "An editable free-text cell stored per row. Each annotation column has a unique slug. Values persist across page reloads."],
              ["Formula", "A numeric expression using $N.field-slug references to other columns' custom field values. Supports +, -, *, /, and parentheses."],
            ]} />
            <p>
              Columns are evaluated left to right. Traversal columns can
              produce multiple rows per seed item when more than one relation
              matches — these rows are grouped and can be expanded/collapsed
              using the chevron on the first column.
            </p>
          </div>
        ),
      },
      {
        id: "tables-annotations",
        title: "Annotations",
        summary: "Storing free-text notes per row.",
        content: (
          <div className="space-y-4">
            <p>
              An <strong>annotation column</strong> adds an editable text cell
              to every row. The value is keyed by the row's{" "}
              <em>row hash</em> — a fingerprint of the item IDs at each
              traversal position in that row.
            </p>
            <p>
              Click any annotation cell and type to edit. The value is saved
              automatically when you move focus away (blur). The column header
              shows a ✎ symbol to distinguish annotation columns from read-only
              columns.
            </p>
            <Note>
              If a relation is removed and then re-added, the row hash changes
              and the old annotation value becomes orphaned (not shown). Renaming
              items or editing their fields does not affect the row hash.
            </Note>
          </div>
        ),
      },
      {
        id: "tables-formulas",
        title: "Formula Syntax",
        summary: "Writing numeric expressions in formula columns.",
        content: (
          <div className="space-y-4">
            <p>
              Formula expressions reference other columns using{" "}
              <code className="rounded bg-gray-100 px-1 font-mono text-sm">$N.field-slug</code>{" "}
              where <code className="rounded bg-gray-100 px-1 font-mono text-sm">N</code> is
              the 1-based column position (counting from the seed or first
              traversal column) and <code className="rounded bg-gray-100 px-1 font-mono text-sm">field-slug</code>{" "}
              is a custom field on that column's item type.
            </p>
            <p>Example: <code className="rounded bg-gray-100 px-1 font-mono text-sm">$1.threat-level * $2.severity</code></p>
            <ul className="list-disc space-y-1 pl-5 text-gray-700">
              <li>Supports <code className="rounded bg-gray-100 px-1 font-mono text-sm">+ - * / ( )</code></li>
              <li>Choice fields are converted to their 1-based index in the choices list</li>
              <li>Missing or non-numeric values are treated as 0</li>
            </ul>
          </div>
        ),
      },
    ],
  },

  // ── Mailbox ───────────────────────────────────────────────────────────────
  {
    id: "mailbox",
    title: "Mailbox",
    summary: "Generated Markdown documents produced by the AI assistant.",
    content: (
      <div className="space-y-4">
        <p>
          The <strong>Mailbox</strong> stores Markdown documents generated by
          the AI assistant. When the assistant produces a report, analysis, or
          other artifact, it is delivered here as a named file you can read and
          download.
        </p>
        <p>
          Documents are per-user and are never shared across accounts. They
          accumulate over time — delete any you no longer need.
        </p>
      </div>
    ),
  },

  // ── AI Assistant ──────────────────────────────────────────────────────────
  {
    id: "ai-assistant",
    title: "AI Assistant",
    summary: "Ask questions and propose changes using a conversational agent.",
    content: (
      <div className="space-y-4">
        <p>
          The <strong>AI Assistant</strong> panel lets you converse with an AI
          agent that has read access to your vault's items and relations. You can
          ask questions, request analyses, and ask the agent to propose new items
          or edits.
        </p>
        <p>
          When the agent wants to create or update an item it proposes a{" "}
          <strong>pending action</strong>. Review the proposed payload and
          click <strong>Accept</strong> to execute it or <strong>Reject</strong>{" "}
          to dismiss it. Nothing is written to the database without your
          approval.
        </p>
        <p>
          Conversations are scoped to the item you were viewing when you opened
          the panel. The agent uses that item as context for its responses.
        </p>
      </div>
    ),
  },
];

// ── route → topic mapping ─────────────────────────────────────────────────────

const ROUTE_TOPIC_MAP: { pattern: RegExp; topicId: string }[] = [
  { pattern: /^\/items\/[^/]+\/doc-edit/, topicId: "doc-editor" },
  { pattern: /^\/manage\/templates/, topicId: "templates" },
  { pattern: /^\/manage\/item-types/, topicId: "item-types" },
  { pattern: /^\/manage\/relation-types/, topicId: "relation-types" },
  { pattern: /^\/tables/, topicId: "tables" },
  { pattern: /^\/mailbox/, topicId: "mailbox" },
  { pattern: /^\/manage\/ai/, topicId: "ai-assistant" },
  { pattern: /^\/items\/[^/]+/, topicId: "navigator" },
];

export function useHelpTopicId(): string | null {
  const location = useLocation();
  for (const { pattern, topicId } of ROUTE_TOPIC_MAP) {
    if (pattern.test(location.pathname)) return topicId;
  }
  return null;
}

// ── navigation helpers ────────────────────────────────────────────────────────

function findTopic(topics: HelpTopic[], id: string): HelpTopic | undefined {
  for (const t of topics) {
    if (t.id === id) return t;
    if (t.subtopics) {
      const found = findTopic(t.subtopics, id);
      if (found) return found;
    }
  }
  return undefined;
}

// ── modal ─────────────────────────────────────────────────────────────────────

export function HelpModal({ initialTopicId, onClose }: { initialTopicId?: string | null; onClose: () => void }) {
  const [path, setPath] = useState<string[]>(initialTopicId ? [initialTopicId] : []);

  const currentTopic = path.length > 0 ? findTopic(TOPICS, path[path.length - 1]) : null;
  const parentTopic = path.length > 1 ? findTopic(TOPICS, path[path.length - 2]) : null;
  const displayTopics = currentTopic?.subtopics ?? TOPICS;

  function navigate(id: string) { setPath((p) => [...p, id]); }
  function goBack() { setPath((p) => p.slice(0, -1)); }
  function goHome() { setPath([]); }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="relative flex h-[82vh] w-[780px] max-w-[95vw] flex-col overflow-hidden rounded-xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center gap-2 border-b border-gray-200 bg-gray-50 px-5 py-3">
          {path.length > 0 ? (
            <>
              <button onClick={goHome} className="rounded p-1 text-gray-400 hover:bg-gray-200 hover:text-gray-600" title="Home">
                <Home className="h-4 w-4" />
              </button>
              <ChevronRight className="h-3 w-3 text-gray-300" />
              {path.length > 1 && parentTopic && (
                <>
                  <button onClick={goBack} className="text-sm text-gray-500 hover:text-gray-800">
                    {parentTopic.title}
                  </button>
                  <ChevronRight className="h-3 w-3 text-gray-300" />
                </>
              )}
              <span className="text-sm font-semibold text-gray-800">{currentTopic?.title}</span>
            </>
          ) : (
            <>
              <HelpCircle className="h-4 w-4 text-blue-500" />
              <span className="text-sm font-semibold text-gray-800">Help</span>
            </>
          )}
          <button onClick={onClose} className="ml-auto rounded p-1 text-gray-400 hover:bg-gray-200 hover:text-gray-600" title="Close">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar */}
          <nav className="w-52 flex-none overflow-y-auto border-r border-gray-100 bg-gray-50 py-3">
            {path.length > 0 && (
              <button
                onClick={goBack}
                className="mb-1 flex w-full items-center gap-1.5 px-4 py-1.5 text-left text-xs text-blue-600 hover:text-blue-800"
              >
                <ChevronLeft className="h-3 w-3" />
                Back
              </button>
            )}
            {displayTopics.map((t) => {
              const isActive = path[path.length - 1] === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => navigate(t.id)}
                  className={`flex w-full items-start gap-2 px-4 py-2 text-left transition-colors ${
                    isActive ? "bg-blue-50 text-blue-700" : "text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  <span className="flex-1">
                    <span className={`block text-sm font-medium ${isActive ? "text-blue-700" : "text-gray-800"}`}>
                      {t.title}
                    </span>
                    <span className="mt-0.5 block text-[11px] leading-snug text-gray-400">
                      {t.summary}
                    </span>
                  </span>
                  {t.subtopics && (
                    <ChevronRight className={`mt-0.5 h-3 w-3 flex-none ${isActive ? "text-blue-400" : "text-gray-300"}`} />
                  )}
                </button>
              );
            })}
          </nav>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-8 py-6 text-sm leading-relaxed text-gray-700">
            {currentTopic ? (
              <div className="space-y-4">
                {currentTopic.content}
                {currentTopic.subtopics && currentTopic.subtopics.length > 0 && (
                  <div className="mt-6">
                    <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">
                      Subtopics
                    </h3>
                    <div className="space-y-2">
                      {currentTopic.subtopics.map((sub) => (
                        <button
                          key={sub.id}
                          onClick={() => navigate(sub.id)}
                          className="flex w-full items-center gap-3 rounded-lg border border-gray-100 bg-gray-50 px-4 py-3 text-left transition-colors hover:border-blue-200 hover:bg-blue-50"
                        >
                          <div className="flex-1">
                            <div className="text-sm font-medium text-gray-800">{sub.title}</div>
                            <div className="mt-0.5 text-xs text-gray-500">{sub.summary}</div>
                          </div>
                          <ChevronRight className="h-4 w-4 flex-none text-gray-300" />
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                <p className="mb-5 text-sm text-gray-500">Select a topic to get started.</p>
                {TOPICS.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => navigate(t.id)}
                    className="flex w-full items-center gap-4 rounded-lg border border-gray-100 bg-gray-50 px-5 py-4 text-left transition-colors hover:border-blue-200 hover:bg-blue-50"
                  >
                    <div className="flex-1">
                      <div className="text-sm font-semibold text-gray-800">{t.title}</div>
                      <div className="mt-0.5 text-xs text-gray-500">{t.summary}</div>
                    </div>
                    <ChevronRight className="h-4 w-4 flex-none text-gray-300" />
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── standalone button (kept for any direct usage) ─────────────────────────────

export function HelpButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      title="Help"
      className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-blue-500"
    >
      <HelpCircle className="h-4 w-4" />
    </button>
  );
}
