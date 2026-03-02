import { useEffect, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  ArrowLeft,
  Pencil,
  Trash2,
  Link as LinkIcon,
  Copy,
  Check,
  Plus,
  History,
  FileText,
  Loader2,
  AlertTriangle,
  CheckCircle,
} from "lucide-react";
import { getItem, getItems, deleteItem, getItemTypes, getItemVersions } from "../api/items";
import { getNavigation, getRelationTypes, createRelation, confirmRelation } from "../api/relations";
import { generateDocument } from "../api/mailbox";
import type { NavigationRef, RelationType, ItemVersion } from "../types";
import { useState } from "react";

export default function ItemNavigator() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: item, isLoading } = useQuery({
    queryKey: ["item", id],
    queryFn: () => getItem(id!),
    enabled: !!id,
  });

  const { data: nav } = useQuery({
    queryKey: ["navigation", id],
    queryFn: () => getNavigation(id!),
    enabled: !!id,
  });

  const { data: itemTypes } = useQuery({
    queryKey: ["itemTypes"],
    queryFn: getItemTypes,
  });

  const { data: relationTypes } = useQuery({
    queryKey: ["relationTypes"],
    queryFn: getRelationTypes,
  });

  const { data: versions } = useQuery({
    queryKey: ["versions", id],
    queryFn: () => getItemVersions(id!),
    enabled: !!id,
  });

  const [showAddRelation, setShowAddRelation] = useState(false);
  const [copied, setCopied] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  function copyLink() {
    navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const generateMutation = useMutation({
    mutationFn: () => generateDocument(id!),
    onSuccess: () => {
      setGenerated(true);
      setTimeout(() => setGenerated(false), 2000);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteItem(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["items"] });
      navigate("/items");
    },
  });

  // Keyboard navigation
  const handleKeyNav = useCallback(
    (e: KeyboardEvent) => {
      if (!nav) return;
      // Don't intercept if user is typing in an input
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      )
        return;

      switch (e.key) {
        case "ArrowLeft":
          if (nav.left.length > 0) {
            e.preventDefault();
            navigate(`/items/${nav.left[0].id}`);
          }
          break;
        case "ArrowRight":
          if (nav.right.length > 0) {
            e.preventDefault();
            navigate(`/items/${nav.right[0].id}`);
          }
          break;
      }
    },
    [nav, navigate]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyNav);
    return () => window.removeEventListener("keydown", handleKeyNav);
  }, [handleKeyNav]);

  if (isLoading || !item) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  const itemType = itemTypes?.find((t) => t.id === item.item_type);

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <div className="flex items-center gap-3 border-b border-gray-200 bg-white px-4 py-3">
        <button
          onClick={() => navigate("/items")}
          className="rounded p-1 text-gray-500 hover:bg-gray-100"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <span className="inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
          {item.item_type_name}
        </span>
        <span className="inline-flex rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
          v{item.current_version}
        </span>
        <h1 className="flex-1 truncate text-lg font-semibold text-gray-900">
          {item.title}
        </h1>
        <div className="flex items-center gap-1">
          <button
            onClick={copyLink}
            className="rounded p-1.5 text-gray-500 hover:bg-gray-100"
            title="Copy link"
          >
            {copied ? (
              <Check className="h-4 w-4 text-green-500" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
          </button>
          <button
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
            className="rounded p-1.5 text-gray-500 hover:bg-gray-100"
            title="Generate Document"
          >
            {generateMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : generated ? (
              <Check className="h-4 w-4 text-green-500" />
            ) : (
              <FileText className="h-4 w-4" />
            )}
          </button>
          <Link
            to={`/items/${id}/edit`}
            className="rounded p-1.5 text-gray-500 hover:bg-gray-100"
            title="Edit"
          >
            <Pencil className="h-4 w-4" />
          </Link>
          <Link
            to={`/items/new?type=${encodeURIComponent(item.item_type_slug)}${nav?.parent ? `&parent=${nav.parent.id}` : ""}`}
            className="rounded p-1.5 text-gray-500 hover:bg-gray-100"
            title={nav?.parent ? `Add sibling ${item.item_type_name}` : `New ${item.item_type_name}`}
          >
            <Plus className="h-4 w-4" />
          </Link>
          <button
            onClick={() => setShowHistory(!showHistory)}
            className={`rounded p-1.5 hover:bg-gray-100 ${showHistory ? "text-blue-600 bg-blue-50" : "text-gray-500"}`}
            title="Version History"
          >
            <History className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowAddRelation(true)}
            className="rounded p-1.5 text-gray-500 hover:bg-gray-100"
            title="Add Relation"
          >
            <LinkIcon className="h-4 w-4" />
          </button>
          <button
            onClick={() => {
              if (confirm("Delete this item?")) deleteMutation.mutate();
            }}
            className="rounded p-1.5 text-red-500 hover:bg-red-50"
            title="Delete"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Navigation grid */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel - incoming relations */}
        <NavPanel
          title="Incoming"
          icon={<ChevronLeft className="h-4 w-4" />}
          items={nav?.left || []}
          onNavigate={(ref) => navigate(`/items/${ref.id}`)}
          onConfirm={(ref) => {
            if (ref.relation_id) {
              confirmRelation(ref.relation_id).then(() => {
                queryClient.invalidateQueries({ queryKey: ["navigation", id] });
                queryClient.invalidateQueries({ queryKey: ["tree"] });
              });
            }
          }}
          side="left"
        />

        {/* Center content */}
        <div className="flex flex-1 flex-col overflow-y-auto">
          {/* Item detail */}
          <div className="flex-1 overflow-y-auto p-6">
            <div className="space-y-6">
              {/* Status */}
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium text-gray-500">
                  Status:
                </span>
                <span className="inline-flex rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700">
                  {item.status.replace("_", " ")}
                </span>
              </div>

              {/* Description */}
              {item.description && (
                <div>
                  <h3 className="text-sm font-medium text-gray-500">
                    Description
                  </h3>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-gray-800">
                    {item.description}
                  </p>
                </div>
              )}

              {/* Custom fields */}
              {item.custom_fields &&
                Object.keys(item.custom_fields).length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-500">
                      Attributes
                    </h3>
                    <dl className="mt-2 grid grid-cols-2 gap-3">
                      {Object.entries(item.custom_fields).map(([key, val]) => {
                        const fieldDef = itemType?.custom_fields.find(
                          (f) => f.slug === key
                        );
                        return (
                          <div
                            key={key}
                            className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2"
                          >
                            <dt className="text-xs font-medium text-gray-500">
                              {fieldDef?.name || key}
                            </dt>
                            <dd className="mt-0.5 text-sm text-gray-800">
                              {String(val ?? "—")}
                            </dd>
                          </div>
                        );
                      })}
                    </dl>
                  </div>
                )}

              {/* Metadata */}
              <div className="border-t border-gray-100 pt-4 text-xs text-gray-400">
                Created by {item.created_by_username} on{" "}
                {new Date(item.created_at).toLocaleString()} · Last updated{" "}
                {new Date(item.updated_at).toLocaleString()}
              </div>

              {/* Version History */}
              {showHistory && (
                <VersionHistory versions={versions || []} />
              )}
            </div>
          </div>

        </div>

        {/* Right panel - outgoing relations */}
        <NavPanel
          title="Outgoing"
          icon={<ChevronRight className="h-4 w-4" />}
          items={nav?.right || []}
          onNavigate={(ref) => navigate(`/items/${ref.id}`)}
          onConfirm={(ref) => {
            if (ref.relation_id) {
              confirmRelation(ref.relation_id).then(() => {
                queryClient.invalidateQueries({ queryKey: ["navigation", id] });
                queryClient.invalidateQueries({ queryKey: ["tree"] });
              });
            }
          }}
          side="right"
        />
      </div>

      {/* Add relation dialog */}
      {showAddRelation && (
        <AddRelationDialog
          sourceId={id!}
          sourceItemType={item.item_type}
          relationTypes={relationTypes || []}
          onClose={() => setShowAddRelation(false)}
          onCreated={() => {
            queryClient.invalidateQueries({ queryKey: ["navigation", id] });
            setShowAddRelation(false);
          }}
        />
      )}
    </div>
  );
}

function NavPanel({
  title,
  icon,
  items,
  onNavigate,
  onConfirm,
  side,
}: {
  title: string;
  icon: React.ReactNode;
  items: NavigationRef[];
  onNavigate: (ref: NavigationRef) => void;
  onConfirm: (ref: NavigationRef) => void;
  side: "left" | "right";
}) {
  const suspectCount = items.filter((r) => r.is_suspect).length;
  return (
    <div
      className={`w-56 flex-shrink-0 overflow-y-auto border-gray-200 bg-white ${
        side === "left" ? "border-r" : "border-l"
      }`}
    >
      <div className="flex items-center gap-1.5 border-b border-gray-100 px-3 py-2">
        {icon}
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          {title}
        </span>
        {suspectCount > 0 && (
          <span className="ml-1 inline-flex items-center rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
            {suspectCount} suspect
          </span>
        )}
        <span className="ml-auto text-xs text-gray-400">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className="px-3 py-4 text-xs text-gray-400">No relations</p>
      ) : (
        <div className="divide-y divide-gray-50">
          {items.map((ref) => (
            <div
              key={ref.relation_id || ref.id}
              className={`group px-3 py-2 ${ref.is_suspect ? "bg-amber-50" : ""}`}
            >
              <button
                onClick={() => onNavigate(ref)}
                className="block w-full text-left hover:bg-gray-50"
              >
                <p className="truncate text-sm font-medium text-gray-800">
                  {ref.is_suspect && (
                    <AlertTriangle className="mr-1 inline h-3.5 w-3.5 text-amber-500" />
                  )}
                  {ref.title}
                </p>
                <p className="text-xs text-gray-400">
                  {ref.relation_label} · {ref.item_type_slug}
                </p>
                {ref.is_suspect && (
                  <p className="mt-0.5 text-[10px] text-amber-600">
                    {ref.other_changed && ref.self_changed
                      ? `Both sides changed (linked: v${ref.pinned_version}, now: v${ref.current_version}; this item: v${ref.self_pinned_version} → v${ref.self_current_version})`
                      : ref.other_changed
                        ? `Linked item changed (v${ref.pinned_version} → v${ref.current_version})`
                        : `This item changed since link confirmed (v${ref.self_pinned_version} → v${ref.self_current_version})`}
                  </p>
                )}
              </button>
              {ref.is_suspect && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onConfirm(ref);
                  }}
                  className="mt-1 inline-flex items-center gap-1 rounded bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700 hover:bg-amber-200"
                  title="Confirm this link is still valid"
                >
                  <CheckCircle className="h-3 w-3" />
                  Confirm
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AddRelationDialog({
  sourceId,
  sourceItemType,
  relationTypes,
  onClose,
  onCreated,
}: {
  sourceId: string;
  sourceItemType: string;
  relationTypes: RelationType[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [relationTypeId, setRelationTypeId] = useState("");
  const [targetSearch, setTargetSearch] = useState("");
  const [selectedTargetId, setSelectedTargetId] = useState("");
  const [direction, setDirection] = useState<"outgoing" | "incoming">(
    "outgoing"
  );
  const queryClient = useQueryClient();

  // Filter relation types based on direction and current item's type
  const filteredRelationTypes = relationTypes.filter((rt) => {
    if (direction === "outgoing") {
      // Current item is source: source_item_type must match or be null (any)
      return !rt.source_item_type || rt.source_item_type === sourceItemType;
    } else {
      // Current item is target: target_item_type must match or be null (any)
      return !rt.target_item_type || rt.target_item_type === sourceItemType;
    }
  });

  // Determine the required item type for the other end
  const selectedRelationType = relationTypes.find(
    (rt) => rt.id === relationTypeId
  );
  const requiredTargetTypeId =
    direction === "outgoing"
      ? selectedRelationType?.target_item_type
      : selectedRelationType?.source_item_type;

  const { data: searchResults } = useQuery({
    queryKey: ["items", "search", targetSearch, requiredTargetTypeId],
    queryFn: async () => {
      const params: Record<string, string> = { search: targetSearch };
      if (requiredTargetTypeId) {
        const types = await getItemTypes();
        const targetType = types.find((t) => t.id === requiredTargetTypeId);
        if (targetType) {
          params.item_type__slug = targetType.slug;
        }
      }
      return getItems(params);
    },
    enabled: targetSearch.length >= 2,
  });

  const mutation = useMutation({
    mutationFn: () =>
      createRelation({
        relation_type: relationTypeId,
        source: direction === "outgoing" ? sourceId : selectedTargetId,
        target: direction === "outgoing" ? selectedTargetId : sourceId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["navigation"] });
      queryClient.invalidateQueries({ queryKey: ["relations"] });
      queryClient.invalidateQueries({ queryKey: ["tree"] });
      onCreated();
    },
  });

  // Reset relation type when direction changes (filtered list may differ)
  const handleDirectionChange = (newDirection: "outgoing" | "incoming") => {
    setDirection(newDirection);
    setRelationTypeId("");
    setTargetSearch("");
    setSelectedTargetId("");
  };

  // Reset target when relation type changes (target type constraint may differ)
  const handleRelationTypeChange = (newId: string) => {
    setRelationTypeId(newId);
    setTargetSearch("");
    setSelectedTargetId("");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-gray-900">Add Relation</h2>

        <div className="mt-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Direction
            </label>
            <select
              value={direction}
              onChange={(e) =>
                handleDirectionChange(
                  e.target.value as "outgoing" | "incoming"
                )
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="outgoing">
                This item → Target (outgoing)
              </option>
              <option value="incoming">
                Target → This item (incoming)
              </option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Relation Type
            </label>
            <select
              value={relationTypeId}
              onChange={(e) => handleRelationTypeChange(e.target.value)}
              required
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="">Select...</option>
              {filteredRelationTypes.map((rt) => (
                <option key={rt.id} value={rt.id}>
                  {direction === "outgoing"
                    ? rt.forward_label
                    : rt.reverse_label}{" "}
                  ({rt.name})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Target Item
              {selectedRelationType &&
                (direction === "outgoing"
                  ? selectedRelationType.target_item_type_name
                  : selectedRelationType.source_item_type_name) && (
                  <span className="ml-1 font-normal text-gray-400">
                    (
                    {direction === "outgoing"
                      ? selectedRelationType.target_item_type_name
                      : selectedRelationType.source_item_type_name}
                    )
                  </span>
                )}
            </label>
            <input
              type="text"
              placeholder="Search items..."
              value={targetSearch}
              onChange={(e) => {
                setTargetSearch(e.target.value);
                setSelectedTargetId("");
              }}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
            {searchResults && !selectedTargetId && (
              <div className="mt-1 max-h-40 overflow-y-auto rounded-md border border-gray-200 bg-white">
                {searchResults.results
                  .filter((i) => i.id !== sourceId)
                  .map((i) => (
                    <button
                      key={i.id}
                      onClick={() => {
                        setSelectedTargetId(i.id);
                        setTargetSearch(i.title);
                      }}
                      className="block w-full px-3 py-2 text-left text-sm hover:bg-gray-50"
                    >
                      <span className="font-medium">{i.title}</span>
                      <span className="ml-2 text-xs text-gray-400">
                        {i.item_type_name}
                      </span>
                    </button>
                  ))}
              </div>
            )}
          </div>

        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!relationTypeId || !selectedTargetId || mutation.isPending}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? "Creating..." : "Create Relation"}
          </button>
        </div>
      </div>
    </div>
  );
}

function VersionHistory({ versions }: { versions: ItemVersion[] }) {
  if (versions.length === 0) {
    return (
      <div className="border-t border-gray-100 pt-4">
        <h3 className="text-sm font-medium text-gray-500">Version History</h3>
        <p className="mt-2 text-xs text-gray-400">
          No previous versions. History starts from the first edit.
        </p>
      </div>
    );
  }

  return (
    <div className="border-t border-gray-100 pt-4">
      <h3 className="text-sm font-medium text-gray-500">Version History</h3>
      <div className="mt-2 space-y-2">
        {versions.map((v) => (
          <div
            key={v.id}
            className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2"
          >
            <div className="flex items-center gap-2">
              <span className="inline-flex rounded bg-blue-100 px-1.5 py-0.5 text-xs font-semibold text-blue-700">
                v{v.version_number}
              </span>
              <span className="truncate text-sm font-medium text-gray-800">
                {v.title}
              </span>
              <span className="ml-auto flex-shrink-0 text-xs text-gray-400">
                {new Date(v.created_at).toLocaleDateString()}
              </span>
            </div>
            {v.change_summary && (
              <p className="mt-1 text-xs text-gray-600">{v.change_summary}</p>
            )}
            <p className="mt-0.5 text-xs text-gray-400">
              by {v.created_by_username} · {v.status}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
