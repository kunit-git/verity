import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Users, KeyRound } from "lucide-react";
import { getUsers, updateUserRole, getSiteSettings, updateSiteSettings } from "../api/users";
import { useAuth } from "../auth/AuthContext";
import ChangePasswordDialog from "../components/ChangePasswordDialog";
import type { User } from "../types";

const ROLES: User["role"][] = ["viewer", "editor", "admin"];

export default function UserManagementPage() {
  const { user: me } = useAuth();
  const queryClient = useQueryClient();
  const [passwordTarget, setPasswordTarget] = useState<{
    id: number;
    username: string;
  } | null>(null);

  const { data: users, isLoading, isError } = useQuery({
    queryKey: ["users"],
    queryFn: getUsers,
  });

  const roleMutation = useMutation({
    mutationFn: ({ id, role }: { id: number; role: User["role"] }) =>
      updateUserRole(id, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  const { data: siteSettings } = useQuery({
    queryKey: ["site-settings"],
    queryFn: getSiteSettings,
  });

  const settingsMutation = useMutation({
    mutationFn: (patch: { registration_enabled: boolean }) =>
      updateSiteSettings(patch),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["site-settings"] }),
  });

  if (isError) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-gray-500">Access denied.</p>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center gap-3">
        <Users className="h-6 w-6 text-gray-400" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Users</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Manage user accounts and roles.
          </p>
        </div>
      </div>

      <div className="mt-6 flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3">
        <div>
          <p className="text-sm font-medium text-gray-900">User registration</p>
          <p className="text-xs text-gray-500">
            Allow new users to create accounts via the registration page.
          </p>
        </div>
        <button
          role="switch"
          aria-checked={siteSettings?.registration_enabled ?? true}
          onClick={() =>
            settingsMutation.mutate({
              registration_enabled: !(siteSettings?.registration_enabled ?? true),
            })
          }
          disabled={settingsMutation.isPending}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none disabled:opacity-50 ${
            siteSettings?.registration_enabled ? "bg-blue-600" : "bg-gray-300"
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
              siteSettings?.registration_enabled ? "translate-x-6" : "translate-x-1"
            }`}
          />
        </button>
      </div>

      <div className="mt-4">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Username
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Email
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Joined
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Role
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Password
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {users?.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {u.username}
                      {u.id === me?.id && (
                        <span className="ml-2 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-600">
                          you
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {u.email || "—"}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {new Date(u.date_joined).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={u.role}
                        disabled={u.id === me?.id}
                        onChange={(e) =>
                          roleMutation.mutate({
                            id: u.id,
                            role: e.target.value as User["role"],
                          })
                        }
                        className="rounded border border-gray-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() =>
                          setPasswordTarget({
                            id: u.id,
                            username: u.username,
                          })
                        }
                        className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                        title={`Change password for ${u.username}`}
                      >
                        <KeyRound className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {passwordTarget && (
        <ChangePasswordDialog
          targetUser={passwordTarget}
          onClose={() => setPasswordTarget(null)}
        />
      )}
    </div>
  );
}
