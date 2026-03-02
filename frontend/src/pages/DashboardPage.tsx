import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getItemTypes } from "../api/items";
import { getItems } from "../api/items";
import { useAuth } from "../auth/AuthContext";

export default function DashboardPage() {
  const { user } = useAuth();
  const { data: itemTypes } = useQuery({
    queryKey: ["itemTypes"],
    queryFn: getItemTypes,
  });
  const { data: recentItems } = useQuery({
    queryKey: ["items", "recent"],
    queryFn: () => getItems({ ordering: "-updated_at" }),
  });

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900">
        Welcome back, {user?.username}
      </h1>
      <p className="mt-1 text-sm text-gray-500">
        Systems engineering item management
      </p>

      {/* Stats cards */}
      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {itemTypes?.slice().sort((a, b) => a.name.localeCompare(b.name)).map((t) => (
          <Link
            key={t.id}
            to={`/items?type=${t.slug}`}
            className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
          >
            <p className="text-sm font-medium text-gray-500">{t.name}</p>
            <p className="mt-1 text-2xl font-bold text-gray-900">
              {t.item_count}
            </p>
          </Link>
        ))}
      </div>

      {/* Recent items */}
      <div className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Recent Items</h2>
          <Link
            to="/items"
            className="text-sm text-blue-600 hover:text-blue-700"
          >
            View all
          </Link>
        </div>

        <div className="mt-4 overflow-hidden rounded-lg border border-gray-200 bg-white">
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
                  Updated
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {recentItems?.results.slice(0, 10).map((item) => (
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
                    <StatusBadge status={item.status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(item.updated_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
              {recentItems?.results.length === 0 && (
                <tr>
                  <td
                    colSpan={4}
                    className="px-4 py-8 text-center text-sm text-gray-500"
                  >
                    No items yet.{" "}
                    <Link
                      to="/items/new"
                      className="text-blue-600 hover:text-blue-700"
                    >
                      Create your first item
                    </Link>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    draft: "bg-gray-100 text-gray-700",
    active: "bg-green-100 text-green-700",
    in_review: "bg-yellow-100 text-yellow-700",
    approved: "bg-blue-100 text-blue-700",
    archived: "bg-red-100 text-red-700",
  };
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] ?? colors.draft}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}
