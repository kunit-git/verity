import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  ChevronRight,
} from "lucide-react";
import { getTable, createTable, updateTable } from "../api/tables";
import { getItemTypes, getItems } from "../api/items";
import { getRelationTypes } from "../api/relations";
import type { TableColumnPayload, RelationType, ColumnKind } from "../types";

export default function TableEditorPage() {
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: existingTable } = useQuery({
    queryKey: ["table", id],
    queryFn: () => getTable(id!),
    enabled: isEdit,
  });
  const { data: itemTypes } = useQuery({
    queryKey: ["itemTypes"],
    queryFn: getItemTypes,
  });
  const { data: relationTypes } = useQuery({
    queryKey: ["relationTypes"],
    queryFn: getRelationTypes,
  });

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [columns, setColumns] = useState<TableColumnPayload[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (existingTable) {
      setName(existingTable.name);
      setDescription(existingTable.description);
      setColumns(
        existingTable.columns.map((c) => ({
          position: c.position,
          label: c.label,
          column_kind: c.column_kind,
          seed_item_type: c.seed_item_type,
          seed_container: c.seed_container,
          relation_type: c.relation_type,
          direction: c.direction,
          formula: c.formula,
        }))
      );
    }
  }, [existingTable]);

  function addColumn(kind: ColumnKind) {
    if (columns.length === 0 && kind === "seed") {
      setColumns([
        {
          position: 0,
          label: "",
          column_kind: "seed",
          seed_item_type: null,
          seed_container: null,
        },
      ]);
    } else if (kind === "formula") {
      setColumns((prev) => [
        ...prev,
        {
          position: prev.length,
          label: "",
          column_kind: "formula",
          formula: "",
        },
      ]);
    } else {
      setColumns((prev) => [
        ...prev,
        {
          position: prev.length,
          label: "",
          column_kind: "traversal",
          relation_type: null,
          direction: "outgoing",
        },
      ]);
    }
  }

  function removeColumn(idx: number) {
    setColumns((prev) =>
      prev.filter((_, i) => i !== idx).map((c, i) => ({ ...c, position: i }))
    );
  }

  function moveColumn(idx: number, dir: "up" | "down") {
    setColumns((prev) => {
      const next = [...prev];
      const swap = dir === "up" ? idx - 1 : idx + 1;
      if (swap < 0 || swap >= next.length) return prev;
      // Column 0 is always seed; don't allow moving it
      if (idx === 0 || swap === 0) return prev;
      [next[idx], next[swap]] = [next[swap], next[idx]];
      return next.map((c, i) => ({ ...c, position: i }));
    });
  }

  function updateColumn(idx: number, patch: Partial<TableColumnPayload>) {
    setColumns((prev) =>
      prev.map((c, i) => (i === idx ? { ...c, ...patch } : c))
    );
  }

  const mutation = useMutation({
    mutationFn: () => {
      const payload = { name, description, columns };
      return isEdit ? updateTable(id!, payload) : createTable(payload);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["tables"] });
      navigate(`/tables/${data.id}`);
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : "Failed to save table");
    },
  });

  const canSubmit =
    name.trim() &&
    columns.length >= 1 &&
    columns.every((c) => c.label.trim()) &&
    columns[0]?.seed_item_type &&
    columns.slice(1).every((c) => {
      if (c.column_kind === "formula") return !!c.formula?.trim();
      return c.relation_type && c.direction;
    });

  return (
    <div className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-bold text-gray-900">
        {isEdit ? "Edit Table" : "New Table"}
      </h1>
      <p className="mt-1 text-sm text-gray-500">
        Define columns. Each column after the first follows a relation from the
        previous column's items, or computes a formula.
      </p>

      <div className="mt-6 space-y-5">
        {error && (
          <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Name & description */}
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Table Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="e.g. Requirements → Test Cases → Failure Modes"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Columns */}
        <div>
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700">Columns</h2>
            {columns.length === 0 ? (
              <button
                type="button"
                onClick={() => addColumn("seed")}
                className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700"
              >
                <Plus className="h-3.5 w-3.5" />
                Add first column
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => addColumn("traversal")}
                  className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Traversal
                </button>
                <button
                  type="button"
                  onClick={() => addColumn("formula")}
                  className="flex items-center gap-1 text-sm text-purple-600 hover:text-purple-700"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Formula
                </button>
              </div>
            )}
          </div>

          {columns.length === 0 && (
            <p className="mt-3 text-sm text-gray-400">
              No columns yet — add the first column to define what items to
              start from.
            </p>
          )}

          <div className="mt-3 space-y-3">
            {columns.map((col, idx) => (
              <ColumnEditor
                key={idx}
                col={col}
                idx={idx}
                columns={columns}
                isFirst={idx === 0}
                isLast={idx === columns.length - 1}
                itemTypes={itemTypes ?? []}
                relationTypes={relationTypes ?? []}
                onUpdate={(patch) => updateColumn(idx, patch)}
                onRemove={() => removeColumn(idx)}
                onMoveUp={() => moveColumn(idx, "up")}
                onMoveDown={() => moveColumn(idx, "down")}
              />
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 border-t border-gray-100 pt-4">
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={!canSubmit || mutation.isPending}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? "Saving..." : isEdit ? "Update" : "Create"}
          </button>
          <button
            type="button"
            onClick={() => navigate(isEdit ? `/tables/${id}` : "/tables")}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ---- Sub-components ----

interface ColumnEditorProps {
  col: TableColumnPayload;
  idx: number;
  columns: TableColumnPayload[];
  isFirst: boolean;
  isLast: boolean;
  itemTypes: { id: string; name: string; slug: string }[];
  relationTypes: RelationType[];
  onUpdate: (patch: Partial<TableColumnPayload>) => void;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}

function ColumnEditor({
  col,
  idx,
  columns,
  isFirst,
  isLast,
  itemTypes,
  relationTypes,
  onUpdate,
  onRemove,
  onMoveUp,
  onMoveDown,
}: ColumnEditorProps) {
  const selectedRelationType = relationTypes.find(
    (rt) => rt.id === col.relation_type
  );

  const directionLabel = col.direction === "outgoing"
    ? selectedRelationType
      ? `→ ${selectedRelationType.forward_label} (this item is source)`
      : "→ Outgoing (this item is source, next items are targets)"
    : selectedRelationType
      ? `← ${selectedRelationType.reverse_label} (this item is target)`
      : "← Incoming (this item is target, next items are sources)";

  const kindLabel =
    col.column_kind === "formula"
      ? "Formula Column"
      : isFirst
        ? "Seed Column"
        : "Traversal Column";

  const kindColor =
    col.column_kind === "formula" ? "text-purple-500" : "text-gray-500";

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      {/* Column header row */}
      <div className="flex items-center gap-2">
        <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-500">
          {idx + 1}
        </div>
        {!isFirst && (
          <ChevronRight className="h-4 w-4 flex-shrink-0 text-gray-400" />
        )}
        <span className={`text-xs font-semibold uppercase tracking-wider ${kindColor}`}>
          {kindLabel}
        </span>
        <div className="ml-auto flex items-center gap-1">
          {!isFirst && (
            <button
              onClick={onMoveUp}
              disabled={idx <= 1}
              className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-30"
              title="Move up"
            >
              <ArrowUp className="h-3.5 w-3.5" />
            </button>
          )}
          {!isLast && !isFirst && (
            <button
              onClick={onMoveDown}
              className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              title="Move down"
            >
              <ArrowDown className="h-3.5 w-3.5" />
            </button>
          )}
          <button
            onClick={onRemove}
            className="rounded p-1 text-red-400 hover:bg-red-50 hover:text-red-600"
            title="Remove column"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3">
        {/* Label */}
        <div className="col-span-2">
          <label className="block text-xs font-medium text-gray-600">
            Column Label
          </label>
          <input
            type="text"
            value={col.label}
            onChange={(e) => onUpdate({ label: e.target.value })}
            placeholder={
              col.column_kind === "formula"
                ? "e.g. Risk Score"
                : isFirst
                  ? "e.g. Requirements"
                  : "e.g. Test Cases"
            }
            className="mt-1 block w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {isFirst ? (
          <SeedColumnFields
            col={col}
            itemTypes={itemTypes}
            onUpdate={onUpdate}
          />
        ) : col.column_kind === "formula" ? (
          <FormulaColumnFields
            col={col}
            columns={columns}
            idx={idx}
            onUpdate={onUpdate}
          />
        ) : (
          <TraversalColumnFields
            col={col}
            relationTypes={relationTypes}
            directionLabel={directionLabel}
            onUpdate={onUpdate}
          />
        )}
      </div>
    </div>
  );
}

function SeedColumnFields({
  col,
  itemTypes,
  onUpdate,
}: {
  col: TableColumnPayload;
  itemTypes: { id: string; name: string }[];
  onUpdate: (patch: Partial<TableColumnPayload>) => void;
}) {
  const [containerSearch, setContainerSearch] = useState("");
  const [showResults, setShowResults] = useState(false);

  const { data: containerResults } = useQuery({
    queryKey: ["items", "search", containerSearch],
    queryFn: () => getItems({ search: containerSearch }),
    enabled: containerSearch.length >= 2,
  });

  return (
    <>
      {/* Item type */}
      <div>
        <label className="block text-xs font-medium text-gray-600">
          Item Type <span className="text-red-500">*</span>
        </label>
        <select
          value={col.seed_item_type ?? ""}
          onChange={(e) =>
            onUpdate({ seed_item_type: e.target.value || null })
          }
          className="mt-1 block w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="">Select type...</option>
          {itemTypes.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </div>

      {/* Scope to container (optional) */}
      <div className="relative">
        <label className="block text-xs font-medium text-gray-600">
          Scope to Container{" "}
          <span className="font-normal text-gray-400">(optional)</span>
        </label>
        {col.seed_container ? (
          <div className="mt-1 flex items-center gap-2 rounded border border-gray-300 px-2.5 py-1.5">
            <span className="flex-1 truncate text-sm text-gray-700">
              Container selected
            </span>
            <button
              onClick={() => {
                onUpdate({ seed_container: null });
                setContainerSearch("");
              }}
              className="text-xs text-red-400 hover:text-red-600"
            >
              Clear
            </button>
          </div>
        ) : (
          <input
            type="text"
            value={containerSearch}
            onChange={(e) => {
              setContainerSearch(e.target.value);
              setShowResults(true);
            }}
            onFocus={() => setShowResults(true)}
            placeholder="Search containers..."
            className="mt-1 block w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          />
        )}
        {showResults && containerResults && containerSearch.length >= 2 && !col.seed_container && (
          <div className="absolute z-10 mt-1 max-h-40 w-full overflow-y-auto rounded border border-gray-200 bg-white shadow-md">
            {containerResults.results.length === 0 ? (
              <p className="px-3 py-2 text-xs text-gray-400">No items found</p>
            ) : (
              containerResults.results.map((item) => (
                <button
                  key={item.id}
                  onMouseDown={() => {
                    onUpdate({ seed_container: item.id });
                    setContainerSearch(item.title);
                    setShowResults(false);
                  }}
                  className="block w-full px-3 py-1.5 text-left text-sm hover:bg-gray-50"
                >
                  <span className="font-medium">{item.title}</span>
                  <span className="ml-2 text-xs text-gray-400">
                    {item.item_type_name}
                  </span>
                </button>
              ))
            )}
          </div>
        )}
      </div>
    </>
  );
}

function TraversalColumnFields({
  col,
  relationTypes,
  directionLabel,
  onUpdate,
}: {
  col: TableColumnPayload;
  relationTypes: RelationType[];
  directionLabel: string;
  onUpdate: (patch: Partial<TableColumnPayload>) => void;
}) {
  const selectedRt = relationTypes.find((rt) => rt.id === col.relation_type);

  function handleRelationChange(rtId: string) {
    const rt = relationTypes.find((r) => r.id === rtId);
    onUpdate({
      relation_type: rtId || null,
      // Auto-fill label from relation label if label is currently empty
      label: col.label
        ? col.label
        : col.direction === "outgoing"
          ? (rt?.forward_label ?? "")
          : (rt?.reverse_label ?? ""),
    });
  }

  function handleDirectionChange(dir: "outgoing" | "incoming") {
    onUpdate({
      direction: dir,
      // Update auto-filled label if it matches the old auto-fill
      label: col.label
        ? col.label
        : dir === "outgoing"
          ? (selectedRt?.forward_label ?? "")
          : (selectedRt?.reverse_label ?? ""),
    });
  }

  return (
    <>
      {/* Relation type */}
      <div>
        <label className="block text-xs font-medium text-gray-600">
          Relation Type <span className="text-red-500">*</span>
        </label>
        <select
          value={col.relation_type ?? ""}
          onChange={(e) => handleRelationChange(e.target.value)}
          className="mt-1 block w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="">Select relation...</option>
          {relationTypes.map((rt) => (
            <option key={rt.id} value={rt.id}>
              {rt.name}
            </option>
          ))}
        </select>
      </div>

      {/* Direction */}
      <div>
        <label className="block text-xs font-medium text-gray-600">
          Direction <span className="text-red-500">*</span>
        </label>
        <select
          value={col.direction ?? "outgoing"}
          onChange={(e) =>
            handleDirectionChange(e.target.value as "outgoing" | "incoming")
          }
          className="mt-1 block w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="outgoing">→ Outgoing (follow to targets)</option>
          <option value="incoming">← Incoming (follow to sources)</option>
        </select>
      </div>

      {/* Direction hint */}
      {selectedRt && (
        <div className="col-span-2 rounded bg-blue-50 px-3 py-2 text-xs text-blue-700">
          {directionLabel}
        </div>
      )}
    </>
  );
}

function FormulaColumnFields({
  col,
  columns,
  idx,
  onUpdate,
}: {
  col: TableColumnPayload;
  columns: TableColumnPayload[];
  idx: number;
  onUpdate: (patch: Partial<TableColumnPayload>) => void;
}) {
  // Build reference hints from preceding columns
  const refHints = columns
    .filter((_, i) => i < idx && columns[i].column_kind !== "formula")
    .map((c) => `$${c.position + 1}`);

  return (
    <div className="col-span-2">
      <label className="block text-xs font-medium text-gray-600">
        Formula <span className="text-red-500">*</span>
      </label>
      <input
        type="text"
        value={col.formula ?? ""}
        onChange={(e) => onUpdate({ formula: e.target.value })}
        placeholder="e.g. $1.threat-level * $2.severity"
        className="mt-1 block w-full rounded border border-gray-300 px-2.5 py-1.5 font-mono text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
      />
      <p className="mt-1.5 text-xs text-gray-400">
        Use <code className="rounded bg-gray-100 px-1">$N.field-slug</code> to
        reference a custom field from column N.
        {refHints.length > 0 && (
          <>
            {" "}Available columns:{" "}
            {refHints.map((h, i) => (
              <span key={i}>
                {i > 0 && ", "}
                <code className="rounded bg-gray-100 px-1">{h}</code>
              </span>
            ))}
          </>
        )}
        . Supports <code className="rounded bg-gray-100 px-1">+ - * / ( )</code>.
        Choice fields are converted to numbers (1-based index).
      </p>
    </div>
  );
}
