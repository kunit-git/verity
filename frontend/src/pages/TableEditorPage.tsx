import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  ChevronRight,
  Code,
  LayoutList,
  Undo2,
} from "lucide-react";
import { getTable, createTable, updateTable } from "../api/tables";
import { getItemTypes, getItems } from "../api/items";
import { getRelationTypes } from "../api/relations";
import type {
  TableSourcePayload,
  TableDisplayColumnPayload,
  RelationType,
  SourceKind,
  Table,
} from "../types";

type EditorMode = "visual" | "text";

const VALID_SOURCE_KINDS: SourceKind[] = ["seed", "traversal", "formula", "annotation", "item_field"];
const VALID_DIRECTIONS = ["outgoing", "incoming"];

function validateJson(parsed: unknown): {
  ok: true;
  sources: TableSourcePayload[];
  columns: TableDisplayColumnPayload[];
} | { ok: false; error: string } {
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return { ok: false, error: 'Top-level value must be an object with "sources" and "columns".' };
  }
  const obj = parsed as Record<string, unknown>;

  // Validate sources
  if (!Array.isArray(obj.sources)) {
    return { ok: false, error: '"sources" must be an array.' };
  }
  if (obj.sources.length === 0) {
    return { ok: false, error: "At least one source is required." };
  }
  const names = new Set<string>();
  for (let i = 0; i < obj.sources.length; i++) {
    const src = obj.sources[i] as Record<string, unknown>;
    if (typeof src !== "object" || src === null) {
      return { ok: false, error: `Source ${i + 1}: must be an object.` };
    }
    if (typeof src.name !== "string" || !src.name) {
      return { ok: false, error: `Source ${i + 1}: "name" is required.` };
    }
    if (names.has(src.name)) {
      return { ok: false, error: `Source ${i + 1}: name "${src.name}" is not unique.` };
    }
    names.add(src.name);
    if (typeof src.kind !== "string" || !VALID_SOURCE_KINDS.includes(src.kind as SourceKind)) {
      return { ok: false, error: `Source ${i + 1}: "kind" must be one of: ${VALID_SOURCE_KINDS.join(", ")}.` };
    }
    if (i === 0 && src.kind !== "seed") {
      return { ok: false, error: 'First source must be a "seed".' };
    }
    if (src.direction !== undefined && src.direction !== null && !VALID_DIRECTIONS.includes(src.direction as string)) {
      return { ok: false, error: `Source ${i + 1}: "direction" must be "outgoing" or "incoming".` };
    }
  }

  // Validate columns
  if (!Array.isArray(obj.columns)) {
    return { ok: false, error: '"columns" must be an array.' };
  }
  for (let i = 0; i < obj.columns.length; i++) {
    const col = obj.columns[i] as Record<string, unknown>;
    if (typeof col !== "object" || col === null) {
      return { ok: false, error: `Column ${i + 1}: must be an object.` };
    }
    if (typeof col.heading !== "string") {
      return { ok: false, error: `Column ${i + 1}: "heading" must be a string.` };
    }
    if (typeof col.source !== "string" || !names.has(col.source)) {
      return { ok: false, error: `Column ${i + 1}: "source" must reference a defined source name.` };
    }
  }

  return {
    ok: true,
    sources: obj.sources as TableSourcePayload[],
    columns: obj.columns as TableDisplayColumnPayload[],
  };
}

export default function TableEditorPage() {
  const { id } = useParams<{ id: string }>();
  const { data: existingTable, isError } = useQuery({
    queryKey: ["table", id],
    queryFn: () => getTable(id!),
    enabled: !!id,
  });
  if (id && isError) return <p className="p-6 text-red-600">Unable to load table.</p>;
  if (id && !existingTable) return <p className="p-6">Loading table…</p>;
  return <TableEditor key={id ?? "new"} id={id} existingTable={existingTable} />;
}

function TableEditor({ id, existingTable }: { id?: string; existingTable?: Table }) {
  const isEdit = !!id;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: itemTypes } = useQuery({
    queryKey: ["itemTypes"],
    queryFn: getItemTypes,
  });
  const { data: relationTypes } = useQuery({
    queryKey: ["relationTypes"],
    queryFn: getRelationTypes,
  });

  const [name, setName] = useState(existingTable?.name ?? "");
  const [description, setDescription] = useState(existingTable?.description ?? "");
  const [sources, setSources] = useState<TableSourcePayload[]>(() =>
    existingTable?.sources.map((s) => ({
      name: s.name, kind: s.kind, seed_item_type: s.seed_item_type,
      seed_container: s.seed_container, relation_type: s.relation_type,
      direction: s.direction, formula: s.formula, source_ref: s.source_ref,
      field_slug: s.field_slug,
    })) ?? []
  );
  const [displayColumns, setDisplayColumns] = useState<TableDisplayColumnPayload[]>(() =>
    existingTable?.columns.map((c) => ({ heading: c.heading, source: c.source })) ?? []
  );
  const [error, setError] = useState("");

  // Editor mode: visual or text (JSON)
  const [mode, setMode] = useState<EditorMode>("visual");
  const [jsonText, setJsonText] = useState("");
  const [jsonError, setJsonError] = useState("");
  const [jsonRevertSnapshot, setJsonRevertSnapshot] = useState("");

  // ---- Source management ----

  function addSource(kind: SourceKind) {
    const baseName = kind === "seed" ? "seed" : `${kind}-${sources.length}`;
    const newSource: TableSourcePayload = { name: baseName, kind };
    if (kind === "seed") {
      newSource.seed_item_type = null;
      newSource.seed_container = null;
    } else if (kind === "traversal") {
      newSource.relation_type = null;
      newSource.direction = "outgoing";
    } else if (kind === "formula") {
      newSource.formula = "";
    } else if (kind === "item_field") {
      newSource.source_ref = "";
      newSource.field_slug = "";
    }
    setSources((prev) => [...prev, newSource]);
    // Auto-add a display column for this source
    setDisplayColumns((prev) => [...prev, { heading: "", source: baseName }]);
  }

  function removeSource(idx: number) {
    const removedName = sources[idx].name;
    setSources((prev) => prev.filter((_, i) => i !== idx));
    // Remove display columns that reference this source
    setDisplayColumns((prev) => prev.filter((c) => c.source !== removedName));
  }

  function moveSource(idx: number, dir: "up" | "down") {
    setSources((prev) => {
      const next = [...prev];
      const swap = dir === "up" ? idx - 1 : idx + 1;
      if (swap < 0 || swap >= next.length) return prev;
      if (idx === 0 || swap === 0) return prev; // Seed stays at 0
      [next[idx], next[swap]] = [next[swap], next[idx]];
      return next;
    });
  }

  function updateSource(idx: number, patch: Partial<TableSourcePayload>) {
    setSources((prev) => {
      const old = prev[idx];
      const updated = { ...old, ...patch };
      // If name changed, update display columns that reference the old name
      if (patch.name && patch.name !== old.name) {
        setDisplayColumns((cols) =>
          cols.map((c) =>
            c.source === old.name ? { ...c, source: patch.name! } : c
          )
        );
      }
      return prev.map((s, i) => (i === idx ? updated : s));
    });
  }

  // ---- Display column management ----

  function addDisplayColumn() {
    setDisplayColumns((prev) => [
      ...prev,
      { heading: "", source: sources[0]?.name ?? "" },
    ]);
  }

  function removeDisplayColumn(idx: number) {
    setDisplayColumns((prev) => prev.filter((_, i) => i !== idx));
  }

  function moveDisplayColumn(idx: number, dir: "up" | "down") {
    setDisplayColumns((prev) => {
      const next = [...prev];
      const swap = dir === "up" ? idx - 1 : idx + 1;
      if (swap < 0 || swap >= next.length) return prev;
      [next[idx], next[swap]] = [next[swap], next[idx]];
      return next;
    });
  }

  function updateDisplayColumn(idx: number, patch: Partial<TableDisplayColumnPayload>) {
    setDisplayColumns((prev) =>
      prev.map((c, i) => (i === idx ? { ...c, ...patch } : c))
    );
  }

  // ---- Mode switching ----

  function toJsonText(): string {
    return JSON.stringify({ sources, columns: displayColumns }, null, 2);
  }

  function switchToText() {
    const text = toJsonText();
    setJsonText(text);
    setJsonRevertSnapshot(text);
    setJsonError("");
    setMode("text");
  }

  function switchToVisual() {
    let parsed: unknown;
    try {
      parsed = JSON.parse(jsonText);
    } catch (e) {
      setJsonError(`Invalid JSON: ${(e as Error).message}`);
      return;
    }
    const result = validateJson(parsed);
    if (!result.ok) {
      setJsonError(result.error);
      return;
    }
    setSources(result.sources);
    setDisplayColumns(result.columns);
    setJsonError("");
    setMode("visual");
  }

  function revertJson() {
    setJsonText(jsonRevertSnapshot);
    setJsonError("");
  }

  // ---- Submission ----

  const mutation = useMutation({
    mutationFn: () => {
      let finalSources = sources;
      let finalColumns = displayColumns;
      if (mode === "text") {
        let parsed: unknown;
        try {
          parsed = JSON.parse(jsonText);
        } catch (e) {
          throw new Error(`Invalid JSON: ${(e as Error).message}`);
        }
        const result = validateJson(parsed);
        if (!result.ok) throw new Error(result.error);
        finalSources = result.sources;
        finalColumns = result.columns;
      }
      const payload = {
        name,
        description,
        sources: finalSources,
        columns: finalColumns,
      };
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

  const sourceNames = new Set(sources.map((s) => s.name));
  const canSubmit =
    name.trim() &&
    sources.length >= 1 &&
    sources[0]?.kind === "seed" &&
    sources[0]?.seed_item_type &&
    sources.every((s) => s.name.trim()) &&
    new Set(sources.map((s) => s.name)).size === sources.length &&
    sources.slice(1).every((s) => {
      if (s.kind === "traversal") return s.relation_type && s.direction;
      if (s.kind === "formula") return !!s.formula?.trim();
      if (s.kind === "item_field") return !!s.source_ref?.trim() && !!s.field_slug?.trim();
      if (s.kind === "annotation") return true;
      return false;
    }) &&
    displayColumns.length >= 1 &&
    displayColumns.every((c) => c.heading.trim() && sourceNames.has(c.source));

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-bold text-gray-900">
        {isEdit ? "Edit Table" : "New Table"}
      </h1>
      <p className="mt-1 text-sm text-gray-500">
        Define data sources and display columns. Sources define the data pipeline;
        columns define how data is displayed.
      </p>

      <div className="mt-6 space-y-5">
        {error && (
          <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Name & description */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Table Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="e.g. Requirements Traceability"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Mode toggle */}
        <div className="flex items-center justify-end">
          <div className="flex rounded-md border border-gray-300 bg-gray-50">
            <button
              type="button"
              onClick={() => mode === "text" ? switchToVisual() : undefined}
              className={`flex items-center gap-1 rounded-l-md px-2.5 py-1 text-xs font-medium transition-colors ${
                mode === "visual"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <LayoutList className="h-3.5 w-3.5" />
              Visual
            </button>
            <button
              type="button"
              onClick={() => mode === "visual" ? switchToText() : undefined}
              className={`flex items-center gap-1 rounded-r-md px-2.5 py-1 text-xs font-medium transition-colors ${
                mode === "text"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <Code className="h-3.5 w-3.5" />
              Text
            </button>
          </div>
        </div>

        {mode === "visual" ? (
          <div className="grid grid-cols-2 gap-6">
            {/* Left pane: Sources */}
            <div>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-700">Sources</h2>
                <div className="flex flex-wrap items-center gap-1">
                  {sources.length === 0 ? (
                    <button
                      type="button"
                      onClick={() => addSource("seed")}
                      className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700"
                    >
                      <Plus className="h-3 w-3" />
                      Seed
                    </button>
                  ) : (
                    <>
                      <button type="button" onClick={() => addSource("traversal")} className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700">
                        <Plus className="h-3 w-3" /> Traversal
                      </button>
                      <button type="button" onClick={() => addSource("item_field")} className="flex items-center gap-1 text-xs text-orange-600 hover:text-orange-700">
                        <Plus className="h-3 w-3" /> Field
                      </button>
                      <button type="button" onClick={() => addSource("annotation")} className="flex items-center gap-1 text-xs text-green-600 hover:text-green-700">
                        <Plus className="h-3 w-3" /> Annotation
                      </button>
                      <button type="button" onClick={() => addSource("formula")} className="flex items-center gap-1 text-xs text-purple-600 hover:text-purple-700">
                        <Plus className="h-3 w-3" /> Formula
                      </button>
                    </>
                  )}
                </div>
              </div>
              <p className="mt-1 text-xs text-gray-400">
                Order matters — traversal sources expand rows left to right.
              </p>

              <div className="mt-3 space-y-3">
                {sources.map((src, idx) => (
                  <SourceEditor
                    key={idx}
                    src={src}
                    idx={idx}
                    sources={sources}
                    isFirst={idx === 0}
                    isLast={idx === sources.length - 1}
                    itemTypes={itemTypes ?? []}
                    relationTypes={relationTypes ?? []}
                    onUpdate={(patch) => updateSource(idx, patch)}
                    onRemove={() => removeSource(idx)}
                    onMoveUp={() => moveSource(idx, "up")}
                    onMoveDown={() => moveSource(idx, "down")}
                  />
                ))}
              </div>
            </div>

            {/* Right pane: Display Columns */}
            <div>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-700">Display Columns</h2>
                <button
                  type="button"
                  onClick={addDisplayColumn}
                  disabled={sources.length === 0}
                  className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 disabled:opacity-30"
                >
                  <Plus className="h-3 w-3" />
                  Column
                </button>
              </div>
              <p className="mt-1 text-xs text-gray-400">
                Each column displays data from a source. One source can appear in multiple columns.
              </p>

              <div className="mt-3 space-y-2">
                {displayColumns.map((col, idx) => (
                  <DisplayColumnEditor
                    key={idx}
                    col={col}
                    idx={idx}
                    isFirst={idx === 0}
                    isLast={idx === displayColumns.length - 1}
                    sourceNames={sources.map((s) => s.name)}
                    onUpdate={(patch) => updateDisplayColumn(idx, patch)}
                    onRemove={() => removeDisplayColumn(idx)}
                    onMoveUp={() => moveDisplayColumn(idx, "up")}
                    onMoveDown={() => moveDisplayColumn(idx, "down")}
                  />
                ))}
                {displayColumns.length === 0 && sources.length > 0 && (
                  <p className="text-xs text-gray-400">
                    No display columns yet — add one to show source data.
                  </p>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div>
            {jsonError && (
              <div className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                {jsonError}
              </div>
            )}
            <textarea
              value={jsonText}
              onChange={(e) => { setJsonText(e.target.value); setJsonError(""); }}
              spellCheck={false}
              rows={Math.max(16, jsonText.split("\n").length + 2)}
              className={`block w-full rounded-md border px-3 py-2 font-mono text-sm leading-relaxed focus:outline-none focus:ring-1 ${
                jsonError
                  ? "border-red-300 focus:border-red-500 focus:ring-red-500"
                  : "border-gray-300 focus:border-blue-500 focus:ring-blue-500"
              }`}
            />
            <div className="mt-2 flex items-center justify-between">
              <p className="text-xs text-gray-400">
                Edit sources and columns as JSON.
              </p>
              <button
                type="button"
                onClick={revertJson}
                disabled={jsonText === jsonRevertSnapshot}
                className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 disabled:opacity-30"
              >
                <Undo2 className="h-3.5 w-3.5" />
                Revert
              </button>
            </div>
          </div>
        )}

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

// ---- Source Editor ----

function SourceEditor({
  src,
  idx,
  sources,
  isFirst,
  isLast,
  itemTypes,
  relationTypes,
  onUpdate,
  onRemove,
  onMoveUp,
  onMoveDown,
}: {
  src: TableSourcePayload;
  idx: number;
  sources: TableSourcePayload[];
  isFirst: boolean;
  isLast: boolean;
  itemTypes: { id: string; name: string; slug: string }[];
  relationTypes: RelationType[];
  onUpdate: (patch: Partial<TableSourcePayload>) => void;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  const kindColor =
    src.kind === "formula" ? "text-purple-500"
    : src.kind === "annotation" ? "text-green-600"
    : src.kind === "item_field" ? "text-orange-600"
    : "text-blue-600";

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3">
      <div className="flex items-center gap-2">
        {!isFirst && <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" />}
        <span className={`text-[10px] font-semibold uppercase tracking-wider ${kindColor}`}>
          {src.kind}
        </span>
        <div className="ml-auto flex items-center gap-0.5">
          {!isFirst && (
            <button onClick={onMoveUp} disabled={idx <= 1} className="rounded p-0.5 text-gray-400 hover:bg-gray-100 disabled:opacity-30" title="Move up">
              <ArrowUp className="h-3 w-3" />
            </button>
          )}
          {!isLast && !isFirst && (
            <button onClick={onMoveDown} className="rounded p-0.5 text-gray-400 hover:bg-gray-100" title="Move down">
              <ArrowDown className="h-3 w-3" />
            </button>
          )}
          <button onClick={onRemove} className="rounded p-0.5 text-red-400 hover:bg-red-50 hover:text-red-600" title="Remove">
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-2">
        {/* Name field */}
        <div className="col-span-2">
          <label className="block text-[10px] font-medium text-gray-500">Name <span className="text-red-500">*</span></label>
          <input
            type="text"
            value={src.name}
            onChange={(e) => onUpdate({ name: e.target.value })}
            placeholder="e.g. reqs"
            className="mt-0.5 block w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs focus:border-blue-400 focus:outline-none"
          />
        </div>

        {src.kind === "seed" && (
          <SeedSourceFields src={src} itemTypes={itemTypes} onUpdate={onUpdate} />
        )}
        {src.kind === "traversal" && (
          <TraversalSourceFields src={src} relationTypes={relationTypes} onUpdate={onUpdate} />
        )}
        {src.kind === "formula" && (
          <FormulaSourceFields src={src} sources={sources} onUpdate={onUpdate} />
        )}
        {src.kind === "item_field" && (
          <ItemFieldSourceFields src={src} sources={sources} onUpdate={onUpdate} />
        )}
        {/* Annotation: no additional fields needed beyond name */}
      </div>
    </div>
  );
}

function SeedSourceFields({
  src,
  itemTypes,
  onUpdate,
}: {
  src: TableSourcePayload;
  itemTypes: { id: string; name: string }[];
  onUpdate: (patch: Partial<TableSourcePayload>) => void;
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
      <div>
        <label className="block text-[10px] font-medium text-gray-500">
          Item Type <span className="text-red-500">*</span>
        </label>
        <select
          value={src.seed_item_type ?? ""}
          onChange={(e) => onUpdate({ seed_item_type: e.target.value || null })}
          className="mt-0.5 block w-full rounded border border-gray-300 px-2 py-1 text-xs focus:outline-none"
        >
          <option value="">Select type...</option>
          {itemTypes.map((t) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
      </div>
      <div className="relative">
        <label className="block text-[10px] font-medium text-gray-500">
          Container <span className="font-normal text-gray-400">(optional)</span>
        </label>
        {src.seed_container ? (
          <div className="mt-0.5 flex items-center gap-1 rounded border border-gray-300 px-2 py-1">
            <span className="flex-1 truncate text-xs text-gray-700">Selected</span>
            <button onClick={() => { onUpdate({ seed_container: null }); setContainerSearch(""); }} className="text-[10px] text-red-400 hover:text-red-600">
              Clear
            </button>
          </div>
        ) : (
          <input
            type="text"
            value={containerSearch}
            onChange={(e) => { setContainerSearch(e.target.value); setShowResults(true); }}
            onFocus={() => setShowResults(true)}
            placeholder="Search..."
            className="mt-0.5 block w-full rounded border border-gray-300 px-2 py-1 text-xs focus:outline-none"
          />
        )}
        {showResults && containerResults && containerSearch.length >= 2 && !src.seed_container && (
          <div className="absolute z-10 mt-1 max-h-32 w-full overflow-y-auto rounded border border-gray-200 bg-white shadow-md">
            {containerResults.results.length === 0 ? (
              <p className="px-2 py-1 text-[10px] text-gray-400">No items found</p>
            ) : (
              containerResults.results.map((item) => (
                <button
                  key={item.id}
                  onMouseDown={() => {
                    onUpdate({ seed_container: item.id });
                    setContainerSearch(item.title);
                    setShowResults(false);
                  }}
                  className="block w-full px-2 py-1 text-left text-xs hover:bg-gray-50"
                >
                  <span className="font-medium">{item.title}</span>
                  <span className="ml-1 text-[10px] text-gray-400">{item.item_type_name}</span>
                </button>
              ))
            )}
          </div>
        )}
      </div>
    </>
  );
}

function TraversalSourceFields({
  src,
  relationTypes,
  onUpdate,
}: {
  src: TableSourcePayload;
  relationTypes: RelationType[];
  onUpdate: (patch: Partial<TableSourcePayload>) => void;
}) {
  return (
    <>
      <div>
        <label className="block text-[10px] font-medium text-gray-500">
          Relation Type <span className="text-red-500">*</span>
        </label>
        <select
          value={src.relation_type ?? ""}
          onChange={(e) => onUpdate({ relation_type: e.target.value || null })}
          className="mt-0.5 block w-full rounded border border-gray-300 px-2 py-1 text-xs focus:outline-none"
        >
          <option value="">Select...</option>
          {relationTypes.map((rt) => (
            <option key={rt.id} value={rt.id}>{rt.name}</option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-[10px] font-medium text-gray-500">
          Direction <span className="text-red-500">*</span>
        </label>
        <select
          value={src.direction ?? "outgoing"}
          onChange={(e) => onUpdate({ direction: e.target.value as "outgoing" | "incoming" })}
          className="mt-0.5 block w-full rounded border border-gray-300 px-2 py-1 text-xs focus:outline-none"
        >
          <option value="outgoing">&rarr; Outgoing</option>
          <option value="incoming">&larr; Incoming</option>
        </select>
      </div>
    </>
  );
}

function FormulaSourceFields({
  src,
  sources,
  onUpdate,
}: {
  src: TableSourcePayload;
  sources: TableSourcePayload[];
  onUpdate: (patch: Partial<TableSourcePayload>) => void;
}) {
  const refs = sources
    .filter((s) => s.kind !== "formula" && s.name)
    .map((s) => `$${s.name}`);

  return (
    <div className="col-span-2">
      <label className="block text-[10px] font-medium text-gray-500">
        Formula <span className="text-red-500">*</span>
      </label>
      <input
        type="text"
        value={src.formula ?? ""}
        onChange={(e) => onUpdate({ formula: e.target.value })}
        placeholder="e.g. $reqs.weight * $tests.score"
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

function ItemFieldSourceFields({
  src,
  sources,
  onUpdate,
}: {
  src: TableSourcePayload;
  sources: TableSourcePayload[];
  onUpdate: (patch: Partial<TableSourcePayload>) => void;
}) {
  const refSources = sources
    .filter((s) => s.kind === "seed" || s.kind === "traversal")
    .map((s) => ({ name: s.name }));

  return (
    <>
      <div>
        <label className="block text-[10px] font-medium text-gray-500">
          Source <span className="text-red-500">*</span>
        </label>
        <select
          value={src.source_ref ?? ""}
          onChange={(e) => onUpdate({ source_ref: e.target.value || null })}
          className="mt-0.5 block w-full rounded border border-gray-300 px-2 py-1 text-xs focus:outline-none"
        >
          <option value="">Select source...</option>
          {refSources.map((s) => (
            <option key={s.name} value={s.name}>{s.name}</option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-[10px] font-medium text-gray-500">
          Field Slug <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          value={src.field_slug ?? ""}
          onChange={(e) => onUpdate({ field_slug: e.target.value })}
          placeholder="e.g. severity"
          className="mt-0.5 block w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs focus:border-orange-400 focus:outline-none"
        />
      </div>
    </>
  );
}

// ---- Display Column Editor ----

function DisplayColumnEditor({
  col,
  idx,
  isFirst,
  isLast,
  sourceNames,
  onUpdate,
  onRemove,
  onMoveUp,
  onMoveDown,
}: {
  col: TableDisplayColumnPayload;
  idx: number;
  isFirst: boolean;
  isLast: boolean;
  sourceNames: string[];
  onUpdate: (patch: Partial<TableDisplayColumnPayload>) => void;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  return (
    <div className="flex items-center gap-2 rounded border border-gray-200 bg-white px-3 py-2">
      <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-gray-100 text-[10px] font-semibold text-gray-500">
        {idx + 1}
      </div>
      <input
        type="text"
        value={col.heading}
        onChange={(e) => onUpdate({ heading: e.target.value })}
        placeholder="Heading"
        className="min-w-0 flex-1 rounded border border-gray-300 px-2 py-1 text-xs focus:border-blue-400 focus:outline-none"
      />
      <select
        value={col.source}
        onChange={(e) => onUpdate({ source: e.target.value })}
        className="rounded border border-gray-300 px-2 py-1 font-mono text-xs focus:outline-none"
      >
        <option value="">Source...</option>
        {sourceNames.map((n) => (
          <option key={n} value={n}>{n}</option>
        ))}
      </select>
      <div className="flex items-center gap-0.5">
        {!isFirst && (
          <button onClick={onMoveUp} className="rounded p-0.5 text-gray-400 hover:bg-gray-100" title="Move up">
            <ArrowUp className="h-3 w-3" />
          </button>
        )}
        {!isLast && (
          <button onClick={onMoveDown} className="rounded p-0.5 text-gray-400 hover:bg-gray-100" title="Move down">
            <ArrowDown className="h-3 w-3" />
          </button>
        )}
        <button onClick={onRemove} className="rounded p-0.5 text-red-400 hover:bg-red-50 hover:text-red-600" title="Remove">
          <Trash2 className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}
