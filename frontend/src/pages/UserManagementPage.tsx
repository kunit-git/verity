import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Users, KeyRound, Lock, LockOpen, Trash2, UserPlus } from "lucide-react";
import { getUsers, updateUserSiteAdmin, getSiteSettings, updateSiteSettings, lockUser, unlockUser, deleteUser, createUser } from "../api/users";
import { useAuth } from "../auth/AuthContext";
import { useConfirm } from "../components/ConfirmDialog";
import ChangePasswordDialog from "../components/ChangePasswordDialog";

function MailboxLimitControl({
  value,
  onSave,
  isPending,
}: {
  value: number;
  onSave: (v: number) => void;
  isPending: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleSave() {
    const v = parseInt(inputRef.current?.value ?? "0", 10);
    if (!isNaN(v) && v >= 0) {
      onSave(v);
    }
    setEditing(false);
  }

  return (
    <div className="mt-2 flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3">
      <div>
        <p className="text-sm font-medium text-gray-900">Mailbox document limit</p>
        <p className="text-xs text-gray-500">
          Maximum documents per user. Set to 0 for unlimited.
        </p>
      </div>
      {editing ? (
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="number"
            min={0}
            defaultValue={value}
            className="w-20 rounded border border-gray-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none"
          />
          <button
            onClick={handleSave}
            disabled={isPending}
            className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Save
          </button>
          <button
            onClick={() => setEditing(false)}
            className="rounded px-2 py-1 text-sm text-gray-500 hover:bg-gray-100"
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          onClick={() => setEditing(true)}
          className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-700 hover:bg-gray-50"
        >
          {value === 0 ? "Unlimited" : value}
        </button>
      )}
    </div>
  );
}

function AddUserDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      onCreated();
      onClose();
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: Record<string, string[]> } })?.response
          ?.data;
      if (detail) {
        const first = Object.values(detail)[0];
        setError(Array.isArray(first) ? first[0] : String(first));
      } else {
        setError("Failed to create user.");
      }
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    mutation.mutate({ username, email, password });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Add User</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">
              Username
            </label>
            <input
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">
              Password
            </label>
            <input
              required
              type="password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="mt-1 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="rounded bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {mutation.isPending ? "Creating…" : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function UserManagementPage() {
  const { user: me } = useAuth();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [passwordTarget, setPasswordTarget] = useState<{
    id: number;
    username: string;
  } | null>(null);
  const [showAddUser, setShowAddUser] = useState(false);

  const { data: users, isLoading, isError } = useQuery({
    queryKey: ["users"],
    queryFn: getUsers,
  });

  const siteAdminMutation = useMutation({
    mutationFn: ({ id, is_site_admin }: { id: number; is_site_admin: boolean }) =>
      updateUserSiteAdmin(id, is_site_admin),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  const lockMutation = useMutation({
    mutationFn: (id: number) => lockUser(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  const unlockMutation = useMutation({
    mutationFn: (id: number) => unlockUser(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteUser(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  const { data: siteSettings } = useQuery({
    queryKey: ["site-settings"],
    queryFn: getSiteSettings,
  });

  const settingsMutation = useMutation({
    mutationFn: (patch: Partial<{ registration_enabled: boolean; mailbox_limit: number }>) =>
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
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Users className="h-6 w-6 text-gray-400" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Users</h1>
            <p className="mt-0.5 text-sm text-gray-500">
              Manage user accounts and roles.
            </p>
          </div>
        </div>
        <button
          onClick={() => setShowAddUser(true)}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <UserPlus className="h-4 w-4" />
          Add User
        </button>
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

      <MailboxLimitControl
        value={siteSettings?.mailbox_limit ?? 0}
        onSave={(v) => settingsMutation.mutate({ mailbox_limit: v })}
        isPending={settingsMutation.isPending}
      />

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
                    Site Admin
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Password
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {users?.map((u) => {
                  const isLocked = u.account_status === "locked";
                  const isSelf = u.id === me?.id;
                  return (
                  <tr key={u.id} className={`hover:bg-gray-50 ${isLocked ? "opacity-60" : ""}`}>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {u.username}
                      {isSelf && (
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
                      <button
                        role="switch"
                        aria-checked={u.is_site_admin}
                        disabled={isSelf || isLocked}
                        onClick={() =>
                          siteAdminMutation.mutate({
                            id: u.id,
                            is_site_admin: !u.is_site_admin,
                          })
                        }
                        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 ${
                          u.is_site_admin ? "bg-blue-600" : "bg-gray-300"
                        }`}
                      >
                        <span
                          className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                            u.is_site_admin ? "translate-x-[18px]" : "translate-x-[2px]"
                          }`}
                        />
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      {isLocked ? (
                        <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
                          Locked
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                          Active
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() =>
                          setPasswordTarget({
                            id: u.id,
                            username: u.username,
                          })
                        }
                        disabled={isLocked}
                        className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:cursor-not-allowed disabled:opacity-50"
                        title={`Change password for ${u.username}`}
                      >
                        <KeyRound className="h-4 w-4" />
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      {!isSelf && (
                        <div className="flex items-center gap-1">
                          {isLocked ? (
                            <button
                              onClick={() => unlockMutation.mutate(u.id)}
                              disabled={unlockMutation.isPending}
                              className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-50"
                              title={`Unlock ${u.username}`}
                            >
                              <LockOpen className="h-4 w-4" />
                            </button>
                          ) : (
                            <button
                              onClick={() => lockMutation.mutate(u.id)}
                              disabled={lockMutation.isPending}
                              className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-50"
                              title={`Lock ${u.username}`}
                            >
                              <Lock className="h-4 w-4" />
                            </button>
                          )}
                          <button
                            onClick={async () => {
                              if (await confirm(`Permanently delete the account "${u.username}"? This cannot be undone.`)) {
                                deleteMutation.mutate(u.id);
                              }
                            }}
                            disabled={deleteMutation.isPending}
                            className="rounded p-1 text-red-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                            title={`Delete ${u.username}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                  );
                })}
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

      {showAddUser && (
        <AddUserDialog
          onClose={() => setShowAddUser(false)}
          onCreated={() => queryClient.invalidateQueries({ queryKey: ["users"] })}
        />
      )}
    </div>
  );
}
