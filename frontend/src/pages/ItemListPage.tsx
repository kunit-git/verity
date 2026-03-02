import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { Plus } from "lucide-react";
import { getItems, getItemTypes } from "../api/items";

export default function ItemListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const typeFilter = searchParams.get("type") || "";
  const statusFilter = searchParams.get("status") || "";
  const search = searchParams.get("search") || "";
  const page = searchParams.get("page") || "1";

  const params: Record<string, string> = { page };
  if (typeFilter) params.item_type__slug = typeFilter;
  if (statusFilter) params.status = statusFilter;
  if (search) params.search = search;

  const { data, isLoading } = useQuery({
    queryKey: ["items", params],
    queryFn: () => getItems(params),
  });

  const { data: itemTypes } = useQuery({
    queryKey: ["itemTypes"],
    queryFn: getItemTypes,
  });

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    next.delete("page");
    setSearchParams(next);
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Items</h1>
        <Link
          to="/items/new"
          className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          New Item
        </Link>
      </div>

      {/* Filters */}
      <div className="mt-4 flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Search..."
          value={search}
          onChange={(e) => setFilter("search", e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <select
          value={typeFilter}
          onChange={(e) => setFilter("type", e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="">All Types</option>
          {itemTypes?.map((t) => (
            <option key={t.id} value={t.slug}>
              {t.name}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setFilter("status", e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="in_review">In Review</option>
          <option value="approved">Approved</option>
          <option value="archived">Archived</option>
        </select>
      </div>

      {/* Table */}
      <div className="mt-4 overflow-hidden rounded-lg border border-gray-200 bg-white">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Title
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Created By
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Updated
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {data?.results.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link
                      to={`/items/${item.id}`}
                      className="font-medium text-blue-600 hover:text-blue-700"
                    >
                      {item.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
                      {item.item_type_name}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
                      {item.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {item.created_by_username}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(item.updated_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
              {data?.results.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-8 text-center text-sm text-gray-500"
                  >
                    No items found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {data && data.count > 50 && (
        <div className="mt-4 flex items-center justify-between">
          <p className="text-sm text-gray-500">{data.count} items total</p>
          <div className="flex gap-2">
            <button
              disabled={!data.previous}
              onClick={() => setFilter("page", String(Number(page) - 1))}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-50"
            >
              Previous
            </button>
            <button
              disabled={!data.next}
              onClick={() => setFilter("page", String(Number(page) + 1))}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
