import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { getItemTableFieldData, patchItemTableAnnotation } from "../api/tableFields";
import type { AnyTableCell, TableAnnotationCell, TableDataCell } from "../types";
import { isAnnotationCell, isItemFieldCell, isFormulaCell } from "../types";

interface Props {
  itemId: string;
  fieldSlug: string;
  label: string;
}

type Row = AnyTableCell[];

function groupRowsBySeed(rows: Row[]): { seedId: string | null; rows: Row[] }[] {
  const groups: { seedId: string | null; rows: Row[] }[] = [];
  for (const row of rows) {
    const first = row[0];
    const seedId = first && "id" in first ? (first as TableDataCell).id : null;
    const last = groups[groups.length - 1];
    if (last && last.seedId === seedId) {
      last.rows.push(row);
    } else {
      groups.push({ seedId, rows: [row] });
    }
  }
  return groups;
}

export default function TableFieldWidget({ itemId, fieldSlug, label }: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: tableData, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["tableField", itemId, fieldSlug],
    queryFn: () => getItemTableFieldData(itemId, fieldSlug),
  });

  const annotateMutation = useMutation({
    mutationFn: ({ columnSlug, rowHash, value }: { columnSlug: string; rowHash: string; value: string }) =>
      patchItemTableAnnotation(itemId, fieldSlug, columnSlug, rowHash, value),
    onSuccess: (result) => {
      queryClient.setQueryData(["tableField", itemId, fieldSlug], (old: typeof tableData) => {
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
            })
          ),
        };
      });
    },
  });

  const groups = useMemo(
    () => (tableData ? groupRowsBySeed(tableData.rows) : []),
    [tableData]
  );

  if (isLoading) {
    return (
      <div className="py-4 text-center">
        <div className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  if (!tableData || tableData.columns.length === 0) {
    return (
      <p className="text-sm text-gray-400 italic">No data</p>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      {/* Mini header */}
      <div className="flex items-center justify-between border-b border-gray-100 px-3 py-2">
        <span className="text-xs font-semibold text-gray-600">{label}</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">
            {tableData.rows.length} {tableData.rows.length === 1 ? "row" : "rows"}
          </span>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="rounded p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-100">
          <thead className="bg-gray-50">
            <tr>
              {tableData.columns.map((col) => (
                <th
                  key={col.position}
                  className={`px-3 py-2 text-xs font-semibold uppercase tracking-wider text-gray-500 ${
                    col.kind === "formula" ? "text-right" : "text-left"
                  }`}
                >
                  {col.kind === "formula" && (
                    <span className="mr-1 font-mono text-purple-400">fx</span>
                  )}
                  {col.kind === "annotation" && (
                    <span className="mr-1 text-green-400">✎</span>
                  )}
                  {col.heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {groups.map((group) =>
              group.rows.map((row, rowIdx) => (
                <tr
                  key={`${group.seedId ?? "null"}-${rowIdx}`}
                  className="hover:bg-gray-50"
                >
                  {row.map((cell, colIdx) => (
                    <td key={colIdx} className="px-3 py-2">
                      <FieldTableCell
                        cell={cell}
                        colKind={tableData.columns[colIdx]?.kind}
                        onNavigate={(id) => navigate(`/items/${id}`)}
                        onAnnotate={(columnSlug, rowHash, value) =>
                          annotateMutation.mutate({ columnSlug, rowHash, value })
                        }
                      />
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FieldTableCell({
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
    return <span className="text-xs text-gray-300">—</span>;
  }

  if (isAnnotationCell(cell)) {
    return <AnnotationCell cell={cell} onSave={onAnnotate} />;
  }

  if (isItemFieldCell(cell)) {
    return (
      <span className="text-sm text-gray-700">
        {cell.value != null ? String(cell.value) : "—"}
      </span>
    );
  }

  if (colKind === "formula" && isFormulaCell(cell)) {
    const display = Number.isInteger(cell.value)
      ? cell.value.toString()
      : cell.value.toFixed(2);
    return (
      <span className="block text-right font-mono text-sm font-medium text-gray-800">
        {display}
      </span>
    );
  }

  if ("id" in cell) {
    const dataCell = cell as TableDataCell;
    return (
      <button
        onClick={() => onNavigate(dataCell.id)}
        className="group rounded px-1 py-0.5 text-left hover:bg-blue-50"
      >
        <p className="text-sm font-medium text-gray-800 group-hover:text-blue-700">
          {dataCell.title}
        </p>
        <p className="text-xs text-gray-400">{dataCell.item_type_name}</p>
      </button>
    );
  }

  return null;
}

function AnnotationCell({
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
