import { useState, useMemo, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Pencil,
  RefreshCw,
  ChevronRight,
  ChevronDown,
  ChevronsUpDown,
} from "lucide-react";
import { getTable, getTableData, patchMatrixAnnotation } from "../api/tables";
import type {
  AnyTableCell,
  TableAnnotationCell,
  TableDataCell,
} from "../types";
import {
  isAnnotationCell,
  isFormulaCell,
  isItemFieldCell,
} from "../types";

type Row = AnyTableCell[];

interface RowGroup {
  seedId: string | null;
  rows: Row[];
}

function groupRowsBySeed(rows: Row[]): RowGroup[] {
  const groups: RowGroup[] = [];
  for (const row of rows) {
    const seedCell = row[0];
    const seedId = seedCell && "id" in seedCell ? (seedCell as TableDataCell).id : null;
    const last = groups[groups.length - 1];
    if (last && last.seedId === seedId) {
      last.rows.push(row);
    } else {
      groups.push({ seedId, rows: [row] });
    }
  }
  return groups;
}

export default function TableViewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  const { data: table } = useQuery({
    queryKey: ["table", id],
    queryFn: () => getTable(id!),
    enabled: !!id,
  });

  const {
    data: tableData,
    isLoading,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["tableData", id],
    queryFn: () => getTableData(id!),
    enabled: !!id,
  });

  const annotateMutation = useMutation({
    mutationFn: ({
      columnSlug,
      rowHash,
      value,
    }: {
      columnSlug: string;
      rowHash: string;
      value: string;
    }) => patchMatrixAnnotation(id!, columnSlug, rowHash, value),
    onSuccess: (result) => {
      // Update the cache directly instead of a full refetch
      queryClient.setQueryData(["tableData", id], (old: typeof tableData) => {
        if (!old) return old;
        return {
          ...old,
          rows: old.rows.map((row) =>
            row.map((cell) => {
              if (
                isAnnotationCell(cell) &&
                cell.column_slug === result.column_slug &&
                cell.row_hash === result.row_hash
              ) {
                return { ...cell, value: result.value };
              }
              return cell;
            }),
          ),
        };
      });
    },
  });

  const groups = useMemo(
    () => (tableData ? groupRowsBySeed(tableData.rows) : []),
    [tableData],
  );

  const multiRowGroupIds = useMemo(
    () =>
      new Set(
        groups
          .filter((g) => g.rows.length > 1 && g.seedId)
          .map((g) => g.seedId!),
      ),
    [groups],
  );

  const toggleGroup = useCallback((seedId: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(seedId)) next.delete(seedId);
      else next.add(seedId);
      return next;
    });
  }, []);

  const allExpanded =
    multiRowGroupIds.size > 0 &&
    [...multiRowGroupIds].every((id) => expandedGroups.has(id));

  const toggleAll = useCallback(() => {
    if (allExpanded) {
      setExpandedGroups(new Set());
    } else {
      setExpandedGroups(new Set(multiRowGroupIds));
    }
  }, [allExpanded, multiRowGroupIds]);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-gray-200 bg-white px-6 py-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">
            {table?.name ?? "Table"}
          </h1>
          {table?.description && (
            <p className="mt-0.5 text-sm text-gray-500">{table.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
          <Link
            to={`/tables/${id}/edit`}
            className="flex items-center gap-1.5 rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
          >
            <Pencil className="h-3.5 w-3.5" />
            Edit
          </Link>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto p-6">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
          </div>
        ) : !tableData || tableData.columns.length === 0 ? (
          <div className="rounded-lg border-2 border-dashed border-gray-200 py-16 text-center">
            <p className="text-sm font-medium text-gray-500">No data</p>
            <p className="mt-1 text-sm text-gray-400">
              Check your column configuration or{" "}
              <Link
                to={`/tables/${id}/edit`}
                className="text-blue-600 hover:underline"
              >
                edit this table
              </Link>
              .
            </p>
          </div>
        ) : (
          <>
            <div className="mb-3 flex items-center gap-3">
              <p className="text-sm text-gray-400">
                {tableData.rows.length}{" "}
                {tableData.rows.length === 1 ? "row" : "rows"}
              </p>
              {multiRowGroupIds.size > 0 && (
                <button
                  onClick={toggleAll}
                  className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600"
                >
                  <ChevronsUpDown className="h-3 w-3" />
                  {allExpanded ? "Collapse all" : "Expand all"}
                </button>
              )}
            </div>
            <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
              <table className="min-w-max divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {tableData.columns.map((col) => (
                      <th
                        key={col.position}
                        className={`min-w-[220px] px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 ${
                          col.kind === "formula" ? "text-right" : "text-left"
                        }`}
                      >
                        {col.kind === "formula" && (
                          <span className="mr-1 font-mono text-purple-400">
                            fx
                          </span>
                        )}
                        {col.kind === "annotation" && (
                          <span className="mr-1 text-green-400" title="Editable annotation">✎</span>
                        )}
                        {col.heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {groups.map((group) => {
                    const isMulti = group.rows.length > 1 && group.seedId;
                    const isExpanded =
                      isMulti && expandedGroups.has(group.seedId!);
                    const visibleRows = isMulti && !isExpanded
                      ? [group.rows[0]]
                      : group.rows;

                    return visibleRows.map((row, rowIdx) => (
                      <tr
                        key={`${group.seedId ?? "null"}-${rowIdx}`}
                        className="hover:bg-gray-50"
                      >
                        {row.map((cell, colIdx) => (
                          <td
                            key={colIdx}
                            className={`px-4 py-2.5 ${
                              isMulti && isExpanded && rowIdx > 0 && colIdx === 0
                                ? "border-l-2 border-blue-200"
                                : ""
                            }`}
                          >
                            {colIdx === 0 && multiRowGroupIds.size > 0 ? (
                              <div className="flex items-center gap-1">
                                {isMulti && rowIdx === 0 ? (
                                  <button
                                    onClick={() =>
                                      toggleGroup(group.seedId!)
                                    }
                                    className="flex shrink-0 items-center rounded p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                                  >
                                    {isExpanded ? (
                                      <ChevronDown className="h-3.5 w-3.5" />
                                    ) : (
                                      <ChevronRight className="h-3.5 w-3.5" />
                                    )}
                                  </button>
                                ) : (
                                  <span className="w-[22px] shrink-0" />
                                )}
                                <div className="min-w-0 flex-1">
                                  <TableCell
                                    cell={cell}
                                    colKind={tableData.columns[colIdx]?.kind}
                                    onNavigate={(itemId) =>
                                      navigate(`/items/${itemId}`)
                                    }
                                    onAnnotate={(columnSlug, rowHash, value) =>
                                      annotateMutation.mutate({ columnSlug, rowHash, value })
                                    }
                                  />
                                </div>
                                {isMulti && rowIdx === 0 && !isExpanded && (
                                  <span className="shrink-0 rounded-full bg-gray-100 px-1.5 py-0.5 text-xs text-gray-400">
                                    +{group.rows.length - 1}
                                  </span>
                                )}
                              </div>
                            ) : (
                              <TableCell
                                cell={cell}
                                colKind={tableData.columns[colIdx]?.kind}
                                onNavigate={(itemId) =>
                                  navigate(`/items/${itemId}`)
                                }
                                onAnnotate={(columnSlug, rowHash, value) =>
                                  annotateMutation.mutate({ columnSlug, rowHash, value })
                                }
                              />
                            )}
                          </td>
                        ))}
                      </tr>
                    ));
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function TableCell({
  cell,
  colKind,
  onNavigate,
  onAnnotate,
}: {
  cell: AnyTableCell;
  colKind: string | undefined;
  onNavigate: (id: string) => void;
  onAnnotate: (columnSlug: string, rowHash: string, value: string) => void;
}) {
  if (!cell) {
    return (
      <span className="text-sm text-gray-300" title="No matching relation">
        —
      </span>
    );
  }

  if (isAnnotationCell(cell)) {
    return <AnnotationInput cell={cell} onSave={onAnnotate} />;
  }

  if (isItemFieldCell(cell)) {
    const display = cell.value != null ? String(cell.value) : "—";
    return <span className="text-sm text-gray-700">{display}</span>;
  }

  if (colKind === "formula" && isFormulaCell(cell)) {
    const display =
      Number.isInteger(cell.value) ? cell.value.toString() : cell.value.toFixed(2);
    return (
      <span className="block text-right font-mono text-sm font-medium text-gray-800">
        {display}
      </span>
    );
  }

  if ("id" in cell) {
    return (
      <button
        onClick={() => onNavigate((cell as TableDataCell).id)}
        className="group w-full rounded px-1 py-0.5 text-left hover:bg-blue-50"
      >
        <p className="text-sm font-medium text-gray-800 group-hover:text-blue-700">
          {(cell as TableDataCell).title}
        </p>
        <p className="text-xs text-gray-400">{(cell as TableDataCell).item_type_name}</p>
      </button>
    );
  }

  return null;
}

function AnnotationInput({
  cell,
  onSave,
}: {
  cell: TableAnnotationCell;
  onSave: (columnSlug: string, rowHash: string, value: string) => void;
}) {
  const [value, setValue] = useState(cell.value);

  return (
    <input
      type="text"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={() => {
        if (value !== cell.value) {
          onSave(cell.column_slug, cell.row_hash, value);
        }
      }}
      placeholder="Add note…"
      className="w-full rounded border border-transparent bg-transparent px-1 py-0.5 text-sm text-gray-700 placeholder-gray-300 hover:border-gray-200 focus:border-blue-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-200"
    />
  );
}
