import { useState, useEffect, useRef, useCallback, useMemo, Fragment } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowUp, ArrowDown, Save, Loader2, Check, AlertTriangle, RefreshCw, RotateCcw, Trash2, Undo2, Plus, X, ChevronDown, ChevronRight } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getDocumentEditorData, updateItem, getItem, deleteItem, getItemTypes, createItem, reorderChildren, getDocumentTemplate } from "../api/items";
import { getRelationTypes, createRelation } from "../api/relations";
import type { EditorItem, EditorFieldDefinition, ItemType } from "../types";
import type { ReactNode } from "react";
import MermaidDiagram from "../components/MermaidDiagram";
import TableFieldWidget from "../components/TableFieldWidget";

// ── constants ──────────────────────────────────────────────────────────────

const STATUS_OPTIONS = [
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "in_review", label: "In Review" },
  { value: "approved", label: "Approved" },
  { value: "archived", label: "Archived" },
];

const READONLY_FIELDS = new Set([
  "heading", "id", "item_type", "current_version",
  "created_by", "created_at", "updated_at",
]);

const DEPTH_COLORS = [
  "border-blue-400",
  "border-emerald-400",
  "border-violet-400",
  "border-amber-400",
  "border-rose-400",
  "border-teal-400",
];

// Unique marker that won't appear in normal markdown
const FIELD_MARKER = /\u200B\u200BFIELD:([\w-]+)\u200B\u200B/g;
function fieldMarker(name: string) {
  return `\u200B\u200BFIELD:${name}\u200B\u200B`;
}

// ── template preprocessing ──────────────────────────────────────────────────

function getReadonlyValue(name: string, item: EditorItem): string {
  switch (name) {
    case "heading": return "#".repeat(Math.min(item.depth, 6));
    case "id": return item.id;
    case "item_type": return item.item_type_name;
    case "current_version": return String(item.current_version);
    case "created_by": return item.created_by;
    case "created_at": return item.created_at;
    case "updated_at": return item.updated_at;
    default: return "";
  }
}

/** Replace {{field}} with either its read-only value or a zero-width marker. */
function preprocessTemplate(template: string, item: EditorItem): string {
  return template.replace(/\{\{([\w-]+)\}\}/g, (_, name) => {
    if (READONLY_FIELDS.has(name)) return getReadonlyValue(name, item);
    return fieldMarker(name);
  });
}

// ── inject editable widgets into ReactMarkdown children ────────────────────

type FieldRenderer = (name: string) => ReactNode;

/**
 * Walk react-markdown's rendered children recursively.
 * When a string containing a field marker is found, split it and inject
 * the editable widget returned by renderField.
 */
function injectFields(children: ReactNode, renderField: FieldRenderer): ReactNode {
  if (typeof children === "string") {
    FIELD_MARKER.lastIndex = 0;
    if (!FIELD_MARKER.test(children)) return children;
    FIELD_MARKER.lastIndex = 0;

    const parts: ReactNode[] = [];
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = FIELD_MARKER.exec(children)) !== null) {
      if (m.index > last) parts.push(children.slice(last, m.index));
      parts.push(renderField(m[1]));
      last = m.index + m[0].length;
    }
    if (last < children.length) parts.push(children.slice(last));
    return parts.map((p, i) => <Fragment key={i}>{p}</Fragment>);
  }

  if (Array.isArray(children)) {
    return (children as ReactNode[]).map((c, i) => (
      <Fragment key={i}>{injectFields(c, renderField)}</Fragment>
    ));
  }

  // React element — recurse into its children
  if (
    children !== null &&
    typeof children === "object" &&
    "props" in (children as object)
  ) {
    const el = children as React.ReactElement<{ children?: ReactNode }>;
    if (el.props?.children == null) return el;
    const next = injectFields(el.props.children, renderField);
    return { ...el, props: { ...el.props, children: next } };
  }

  return children;
}

/** Build the components map for ReactMarkdown, injecting editable fields. */
function makeComponents(renderField: FieldRenderer) {
  function Wrap({
    as: Tag,
    children,
    ...rest
  }: { as: string; children?: ReactNode; [k: string]: unknown }) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const T = Tag as any;
    return <T {...rest}>{injectFields(children, renderField)}</T>;
  }

  const tags = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "strong", "em", "blockquote", "table", "thead", "tbody", "tr", "th", "td"];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const comps: Record<string, (props: any) => ReactNode> = {};
  for (const tag of tags) {
    comps[tag] = ({ node: _node, children, ...rest }) => (
      <Wrap as={tag} {...rest}>{children}</Wrap>
    );
  }
  return comps;
}

// ── state types ─────────────────────────────────────────────────────────────

interface FieldValues {
  title: string;
  description: string;
  status: string;
  custom_fields: Record<string, unknown>;
}

type SaveError = null | "conflict" | string;

interface EditEntry {
  values: FieldValues;
  originalVersion: number;
  isDirty: boolean;
  saveError: SaveError;
  isMarkedForDeletion: boolean;
}

type EditState = Record<string, EditEntry>;

interface PendingItem {
  clientId: string;
  parentId: string;
  /** real item ID to insert after within the parent's children; null = prepend */
  insertAfterId: string | null;
  depth: number;
  itemTypeId: string;
  itemTypeName: string;
  values: FieldValues;
  saveError: string | null;
}

// ── tree helpers ─────────────────────────────────────────────────────────────

/** Walk backwards from idx to find the nearest ancestor with depth = target.depth - 1. */
function findParentIdx(items: EditorItem[], idx: number): number | null {
  const targetDepth = items[idx].depth - 1;
  if (targetDepth <= 0) return null;
  for (let i = idx - 1; i >= 0; i--) {
    if (items[i].depth === targetDepth) return i;
  }
  return null;
}

/** Return the config for inserting a new item "after items[afterIdx]". */
function getInsertConfig(
  items: EditorItem[],
  afterIdx: number,
): { parentId: string; insertAfterId: string | null; depth: number } | null {
  const above = items[afterIdx];
  const below = items[afterIdx + 1];
  if (below && below.depth > above.depth) {
    // Insert as first child of `above`
    return { parentId: above.id, insertAfterId: null, depth: above.depth + 1 };
  }
  // Insert as sibling of `above`, right after it
  const parentIdx = findParentIdx(items, afterIdx);
  if (parentIdx === null) return null; // can't insert sibling of root
  return { parentId: items[parentIdx].id, insertAfterId: above.id, depth: above.depth };
}

/** Compute final ordered child IDs for a parent after inserting pending items. */
function buildChildOrder(
  items: EditorItem[],
  parentIdx: number,
  pendingForParent: PendingItem[],
  clientIdToRealId: Map<string, string>,
): string[] {
  const parent = items[parentIdx];
  const realChildren: EditorItem[] = [];
  for (let i = parentIdx + 1; i < items.length; i++) {
    if (items[i].depth <= parent.depth) break;
    if (items[i].depth === parent.depth + 1) realChildren.push(items[i]);
  }
  const result: string[] = [
    ...pendingForParent.filter((p) => p.insertAfterId === null).map((p) => clientIdToRealId.get(p.clientId)!).filter(Boolean),
  ];
  for (const child of realChildren) {
    result.push(child.id);
    pendingForParent
      .filter((p) => p.insertAfterId === child.id)
      .forEach((p) => { const rid = clientIdToRealId.get(p.clientId); if (rid) result.push(rid); });
  }
  return result;
}

function initEntry(item: EditorItem): EditEntry {
  return {
    values: {
      title: item.title,
      description: item.description,
      status: item.status,
      custom_fields: { ...item.custom_fields },
    },
    originalVersion: item.current_version,
    isDirty: false,
    saveError: null,
    isMarkedForDeletion: false,
  };
}

function checkDirty(item: EditorItem, values: FieldValues): boolean {
  if (values.title !== item.title) return true;
  if (values.description !== item.description) return true;
  if (values.status !== item.status) return true;
  for (const [key, val] of Object.entries(values.custom_fields)) {
    if (String(val ?? "") !== String(item.custom_fields[key] ?? "")) return true;
  }
  return false;
}

// ── page ────────────────────────────────────────────────────────────────────

export default function DocumentEditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["editor-data", id],
    queryFn: () => getDocumentEditorData(id!),
    enabled: !!id,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  const [editState, setEditState] = useState<EditState>({});
  const [pendingItems, setPendingItems] = useState<PendingItem[]>([]);
  const [addingAtIndex, setAddingAtIndex] = useState<number | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [collapsedItems, setCollapsedItems] = useState<Set<string>>(new Set());
  const [reorderedParents, setReorderedParents] = useState<Set<string>>(new Set());

  const toggleCollapse = useCallback((id: string) => {
    setCollapsedItems((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const skippedItemIds = useMemo(() => {
    const items = data?.items ?? [];
    const skipped = new Set<string>();
    items.forEach((item, idx) => {
      if (collapsedItems.has(item.id)) {
        for (let i = idx + 1; i < items.length; i++) {
          if (items[i].depth > item.depth) skipped.add(items[i].id);
          else break;
        }
      }
    });
    return skipped;
  }, [data?.items, collapsedItems]);

  const { data: itemTypes = [] } = useQuery({
    queryKey: ["item-types"],
    queryFn: getItemTypes,
    staleTime: 5 * 60 * 1000,
  });
  const { data: relationTypes = [] } = useQuery({
    queryKey: ["relationTypes"],
    queryFn: getRelationTypes,
    staleTime: 5 * 60 * 1000,
  });
  const compositionTypeId = relationTypes.find((rt) => rt.kind === "composition")?.id;

  useEffect(() => {
    if (data) {
      setEditState((prev) => {
        const next: EditState = {};
        for (const item of data.items) {
          next[item.id] = prev[item.id] ?? initEntry(item);
        }
        return next;
      });
    }
  }, [data]);

  const dirtyCount = Object.values(editState).filter((e) => e.isDirty && !e.isMarkedForDeletion).length;
  const deletionCount = Object.values(editState).filter((e) => e.isMarkedForDeletion).length;
  const pendingCount = pendingItems.length;
  const hasErrors = Object.values(editState).some((e) => e.saveError !== null)
    || pendingItems.some((p) => p.saveError !== null);
  const hasUnsavedChanges = dirtyCount > 0 || deletionCount > 0 || pendingCount > 0 || reorderedParents.size > 0;
  const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [hasUnsavedChanges]);

  function handleNavigateBack() {
    if (hasUnsavedChanges) {
      setShowLeaveConfirm(true);
    } else {
      navigate(`/items/${id}`);
    }
  }

  function updateField(itemId: string, field: string, value: unknown) {
    setEditState((prev) => {
      const entry = prev[itemId];
      if (!entry) return prev;
      const item = data?.items.find((i) => i.id === itemId);

      let newValues: FieldValues;
      if (field === "title") {
        newValues = { ...entry.values, title: value as string };
      } else if (field === "description") {
        newValues = { ...entry.values, description: value as string };
      } else if (field === "status") {
        newValues = { ...entry.values, status: value as string };
      } else {
        newValues = {
          ...entry.values,
          custom_fields: { ...entry.values.custom_fields, [field]: value },
        };
      }

      return {
        ...prev,
        [itemId]: {
          ...entry,
          values: newValues,
          isDirty: item ? checkDirty(item, newValues) : true,
          saveError: null,
        },
      };
    });
  }

  function toggleDeletion(itemId: string) {
    setEditState((prev) => {
      const entry = prev[itemId];
      if (!entry) return prev;
      return {
        ...prev,
        [itemId]: { ...entry, isMarkedForDeletion: !entry.isMarkedForDeletion, saveError: null },
      };
    });
  }

  function revertItem(itemId: string) {
    const item = data?.items.find((i) => i.id === itemId);
    if (!item) return;
    setEditState((prev) => ({
      ...prev,
      [itemId]: initEntry(item),
    }));
  }

  function addItemAt(afterRealIdx: number, itemTypeId: string, itemTypeName: string) {
    if (!data) return;
    const config = getInsertConfig(data.items, afterRealIdx);
    if (!config) return;
    const clientId = `pending-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setPendingItems((prev) => [
      ...prev,
      { clientId, ...config, itemTypeId, itemTypeName, values: { title: "", description: "", status: "draft", custom_fields: {} }, saveError: null },
    ]);
    setAddingAtIndex(null);
  }

  function updatePendingField(clientId: string, field: string, value: unknown) {
    setPendingItems((prev) => prev.map((p) => {
      if (p.clientId !== clientId) return p;
      let newValues: FieldValues;
      if (field === "title") {
        newValues = { ...p.values, title: value as string };
      } else if (field === "description") {
        newValues = { ...p.values, description: value as string };
      } else if (field === "status") {
        newValues = { ...p.values, status: value as string };
      } else {
        newValues = { ...p.values, custom_fields: { ...p.values.custom_fields, [field]: value } };
      }
      return { ...p, values: newValues };
    }));
  }

  function removePendingItem(clientId: string) {
    setPendingItems((prev) => prev.filter((p) => p.clientId !== clientId));
  }

  async function reloadItem(itemId: string) {
    try {
      const fresh = await getItem(itemId);
      setEditState((prev) => ({
        ...prev,
        [itemId]: {
          values: {
            title: fresh.title,
            description: fresh.description,
            status: fresh.status,
            custom_fields: { ...(fresh.custom_fields as Record<string, unknown>) },
          },
          originalVersion: fresh.current_version,
          isDirty: false,
          saveError: null,
          isMarkedForDeletion: false,
        },
      }));
    } catch {
      // user can try again
    }
  }

  function moveItem(itemId: string, direction: "up" | "down") {
    if (!data) return;
    const items = data.items;
    const idx = items.findIndex((i) => i.id === itemId);
    if (idx === -1) return;
    const item = items[idx];

    let parentIdx = -1;
    for (let i = idx - 1; i >= 0; i--) {
      if (items[i].depth === item.depth - 1) { parentIdx = i; break; }
      if (items[i].depth < item.depth - 1) break;
    }
    if (parentIdx === -1) return;
    const parent = items[parentIdx];

    // Find sibling blocks (each sibling + its subtree) in the flat array
    const siblingBlocks: { id: string; start: number; end: number }[] = [];
    for (let i = parentIdx + 1; i < items.length; i++) {
      if (items[i].depth === item.depth) {
        if (siblingBlocks.length > 0) siblingBlocks[siblingBlocks.length - 1].end = i;
        siblingBlocks.push({ id: items[i].id, start: i, end: items.length });
      } else if (items[i].depth <= parent.depth) {
        if (siblingBlocks.length > 0) siblingBlocks[siblingBlocks.length - 1].end = i;
        break;
      }
    }

    const sibIdx = siblingBlocks.findIndex((b) => b.id === itemId);
    if (sibIdx === -1) return;

    let swapIdx: number;
    if (direction === "up" && sibIdx > 0) {
      swapIdx = sibIdx - 1;
    } else if (direction === "down" && sibIdx < siblingBlocks.length - 1) {
      swapIdx = sibIdx + 1;
    } else {
      return;
    }

    // Rearrange the flat array by swapping the two sibling blocks
    const a = siblingBlocks[Math.min(sibIdx, swapIdx)];
    const b = siblingBlocks[Math.max(sibIdx, swapIdx)];
    const newItems = [
      ...items.slice(0, a.start),
      ...items.slice(b.start, b.end),
      ...items.slice(a.end, b.start),
      ...items.slice(a.start, a.end),
      ...items.slice(b.end),
    ];

    queryClient.setQueryData(["editor-data", id], { items: newItems });
    setReorderedParents((prev) => new Set(prev).add(parent.id));
  }

  async function handleSave() {
    if (isSaving) return;
    setIsSaving(true);

    const dirtyEntries = Object.entries(editState).filter(([, e]) => e.isDirty && !e.isMarkedForDeletion);
    const savedIds: string[] = [];

    for (const [itemId, entry] of dirtyEntries) {
      try {
        const live = await getItem(itemId);
        if (live.current_version !== entry.originalVersion) {
          setEditState((prev) => ({
            ...prev,
            [itemId]: { ...prev[itemId], saveError: "conflict" },
          }));
          continue;
        }

        await updateItem(itemId, {
          title: entry.values.title,
          description: entry.values.description,
          status: entry.values.status,
          custom_fields: entry.values.custom_fields,
        });

        savedIds.push(itemId);
        setEditState((prev) => ({
          ...prev,
          [itemId]: {
            ...prev[itemId],
            isDirty: false,
            saveError: null,
            originalVersion: live.current_version + 1,
          },
        }));
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to save";
        setEditState((prev) => ({
          ...prev,
          [itemId]: { ...prev[itemId], saveError: message },
        }));
      }
    }

    const toDelete = Object.entries(editState).filter(([, e]) => e.isMarkedForDeletion);
    const deletedIds: string[] = [];

    for (const [itemId] of toDelete) {
      try {
        await deleteItem(itemId);
        deletedIds.push(itemId);
        setEditState((prev) => {
          const next = { ...prev };
          delete next[itemId];
          return next;
        });
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to delete";
        setEditState((prev) => ({
          ...prev,
          [itemId]: { ...prev[itemId], saveError: message },
        }));
      }
    }

    // ── create pending items ─────────────────────────────────────────────────
    const clientIdToRealId = new Map<string, string>();

    for (const pending of pendingItems) {
      try {
        const created = await createItem({
          title: pending.values.title,
          item_type: pending.itemTypeId,
          description: pending.values.description,
          status: pending.values.status,
          custom_fields: pending.values.custom_fields,
        });
        clientIdToRealId.set(pending.clientId, created.id);
        if (compositionTypeId) {
          await createRelation({
            relation_type: compositionTypeId,
            source: pending.parentId,
            target: created.id,
          });
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to create";
        setPendingItems((prev) =>
          prev.map((p) => p.clientId === pending.clientId ? { ...p, saveError: message } : p)
        );
      }
    }

    // Reorder children for each affected parent
    if (data && clientIdToRealId.size > 0) {
      const affectedParents = new Set(pendingItems.filter((p) => clientIdToRealId.has(p.clientId)).map((p) => p.parentId));
      for (const parentId of affectedParents) {
        const parentIdx = data.items.findIndex((item) => item.id === parentId);
        if (parentIdx === -1) continue;
        const pendingForParent = pendingItems.filter((p) => p.parentId === parentId && clientIdToRealId.has(p.clientId));
        const childOrder = buildChildOrder(data.items, parentIdx, pendingForParent, clientIdToRealId);
        if (childOrder.length > 1) {
          try { await reorderChildren(parentId, childOrder); } catch { /* ignore */ }
        }
      }
    }

    const createdClientIds = new Set(clientIdToRealId.keys());
    setPendingItems((prev) => prev.filter((p) => !createdClientIds.has(p.clientId)));

    // ── persist manual reorders ──────────────────────────────────────────────
    let reordersSaved = false;
    for (const parentId of reorderedParents) {
      const items = data?.items ?? [];
      const parentIdx = items.findIndex((item) => item.id === parentId);
      if (parentIdx === -1) continue;
      const parentDepth = items[parentIdx].depth;
      const childIds: string[] = [];
      for (let i = parentIdx + 1; i < items.length; i++) {
        if (items[i].depth === parentDepth + 1) childIds.push(items[i].id);
        else if (items[i].depth <= parentDepth) break;
      }
      if (childIds.length > 0) {
        try { await reorderChildren(parentId, childIds); reordersSaved = true; } catch { /* ignore */ }
      }
    }
    setReorderedParents(new Set());

    // ── invalidate queries ───────────────────────────────────────────────────
    for (const itemId of savedIds) {
      queryClient.invalidateQueries({ queryKey: ["item", itemId] });
      queryClient.invalidateQueries({ queryKey: ["versions", itemId] });
    }
    if (savedIds.length > 0 || deletedIds.length > 0 || createdClientIds.size > 0 || reordersSaved) {
      queryClient.invalidateQueries({ queryKey: ["tree"] });
      queryClient.invalidateQueries({ queryKey: ["navigation"] });
      queryClient.invalidateQueries({ queryKey: ["editor-data", id] });
    }

    setIsSaving(false);
    if (
      savedIds.length === dirtyEntries.length &&
      deletedIds.length === toDelete.length &&
      createdClientIds.size === pendingItems.length
    ) {
      setSavedAt(Date.now());
      setTimeout(() => setSavedAt(null), 2000);
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-red-600">
        Failed to load editor data.
      </div>
    );
  }

  const showCheck = savedAt !== null;

  return (
    <div className="flex h-full flex-col bg-gray-50">
      {/* Top bar */}
      <div className="flex items-center gap-3 border-b border-gray-200 bg-white px-4 py-3 shadow-sm">
        <button
          onClick={handleNavigateBack}
          className="rounded p-1 text-gray-500 hover:bg-gray-100"
          title="Back to item"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
          Document Editor
        </span>
        <span className="h-4 w-px bg-gray-200" />
        <span className="flex-1 truncate text-sm font-medium text-gray-700">
          {data.items[0]?.title}
        </span>
        {hasErrors && (
          <span className="flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">
            <AlertTriangle className="h-3 w-3" />
            Save errors
          </span>
        )}
        {dirtyCount > 0 && !hasErrors && (
          <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">
            {dirtyCount} {dirtyCount === 1 ? "item" : "items"} modified
          </span>
        )}
        {deletionCount > 0 && !hasErrors && (
          <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">
            {deletionCount} {deletionCount === 1 ? "item" : "items"} to delete
          </span>
        )}
        {pendingCount > 0 && !hasErrors && (
          <span className="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700">
            {pendingCount} new {pendingCount === 1 ? "item" : "items"}
          </span>
        )}
        <button
          onClick={handleSave}
          disabled={(dirtyCount === 0 && deletionCount === 0 && pendingCount === 0 && reorderedParents.size === 0) || isSaving}
          className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
        >
          {isSaving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : showCheck ? (
            <Check className="h-4 w-4" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          {showCheck ? "Saved" : "Save"}
        </button>
      </div>

      {/* Document body */}
      <div className="flex-1 overflow-y-auto px-6 py-8" onClick={() => setAddingAtIndex(null)}>
        <div className="mx-auto max-w-3xl space-y-2">
          {data.items.map((item, realIdx) => {
            if (skippedItemIds.has(item.id)) return null;
            const hasChildren = realIdx + 1 < data.items.length && data.items[realIdx + 1].depth > item.depth;
            const isCollapsed = collapsedItems.has(item.id);
            const entry = editState[item.id];
            if (!entry) return null;
            const borderColor = DEPTH_COLORS[(item.depth - 1) % DEPTH_COLORS.length];
            const insertConfig = getInsertConfig(data.items, realIdx);
            const firstChildPending = pendingItems.filter((p) => p.insertAfterId === null && p.parentId === item.id);
            const siblingAfterPending = pendingItems.filter((p) => p.insertAfterId === item.id);

            // Determine if parent is visible and this item's sibling position
            let canMoveUp = false;
            let canMoveDown = false;
            {
              const items = data.items;
              let parentIdx = -1;
              for (let i = realIdx - 1; i >= 0; i--) {
                if (items[i].depth === item.depth - 1) { parentIdx = i; break; }
                if (items[i].depth < item.depth - 1) break;
              }
              if (parentIdx !== -1) {
                const siblings: string[] = [];
                const parent = items[parentIdx];
                for (let i = parentIdx + 1; i < items.length; i++) {
                  if (items[i].depth === item.depth) siblings.push(items[i].id);
                  else if (items[i].depth <= parent.depth) break;
                }
                const sibIdx = siblings.indexOf(item.id);
                canMoveUp = sibIdx > 0;
                canMoveDown = sibIdx < siblings.length - 1;
              }
            }

            return (
              <Fragment key={item.id}>
                <ItemSection
                  item={item}
                  entry={entry}
                  borderColor={borderColor}
                  onFieldChange={(field, value) => updateField(item.id, field, value)}
                  onRevert={() => revertItem(item.id)}
                  onToggleDeletion={() => toggleDeletion(item.id)}
                  onReload={() => reloadItem(item.id)}
                  hasChildren={hasChildren}
                  isCollapsed={isCollapsed}
                  onToggleCollapse={() => toggleCollapse(item.id)}
                  canMoveUp={canMoveUp}
                  canMoveDown={canMoveDown}
                  onMoveUp={() => moveItem(item.id, "up")}
                  onMoveDown={() => moveItem(item.id, "down")}
                />
                {!isCollapsed && firstChildPending.map((p) => (
                  <PendingItemSection
                    key={p.clientId}
                    item={p}
                    itemType={itemTypes.find((t) => t.id === p.itemTypeId)}
                    onFieldChange={(field, value) => updatePendingField(p.clientId, field, value)}
                    onRemove={() => removePendingItem(p.clientId)}
                  />
                ))}
                {siblingAfterPending.map((p) => (
                  <PendingItemSection
                    key={p.clientId}
                    item={p}
                    itemType={itemTypes.find((t) => t.id === p.itemTypeId)}
                    onFieldChange={(field, value) => updatePendingField(p.clientId, field, value)}
                    onRemove={() => removePendingItem(p.clientId)}
                  />
                ))}
                {insertConfig && !isCollapsed && (
                  addingAtIndex === realIdx ? (
                    <TypePicker
                      itemTypes={itemTypes}
                      onSelect={(typeId, typeName) => addItemAt(realIdx, typeId, typeName)}
                      onCancel={() => setAddingAtIndex(null)}
                    />
                  ) : (
                    <AddItemButton onClick={(e) => { e.stopPropagation(); setAddingAtIndex(realIdx); }} />
                  )
                )}
              </Fragment>
            );
          })}
        </div>
      </div>

      {/* Leave confirmation dialog */}
      {showLeaveConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
            <h2 className="mb-2 text-base font-semibold text-gray-900">Unsaved changes</h2>
            <p className="mb-5 text-sm text-gray-600">
              You have unsaved changes that will be lost if you leave. Do you want to continue?
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowLeaveConfirm(false)}
                className="rounded-md px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
              >
                Stay
              </button>
              <button
                onClick={() => navigate(`/items/${id}`)}
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
              >
                Leave
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── item section ─────────────────────────────────────────────────────────────

function ItemSection({
  item,
  entry,
  borderColor,
  onFieldChange,
  onRevert,
  onToggleDeletion,
  onReload,
  hasChildren,
  isCollapsed,
  onToggleCollapse,
  canMoveUp,
  canMoveDown,
  onMoveUp,
  onMoveDown,
}: {
  item: EditorItem;
  entry: EditEntry;
  borderColor: string;
  onFieldChange: (field: string, value: unknown) => void;
  onRevert: () => void;
  onToggleDeletion: () => void;
  onReload: () => void;
  hasChildren: boolean;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  const isConflict = entry.saveError === "conflict";
  const hasError = entry.saveError !== null;
  const isDeleting = entry.isMarkedForDeletion;

  const template = item.template ?? item.default_template;
  const processed = preprocessTemplate(template, item);

  // Keep a ref so renderField is always current without changing identity
  const renderFieldRef = useRef<FieldRenderer>(() => null);
  renderFieldRef.current = (name: string) => (
    <FieldWidget
      key={name}
      fieldName={name}
      item={item}
      values={entry.values}
      onChange={onFieldChange}
    />
  );

  const stableRenderField = useCallback((name: string) => renderFieldRef.current(name), []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const components = useMemo(() => makeComponents(stableRenderField), []);

  return (
    <div
      className={`rounded-md bg-white shadow-sm ${
        isDeleting ? "border-l-4 border-red-400 opacity-60" :
        hasError ? "border-l-4 border-red-400" : `border-l-4 ${borderColor}`
      }`}
    >
      {/* Minimal item header */}
      <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-1.5">
        {hasChildren && (
          <button
            onClick={onToggleCollapse}
            title={isCollapsed ? "Expand" : "Collapse"}
            className="-ml-1 flex-shrink-0 text-gray-400 hover:text-gray-600"
          >
            {isCollapsed
              ? <ChevronRight className="h-3.5 w-3.5" />
              : <ChevronDown className="h-3.5 w-3.5" />
            }
          </button>
        )}
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500">
          {item.item_type_name}
        </span>
        <span className="font-mono text-[10px] text-gray-300">{item.id.slice(0, 8)}</span>
        {item.depth > 1 && (
          <span className="text-[10px] text-gray-300">depth {item.depth}</span>
        )}
        {isDeleting && (
          <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-medium text-red-600 line-through">
            {item.title}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {entry.isDirty && !hasError && !isDeleting && (
            <span className="flex items-center gap-1">
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-600">
                modified
              </span>
              <button
                onClick={onRevert}
                title="Revert changes"
                className="rounded p-0.5 text-amber-500 hover:bg-amber-50 hover:text-amber-700"
              >
                <RotateCcw className="h-3 w-3" />
              </button>
            </span>
          )}
          {isConflict && (
            <span className="flex items-center gap-1 text-[11px] font-medium text-red-600">
              <AlertTriangle className="h-3 w-3" />
              Updated while editing —{" "}
              <button
                onClick={onReload}
                className="inline-flex items-center gap-0.5 underline hover:text-red-800"
              >
                <RefreshCw className="h-3 w-3" />
                Reload
              </button>
            </span>
          )}
          {hasError && !isConflict && (
            <span className="text-[11px] text-red-600">{entry.saveError}</span>
          )}
          {(canMoveUp || canMoveDown) && (
            <>
              <button
                onClick={onMoveUp}
                disabled={!canMoveUp}
                title="Move up"
                className="rounded p-0.5 text-gray-300 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-gray-300"
              >
                <ArrowUp className="h-3 w-3" />
              </button>
              <button
                onClick={onMoveDown}
                disabled={!canMoveDown}
                title="Move down"
                className="rounded p-0.5 text-gray-300 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-gray-300"
              >
                <ArrowDown className="h-3 w-3" />
              </button>
            </>
          )}
          <button
            onClick={onToggleDeletion}
            title={isDeleting ? "Undo deletion" : "Mark for deletion"}
            className={`rounded p-0.5 ${
              isDeleting
                ? "text-red-500 hover:bg-red-50 hover:text-red-700"
                : "text-gray-300 hover:bg-gray-100 hover:text-red-500"
            }`}
          >
            {isDeleting ? <Undo2 className="h-3 w-3" /> : <Trash2 className="h-3 w-3" />}
          </button>
        </div>
      </div>

      {/* Rendered markdown document — hidden when marked for deletion */}
      {!isDeleting && (
        <article className="prose prose-sm max-w-none px-6 py-5 prose-headings:text-gray-900 prose-p:text-gray-700 prose-strong:text-gray-900 prose-ul:text-gray-700 prose-li:text-gray-700 prose-hr:border-gray-200 prose-em:text-gray-500 prose-table:w-full prose-th:border prose-th:border-gray-300 prose-th:bg-gray-50 prose-th:px-3 prose-th:py-1.5 prose-th:text-left prose-th:font-semibold prose-td:border prose-td:border-gray-200 prose-td:px-3 prose-td:py-1.5">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={components}
          >
            {processed}
          </ReactMarkdown>
        </article>
      )}
    </div>
  );
}

// ── field widgets ─────────────────────────────────────────────────────────────

function FieldWidget({
  fieldName,
  item,
  values,
  onChange,
}: {
  fieldName: string;
  item: EditorItem;
  values: FieldValues;
  onChange: (field: string, value: unknown) => void;
}) {
  if (fieldName === "title") {
    return (
      <InlineInput
        value={values.title}
        onChange={(v) => onChange("title", v)}
      />
    );
  }

  if (fieldName === "description") {
    return (
      <GrowingTextarea
        value={values.description}
        onChange={(v) => onChange("description", v)}
        placeholder="(no description)"
      />
    );
  }

  if (fieldName === "status") {
    return (
      <InlineSelect
        value={values.status}
        onChange={(v) => onChange("status", v)}
        options={STATUS_OPTIONS}
      />
    );
  }

  const fieldDef = item.custom_field_definitions.find((f) => f.slug === fieldName);
  if (!fieldDef) {
    return <span className="italic text-gray-300">{`{{${fieldName}}}`}</span>;
  }

  if (fieldDef.field_kind === "table") {
    return (
      <TableFieldWidget
        itemId={item.id}
        fieldSlug={fieldDef.slug}
        label={fieldDef.name}
      />
    );
  }

  return (
    <CustomFieldWidget
      fieldDef={fieldDef}
      value={values.custom_fields[fieldName]}
      onChange={(v) => onChange(fieldName, v)}
    />
  );
}

function CustomFieldWidget({
  fieldDef,
  value,
  onChange,
}: {
  fieldDef: EditorFieldDefinition;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  if (fieldDef.field_kind === "boolean") {
    return (
      <input
        type="checkbox"
        checked={Boolean(value)}
        onChange={(e) => onChange(e.target.checked)}
        className="align-middle"
      />
    );
  }

  if (fieldDef.field_kind === "choice") {
    const choices = (fieldDef.options?.choices as string[]) || [];
    return (
      <InlineSelect
        value={String(value ?? "")}
        onChange={onChange}
        options={[{ value: "", label: "—" }, ...choices.map((c) => ({ value: c, label: c }))]}
      />
    );
  }

  if (fieldDef.field_kind === "date") {
    return (
      <input
        type="date"
        value={String(value ?? "")}
        onChange={(e) => onChange(e.target.value)}
        className="border-0 border-b border-blue-300 bg-transparent text-sm outline-none focus:border-blue-500"
        style={{ padding: 0 }}
      />
    );
  }

  if (fieldDef.field_kind === "integer" || fieldDef.field_kind === "decimal") {
    return (
      <InlineInput
        value={String(value ?? "")}
        onChange={onChange}
        inputType="number"
      />
    );
  }

  if (fieldDef.field_kind === "mermaid") {
    const src = String(value ?? "");
    return (
      <div className="w-full">
        <GrowingTextarea
          value={src}
          onChange={onChange}
          placeholder={`graph TD\n    A --> B`}
        />
        {src.trim() && (
          <div className="mt-2">
            <MermaidDiagram source={src} />
          </div>
        )}
      </div>
    );
  }

  // text
  return (
    <GrowingTextarea
      value={String(value ?? "")}
      onChange={onChange}
      placeholder={`(${fieldDef.name})`}
    />
  );
}

// ── inline edit widgets ───────────────────────────────────────────────────────

/**
 * Auto-sizing inline input using the mirror-span technique.
 * The hidden span dictates the width; the input overlays it.
 */
function InlineInput({
  value,
  onChange,
  inputType = "text",
}: {
  value: string;
  onChange: (v: string) => void;
  inputType?: string;
}) {
  return (
    <span className="relative inline-block min-w-[2ch] align-baseline">
      <span className="invisible inline-block whitespace-pre" aria-hidden style={{ padding: 0 }}>
        {value || "\u00a0"}
      </span>
      <input
        type={inputType}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        spellCheck
        className="absolute inset-0 w-full border-0 border-b border-blue-300 bg-transparent outline-none focus:border-blue-500"
        style={{ padding: 0, font: "inherit", color: "inherit" }}
      />
    </span>
  );
}

/** Textarea that grows with its content, rendered inline. */
function GrowingTextarea({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: unknown) => void;
  placeholder?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  const resize = useCallback(() => {
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = `${ref.current.scrollHeight}px`;
    }
  }, []);

  useEffect(() => {
    resize();
  }, [value, resize]);

  return (
    <textarea
      ref={ref}
      value={value}
      onChange={(e) => {
        onChange(e.target.value);
        resize();
      }}
      placeholder={placeholder}
      rows={1}
      spellCheck
      className="block w-full resize-none border-0 border-b border-blue-300 bg-transparent outline-none placeholder:text-gray-300 focus:border-blue-500"
      style={{ padding: 0, overflow: "hidden", font: "inherit", color: "inherit" }}
    />
  );
}

function InlineSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="border-0 border-b border-blue-300 bg-transparent outline-none focus:border-blue-500"
      style={{ padding: 0, font: "inherit", color: "inherit" }}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}

// ── add-item controls ─────────────────────────────────────────────────────────

function AddItemButton({ onClick }: { onClick: (e: React.MouseEvent) => void }) {
  return (
    <div className="group flex items-center gap-2 py-1">
      <div className="h-px flex-1 bg-gray-200 transition-colors group-hover:bg-blue-300" />
      <button
        onClick={onClick}
        className="flex items-center gap-1 rounded-full border border-dashed border-gray-300 bg-white px-2.5 py-0.5 text-[11px] font-medium text-gray-400 transition-colors hover:border-blue-400 hover:text-blue-500"
      >
        <Plus className="h-3 w-3" />
        Add item
      </button>
      <div className="h-px flex-1 bg-gray-200 transition-colors group-hover:bg-blue-300" />
    </div>
  );
}

function TypePicker({
  itemTypes,
  onSelect,
  onCancel,
}: {
  itemTypes: ItemType[];
  onSelect: (typeId: string, typeName: string) => void;
  onCancel: () => void;
}) {
  return (
    <div
      className="flex flex-wrap items-center gap-1.5 rounded-md border border-blue-200 bg-blue-50 px-3 py-2"
      onClick={(e) => e.stopPropagation()}
    >
      <span className="text-[11px] font-medium text-blue-600">Select type:</span>
      {itemTypes.map((t) => (
        <button
          key={t.id}
          onClick={() => onSelect(t.id, t.name)}
          className="rounded-full border border-blue-200 bg-white px-2.5 py-0.5 text-[11px] font-medium text-gray-600 hover:border-blue-400 hover:text-blue-700"
        >
          {t.name}
        </button>
      ))}
      <button
        onClick={onCancel}
        className="ml-auto rounded p-0.5 text-blue-400 hover:text-blue-600"
        title="Cancel"
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  );
}

function PendingItemSection({
  item,
  itemType,
  onFieldChange,
  onRemove,
}: {
  item: PendingItem;
  itemType: ItemType | undefined;
  onFieldChange: (field: string, value: unknown) => void;
  onRemove: () => void;
}) {
  const { data: templateData } = useQuery({
    queryKey: ["document-template", item.itemTypeId],
    queryFn: () => getDocumentTemplate(item.itemTypeId),
    staleTime: 5 * 60 * 1000,
  });

  const fieldDefinitions: EditorFieldDefinition[] = (itemType?.custom_fields ?? []).map((cf) => ({
    slug: cf.slug,
    name: cf.name,
    field_kind: cf.field_kind,
    options: cf.options,
  }));

  const fakeItem: EditorItem = {
    id: item.clientId,
    depth: item.depth,
    title: item.values.title,
    description: item.values.description,
    status: item.values.status,
    item_type_id: item.itemTypeId,
    item_type_name: item.itemTypeName,
    current_version: 1,
    created_by: "",
    created_at: "",
    updated_at: "",
    custom_fields: item.values.custom_fields,
    custom_field_definitions: fieldDefinitions,
    template: templateData?.template ?? null,
    default_template: templateData?.default_template ?? `${"#".repeat(Math.min(item.depth, 6))} {{title}}\n\n{{description}}`,
  };

  const template = fakeItem.template ?? fakeItem.default_template;
  const processed = preprocessTemplate(template, fakeItem);

  const renderFieldRef = useRef<FieldRenderer>(() => null);
  renderFieldRef.current = (name: string) => (
    <FieldWidget
      key={name}
      fieldName={name}
      item={fakeItem}
      values={item.values}
      onChange={onFieldChange}
    />
  );
  const stableRenderField = useCallback((name: string) => renderFieldRef.current(name), []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const components = useMemo(() => makeComponents(stableRenderField), []);

  const borderColor = DEPTH_COLORS[(item.depth - 1) % DEPTH_COLORS.length];

  return (
    <div className={`rounded-md border border-dashed border-green-300 bg-white shadow-sm border-l-4 ${borderColor}`}>
      <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-1.5">
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500">
          {item.itemTypeName}
        </span>
        <span className="rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-medium text-green-600">
          new
        </span>
        {item.saveError && (
          <span className="text-[11px] text-red-600">{item.saveError}</span>
        )}
        <button
          onClick={onRemove}
          title="Remove"
          className="ml-auto rounded p-0.5 text-gray-300 hover:bg-gray-100 hover:text-red-500"
        >
          <Trash2 className="h-3 w-3" />
        </button>
      </div>
      <article className="prose prose-sm max-w-none px-6 py-5 prose-headings:text-gray-900 prose-p:text-gray-700 prose-strong:text-gray-900 prose-ul:text-gray-700 prose-li:text-gray-700 prose-hr:border-gray-200 prose-em:text-gray-500 prose-table:w-full prose-th:border prose-th:border-gray-300 prose-th:bg-gray-50 prose-th:px-3 prose-th:py-1.5 prose-th:text-left prose-th:font-semibold prose-td:border prose-td:border-gray-200 prose-td:px-3 prose-td:py-1.5">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
          {processed}
        </ReactMarkdown>
      </article>
    </div>
  );
}
