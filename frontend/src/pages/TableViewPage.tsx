import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Pencil, RefreshCw } from "lucide-react";
import { getTable, getTableData } from "../api/tables";
import type { TableDataCell } from "../types";

export default function TableViewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

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
            <p className="mb-3 text-sm text-gray-400">
              {tableData.rows.length}{" "}
              {tableData.rows.length === 1 ? "row" : "rows"}
            </p>
            <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
              <table className="min-w-max divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {tableData.columns.map((col) => (
                      <th
                        key={col.position}
                        className="min-w-[220px] px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500"
                      >
                        {col.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {tableData.rows.map((row, rowIdx) => (
                    <tr key={rowIdx} className="hover:bg-gray-50">
                      {row.map((cell, colIdx) => (
                        <td key={colIdx} className="px-4 py-2.5">
                          <TableCell
                            cell={cell}
                            onNavigate={(itemId) =>
                              navigate(`/items/${itemId}`)
                            }
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
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
  onNavigate,
}: {
  cell: TableDataCell | null;
  onNavigate: (id: string) => void;
}) {
  if (!cell) {
    return (
      <span className="text-sm text-gray-300" title="No matching relation">
        —
      </span>
    );
  }

  return (
    <button
      onClick={() => onNavigate(cell.id)}
      className="group w-full rounded px-1 py-0.5 text-left hover:bg-blue-50"
    >
      <p className="text-sm font-medium text-gray-800 group-hover:text-blue-700">
        {cell.title}
      </p>
      <p className="text-xs text-gray-400">{cell.item_type_name}</p>
    </button>
  );
}
