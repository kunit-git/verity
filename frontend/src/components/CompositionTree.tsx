import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useInfiniteQuery, useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { ChevronRight, ChevronDown, ChevronUp, TreePine, AlertTriangle } from "lucide-react";
import { getRootItems, getItemChildren, getItemAncestors, reorderChildren } from "../api/items";
import type { TreeNode } from "../types";

const MIN_WIDTH = 180;
const MAX_WIDTH = 600;
const DEFAULT_WIDTH = 288; // w-72

interface Props {
  currentItemId?: string;
}

export default function CompositionTree({ currentItemId }: Props) {
  const navigate = useNavigate();
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const currentRef = useRef<HTMLButtonElement>(null);
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const isDragging = useRef(false);

  // Auto-expand ancestors when currentItemId changes
  const { data: ancestors } = useQuery({
    queryKey: ["tree", "ancestors", currentItemId],
    queryFn: () => getItemAncestors(currentItemId!),
    enabled: !!currentItemId && currentItemId !== "new",
  });

  const [previousAncestors, setPreviousAncestors] = useState<typeof ancestors>(undefined);
  if (ancestors !== previousAncestors) {
    setPreviousAncestors(ancestors);
    if (ancestors && ancestors.length > 0) {
      setExpandedNodes((prev) => {
        const next = new Set(prev);
        for (const id of ancestors) next.add(id);
        return next;
      });
    }
  }

  // Scroll current item into view
  useEffect(() => {
    if (currentRef.current) {
      currentRef.current.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [currentItemId, ancestors]);

  const toggle = useCallback((id: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // Root nodes with infinite query
  const roots = useInfiniteQuery({
    queryKey: ["tree", "roots"],
    queryFn: ({ pageParam = 1 }) => getRootItems(pageParam),
    getNextPageParam: (lastPage) => {
      if (!lastPage.next) return undefined;
      const p = new URL(lastPage.next).searchParams.get("page");
      return p ? parseInt(p, 10) : undefined;
    },
    initialPageParam: 1,
  });

  const rootNodes = roots.data?.pages.flatMap((p) => p.results) ?? [];

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    const startX = e.clientX;
    const startWidth = width;

    function onMouseMove(ev: MouseEvent) {
      if (!isDragging.current) return;
      const newWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startWidth + ev.clientX - startX));
      setWidth(newWidth);
    }

    function onMouseUp() {
      isDragging.current = false;
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, [width]);

  return (
    <div className="relative flex flex-shrink-0 flex-col border-r border-gray-200 bg-white" style={{ width }}>
      <div className="flex items-center gap-2 border-b border-gray-200 px-3 py-2.5">
        <TreePine className="h-4 w-4 text-gray-500" />
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Composition
        </span>
      </div>
      <div className="flex-1 overflow-y-auto py-1">
        {roots.isLoading ? (
          <p className="px-3 py-4 text-xs text-gray-400">Loading…</p>
        ) : rootNodes.length === 0 ? (
          <p className="px-3 py-4 text-xs text-gray-400">No items</p>
        ) : (
          <>
            {rootNodes.map((node) => (
              <TreeRow
                key={node.id}
                node={node}
                depth={0}
                currentItemId={currentItemId}
                expandedNodes={expandedNodes}
                onToggle={toggle}
                onNavigate={(id) => navigate(`/items/${id}`)}
                currentRef={currentRef}
              />
            ))}
            {roots.hasNextPage && (
              <button
                onClick={() => roots.fetchNextPage()}
                disabled={roots.isFetchingNextPage}
                className="w-full px-3 py-1.5 text-left text-xs text-blue-600 hover:bg-blue-50"
              >
                {roots.isFetchingNextPage ? "Loading…" : "Load more"}
              </button>
            )}
          </>
        )}
      </div>
      {/* Resize handle */}
      <div
        onMouseDown={handleMouseDown}
        className="absolute right-0 top-0 z-10 h-full w-1 cursor-col-resize hover:bg-blue-400 active:bg-blue-500"
      />
    </div>
  );
}

function TreeRow({
  node,
  depth,
  currentItemId,
  expandedNodes,
  onToggle,
  onNavigate,
  currentRef,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
}: {
  node: TreeNode;
  depth: number;
  currentItemId?: string;
  expandedNodes: Set<string>;
  onToggle: (id: string) => void;
  onNavigate: (id: string) => void;
  currentRef: React.RefObject<HTMLButtonElement | null>;
  onMoveUp?: (id: string) => void;
  onMoveDown?: (id: string) => void;
  isFirst?: boolean;
  isLast?: boolean;
}) {
  const isExpanded = expandedNodes.has(node.id);
  const isCurrent = node.id === currentItemId;
  const hasChildren = (node.child_count ?? 0) > 0;

  return (
    <>
      <div className="group flex items-center" style={{ paddingLeft: depth * 16 + 4 }}>
        <button
          ref={isCurrent ? currentRef : undefined}
          onClick={() => onNavigate(node.id)}
          className={`flex min-w-0 flex-1 items-center gap-1 py-1 pr-2 text-left text-sm hover:bg-gray-50 ${
            isCurrent ? "bg-blue-50 text-blue-700" : "text-gray-700"
          }`}
        >
          {hasChildren ? (
            <span
              onClick={(e) => {
                e.stopPropagation();
                onToggle(node.id);
              }}
              className="flex h-5 w-5 shrink-0 cursor-pointer items-center justify-center rounded hover:bg-gray-200"
            >
              {isExpanded ? (
                <ChevronDown className="h-3.5 w-3.5" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5" />
              )}
            </span>
          ) : (
            <span className="h-5 w-5 shrink-0" />
          )}
          <span className="truncate">{node.title}</span>
          {node.has_suspect_links ? (
            <span title="Has suspect links">
              <AlertTriangle className="ml-1 h-3 w-3 shrink-0 text-amber-500" />
            </span>
          ) : node.has_suspect_descendants ? (
            <span title="Descendant has suspect links">
              <AlertTriangle className="ml-1 h-3 w-3 shrink-0 text-amber-300" />
            </span>
          ) : null}
        </button>
        {onMoveUp && onMoveDown && (
          <span className="mr-1 flex shrink-0 opacity-0 group-hover:opacity-100">
            {!isFirst && (
              <button
                onClick={(e) => { e.stopPropagation(); onMoveUp(node.id); }}
                className="flex h-5 w-5 items-center justify-center rounded text-gray-400 hover:bg-gray-200 hover:text-gray-600"
                title="Move up"
              >
                <ChevronUp className="h-3.5 w-3.5" />
              </button>
            )}
            {!isLast && (
              <button
                onClick={(e) => { e.stopPropagation(); onMoveDown(node.id); }}
                className="flex h-5 w-5 items-center justify-center rounded text-gray-400 hover:bg-gray-200 hover:text-gray-600"
                title="Move down"
              >
                <ChevronDown className="h-3.5 w-3.5" />
              </button>
            )}
          </span>
        )}
      </div>
      {isExpanded && hasChildren && (
        <ChildNodes
          parentId={node.id}
          depth={depth + 1}
          currentItemId={currentItemId}
          expandedNodes={expandedNodes}
          onToggle={onToggle}
          onNavigate={onNavigate}
          currentRef={currentRef}
        />
      )}
    </>
  );
}

function ChildNodes({
  parentId,
  depth,
  currentItemId,
  expandedNodes,
  onToggle,
  onNavigate,
  currentRef,
}: {
  parentId: string;
  depth: number;
  currentItemId?: string;
  expandedNodes: Set<string>;
  onToggle: (id: string) => void;
  onNavigate: (id: string) => void;
  currentRef: React.RefObject<HTMLButtonElement | null>;
}) {
  const queryClient = useQueryClient();
  const { data, hasNextPage, fetchNextPage, isFetchingNextPage, isLoading } =
    useInfiniteQuery({
      queryKey: ["tree", "children", parentId],
      queryFn: ({ pageParam = 1 }) => getItemChildren(parentId, pageParam),
      getNextPageParam: (lastPage) => {
        if (!lastPage.next) return undefined;
        const p = new URL(lastPage.next).searchParams.get("page");
        return p ? parseInt(p, 10) : undefined;
      },
      initialPageParam: 1,
    });

  const children = useMemo(() => data?.pages.flatMap((p) => p.results) ?? [], [data]);

  const reorderMutation = useMutation({
    mutationFn: (childIds: string[]) => reorderChildren(parentId, childIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tree", "children", parentId] });
    },
  });

  const handleMove = useCallback(
    (id: string, direction: "up" | "down") => {
      const idx = children.findIndex((c) => c.id === id);
      if (idx < 0) return;
      const swapIdx = direction === "up" ? idx - 1 : idx + 1;
      if (swapIdx < 0 || swapIdx >= children.length) return;
      const newOrder = children.map((c) => c.id);
      [newOrder[idx], newOrder[swapIdx]] = [newOrder[swapIdx], newOrder[idx]];
      reorderMutation.mutate(newOrder);
    },
    [children, reorderMutation],
  );

  if (isLoading) {
    return (
      <p
        className="py-1 text-xs text-gray-400"
        style={{ paddingLeft: depth * 16 + 24 }}
      >
        Loading…
      </p>
    );
  }

  return (
    <>
      {children.map((child, idx) => (
        <TreeRow
          key={child.id}
          node={child}
          depth={depth}
          currentItemId={currentItemId}
          expandedNodes={expandedNodes}
          onToggle={onToggle}
          onNavigate={onNavigate}
          currentRef={currentRef}
          onMoveUp={(id) => handleMove(id, "up")}
          onMoveDown={(id) => handleMove(id, "down")}
          isFirst={idx === 0}
          isLast={idx === children.length - 1}
        />
      ))}
      {hasNextPage && (
        <button
          onClick={() => fetchNextPage()}
          disabled={isFetchingNextPage}
          className="w-full text-left text-xs text-blue-600 hover:bg-blue-50"
          style={{ paddingLeft: depth * 16 + 24, paddingTop: 2, paddingBottom: 2 }}
        >
          {isFetchingNextPage ? "Loading…" : "Load more"}
        </button>
      )}
    </>
  );
}
