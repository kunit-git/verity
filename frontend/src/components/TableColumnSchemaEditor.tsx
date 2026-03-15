import { useQuery } from "@tanstack/react-query";
import { Plus, Trash2, ArrowUp, ArrowDown } from "lucide-react";
import { getRelationTypes } from "../api/relations";
import type { TableFieldColumnSpec } from "../types";

interface Props {
  value: TableFieldColumnSpec[];
  onChange: (cols: TableFieldColumnSpec[]) => void;
}

export default function TableColumnSchemaEditor({ value, onChange }: Props) {
  const { data: relationTypes } = useQuery({
    queryKey: ["relationTypes"],
    queryFn: getRelationTypes,
  });

  function addColumn(kind: TableFieldColumnSpec["kind"]) {
    const name = `col${value.length}`;
    const base: TableFieldColumnSpec = { name, kind, label: "" };
    if (kind === "traversal") {
      onChange([...value, { ...base, direction: "outgoing" }]);
    } else if (kind === "annotation") {
      onChange([...value, { ...base, slug: "" }]);
    } else if (kind === "item_field") {
      onChange([...value, { ...base, field_slug: "", source_ref: "" }]);
    } else {
      onChange([...value, { ...base, formula: "" }]);
    }
  }

  function updateColumn(idx: number, patch: Partial<TableFieldColumnSpec>) {
    onChange(value.map((c, i) => (i === idx ? { ...c, ...patch } : c)));
  }

  function removeColumn(idx: number) {
    onChange(value.filter((_, i) => i !== idx));
  }

  function moveColumn(idx: number, dir: "up" | "down") {
    const next = [...value];
    const swap = dir === "up" ? idx - 1 : idx + 1;
    if (swap < 0 || swap >= next.length) return;
    // First column must be traversal — don't allow moving it away from index 0
    if (idx === 0 || swap === 0) return;
    [next[idx], next[swap]] = [next[swap], next[idx]];
    onChange(next);
  }

  const canAddNonTraversal = value.length > 0 && value[0].kind === "traversal";

  return (
    <div className="space-y-2">
      {value.length === 0 && (
        <p className="text-xs text-gray-400">
          Add a traversal column first — the owning item is the implicit starting point.
        </p>
      )}

      {value.map((col, idx) => (
        <ColumnRow
          key={idx}
          col={col}
          idx={idx}
          allCols={value}
          isFirst={idx === 0}
          isLast={idx === value.length - 1}
          relationTypes={relationTypes ?? []}
          onUpdate={(p) => updateColumn(idx, p)}
          onRemove={() => removeColumn(idx)}
          onMoveUp={() => moveColumn(idx, "up")}
          onMoveDown={() => moveColumn(idx, "down")}
        />
      ))}

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button
          type="button"
          onClick={() => addColumn("traversal")}
          className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700"
        >
          <Plus className="h-3 w-3" />
          Traversal
        </button>
        {canAddNonTraversal && (
          <>
            <button
              type="button"
              onClick={() => addColumn("item_field")}
              className="flex items-center gap-1 text-xs text-orange-600 hover:text-orange-700"
            >
              <Plus className="h-3 w-3" />
              Item Field
            </button>
            <button
              type="button"
              onClick={() => addColumn("annotation")}
              className="flex items-center gap-1 text-xs text-green-600 hover:text-green-700"
            >
              <Plus className="h-3 w-3" />
              Annotation
            </button>
            <button
              type="button"
              onClick={() => addColumn("formula")}
              className="flex items-center gap-1 text-xs text-purple-600 hover:text-purple-700"
            >
              <Plus className="h-3 w-3" />
              Formula
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function ColumnRow({
  col,
  idx,
  allCols,
  isFirst,
  isLast,
  relationTypes,
  onUpdate,
  onRemove,
  onMoveUp,
  onMoveDown,
}: {
  col: TableFieldColumnSpec;
  idx: number;
  allCols: TableFieldColumnSpec[];
  isFirst: boolean;
  isLast: boolean;
  relationTypes: { id: string; name: string; forward_label: string; reverse_label: string }[];
  onUpdate: (p: Partial<TableFieldColumnSpec>) => void;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  const kindColor =
    col.kind === "formula"
      ? "text-purple-600"
      : col.kind === "annotation"
        ? "text-green-600"
        : col.kind === "item_field"
          ? "text-orange-600"
          : "text-blue-600";

  return (
    <div className="rounded border border-gray-200 bg-white p-2.5">
      <div className="flex items-center gap-1.5">
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${kindColor} bg-gray-50`}
        >
          {col.kind}
        </span>
        <div className="ml-auto flex items-center gap-0.5">
          {!isFirst && (
            <button
              type="button"
              onClick={onMoveUp}
              disabled={idx <= 1}
              className="rounded p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-30"
            >
              <ArrowUp className="h-3 w-3" />
            </button>
          )}
          {!isLast && !isFirst && (
            <button
              type="button"
              onClick={onMoveDown}
              className="rounded p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            >
              <ArrowDown className="h-3 w-3" />
            </button>
          )}
          <button
            type="button"
            onClick={onRemove}
            className="rounded p-0.5 text-red-400 hover:bg-red-50 hover:text-red-600"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-2">
        {/* Name */}
        <div>
          <label className="block text-[10px] font-medium text-gray-500">Name <span className="text-red-500">*</span></label>
          <input
            type="text"
            value={col.name}
            onChange={(e) => onUpdate({ name: e.target.value })}
            placeholder="e.g. tests"
            className="mt-0.5 block w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs focus:border-blue-400 focus:outline-none"
          />
        </div>
        {/* Label */}
        <div>
          <label className="block text-[10px] font-medium text-gray-500">Label</label>
          <input
            type="text"
            value={col.label}
            onChange={(e) => onUpdate({ label: e.target.value })}
            placeholder="Column label"
            className="mt-0.5 block w-full rounded border border-gray-300 px-2 py-1 text-xs focus:border-blue-400 focus:outline-none"
          />
        </div>

        {col.kind === "traversal" && (
          <TraversalFields col={col} relationTypes={relationTypes} onUpdate={onUpdate} />
        )}
        {col.kind === "annotation" && (
          <AnnotationFields col={col} onUpdate={onUpdate} />
        )}
        {col.kind === "item_field" && (
          <ItemFieldFields col={col} allCols={allCols} onUpdate={onUpdate} />
        )}
        {col.kind === "formula" && (
          <FormulaFields col={col} allCols={allCols} onUpdate={onUpdate} />
        )}
      </div>
    </div>
  );
}

function TraversalFields({
  col,
  relationTypes,
  onUpdate,
}: {
  col: TableFieldColumnSpec;
  relationTypes: { id: string; name: string; forward_label: string; reverse_label: string }[];
  onUpdate: (p: Partial<TableFieldColumnSpec>) => void;
}) {
  return (
    <>
      <div>
        <label className="block text-[10px] font-medium text-gray-500">
          Relation Type <span className="text-red-500">*</span>
        </label>
        <select
          value={col.relation_type_id ?? ""}
          onChange={(e) => onUpdate({ relation_type_id: e.target.value || undefined })}
          className="mt-0.5 block w-full rounded border border-gray-300 px-2 py-1 text-xs focus:outline-none"
        >
          <option value="">Select...</option>
          {relationTypes.map((rt) => (
            <option key={rt.id} value={rt.id}>
              {rt.name}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-[10px] font-medium text-gray-500">
          Direction <span className="text-red-500">*</span>
        </label>
        <select
          value={col.direction ?? "outgoing"}
          onChange={(e) =>
            onUpdate({ direction: e.target.value as "outgoing" | "incoming" })
          }
          className="mt-0.5 block w-full rounded border border-gray-300 px-2 py-1 text-xs focus:outline-none"
        >
          <option value="outgoing">&rarr; Outgoing</option>
          <option value="incoming">&larr; Incoming</option>
        </select>
      </div>
    </>
  );
}

function AnnotationFields({
  col,
  onUpdate,
}: {
  col: TableFieldColumnSpec;
  onUpdate: (p: Partial<TableFieldColumnSpec>) => void;
}) {
  return (
    <div className="col-span-2">
      <label className="block text-[10px] font-medium text-gray-500">
        Slug <span className="text-red-500">*</span>
      </label>
      <input
        type="text"
        value={col.slug ?? ""}
        onChange={(e) => onUpdate({ slug: e.target.value })}
        placeholder="e.g. review-notes"
        className="mt-0.5 block w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs focus:border-green-400 focus:outline-none"
      />
    </div>
  );
}

function ItemFieldFields({
  col,
  allCols,
  onUpdate,
}: {
  col: TableFieldColumnSpec;
  allCols: TableFieldColumnSpec[];
  onUpdate: (p: Partial<TableFieldColumnSpec>) => void;
}) {
  const sourceCols = allCols
    .filter((c) => c.kind === "traversal" && c.name)
    .map((c) => ({ name: c.name, label: c.label || c.name }));

  return (
    <>
      <div>
        <label className="block text-[10px] font-medium text-gray-500">
          Source <span className="text-red-500">*</span>
        </label>
        <select
          value={col.source_ref ?? ""}
          onChange={(e) => onUpdate({ source_ref: e.target.value || undefined })}
          className="mt-0.5 block w-full rounded border border-gray-300 px-2 py-1 text-xs focus:outline-none"
        >
          <option value="">Select...</option>
          {sourceCols.map((c) => (
            <option key={c.name} value={c.name}>
              {c.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-[10px] font-medium text-gray-500">
          Field Slug <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          value={col.field_slug ?? ""}
          onChange={(e) => onUpdate({ field_slug: e.target.value })}
          placeholder="e.g. severity"
          className="mt-0.5 block w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs focus:border-orange-400 focus:outline-none"
        />
      </div>
    </>
  );
}

function FormulaFields({
  col,
  allCols,
  onUpdate,
}: {
  col: TableFieldColumnSpec;
  allCols: TableFieldColumnSpec[];
  onUpdate: (p: Partial<TableFieldColumnSpec>) => void;
}) {
  const refs = allCols
    .filter((c) => c.kind !== "formula" && c.name)
    .map((c) => `$${c.name}`);

  return (
    <div className="col-span-2">
      <label className="block text-[10px] font-medium text-gray-500">
        Formula <span className="text-red-500">*</span>
      </label>
      <input
        type="text"
        value={col.formula ?? ""}
        onChange={(e) => onUpdate({ formula: e.target.value })}
        placeholder="e.g. $tests.severity * $tests.probability"
        className="mt-0.5 block w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs focus:border-purple-400 focus:outline-none"
      />
      {refs.length > 0 && (
        <p className="mt-1 text-[10px] text-gray-400">
          Available: {refs.join(", ")}
        </p>
      )}
    </div>
  );
}
