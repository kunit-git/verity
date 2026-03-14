import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus, Trash2, Table2 } from "lucide-react";
import { getTables, deleteTable } from "../api/tables";
import { useAuth } from "../auth/AuthContext";

export default function TableListPage() {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const { data: tables, isLoading } = useQuery({
    queryKey: ["tables"],
    queryFn: getTables,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTable,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tables"] }),
  });

  return (
    <div className="p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tables</h1>
          <p className="mt-1 text-sm text-gray-500">
            Traceability tables that traverse item relations column by column.
          </p>
        </div>
        <Link
          to="/tables/new"
          className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          New Table
        </Link>
      </div>

      <div className="mt-6">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
          </div>
        ) : tables?.length === 0 ? (
          <div className="rounded-lg border-2 border-dashed border-gray-200 py-16 text-center">
            <Table2 className="mx-auto h-10 w-10 text-gray-300" />
            <p className="mt-3 text-sm font-medium text-gray-500">
              No tables yet
            </p>
            <p className="mt-1 text-sm text-gray-400">
              Create a table to trace items across relation types.
            </p>
            <Link
              to="/tables/new"
              className="mt-4 inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <Plus className="h-4 w-4" />
              New Table
            </Link>
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Description
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Columns
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Created By
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Updated
                  </th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {tables?.map((t) => (
                  <tr key={t.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <Link
                        to={`/tables/${t.id}`}
                        className="font-medium text-blue-600 hover:text-blue-700"
                      >
                        {t.name}
                      </Link>
                    </td>
                    <td className="max-w-xs px-4 py-3 text-sm text-gray-500">
                      <span className="line-clamp-1">{t.description || "—"}</span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {t.columns.length}{" "}
                      {t.columns.length === 1 ? "column" : "columns"}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {t.created_by_username}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {new Date(t.updated_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {user?.vault_role && user.vault_role !== "viewer" && (
                        <button
                          onClick={() => {
                            if (confirm(`Delete table "${t.name}"?`))
                              deleteMutation.mutate(t.id);
                          }}
                          className="rounded p-1 text-red-400 hover:bg-red-50 hover:text-red-600"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
