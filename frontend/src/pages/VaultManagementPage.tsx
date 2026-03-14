import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, UserPlus, X } from "lucide-react";
import * as vaultsApi from "../api/vaults";
import { getUsers } from "../api/users";
import type { VaultMembership } from "../types";

const VAULT_ROLES: VaultMembership["role"][] = ["viewer", "editor", "admin"];

function slugify(text: string) {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .replace(/[\s_]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export default function VaultManagementPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [expandedVault, setExpandedVault] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [error, setError] = useState("");

  const { data: vaults, isLoading } = useQuery({
    queryKey: ["admin-vaults"],
    queryFn: vaultsApi.getVaults,
  });

  const createMutation = useMutation({
    mutationFn: vaultsApi.createVault,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-vaults"] });
      setShowCreate(false);
      setNewName("");
      setNewSlug("");
      setNewDesc("");
      setError("");
    },
    onError: () => setError("Failed to create vault."),
  });

  const deleteMutation = useMutation({
    mutationFn: vaultsApi.deleteVault,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-vaults"] });
    },
  });

  const handleCreate = () => {
    if (!newName.trim()) return;
    const slug = newSlug.trim() || slugify(newName);
    createMutation.mutate({ name: newName.trim(), slug, description: newDesc.trim() });
  };

  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Vault Management</h1>
        <button
          onClick={() => setShowCreate((v) => !v)}
          className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          New Vault
        </button>
      </div>

      {showCreate && (
        <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="mb-3 font-medium text-gray-900">Create Vault</h3>
          {error && (
            <div className="mb-3 rounded bg-red-50 p-2 text-sm text-red-700">{error}</div>
          )}
          <div className="space-y-3">
            <input
              type="text"
              placeholder="Vault name"
              value={newName}
              onChange={(e) => {
                setNewName(e.target.value);
                if (!newSlug || newSlug === slugify(newName)) {
                  setNewSlug(slugify(e.target.value));
                }
              }}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
            <input
              type="text"
              placeholder="Slug"
              value={newSlug}
              onChange={(e) => setNewSlug(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
            <textarea
              placeholder="Description (optional)"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              rows={2}
            />
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                disabled={createMutation.isPending}
                className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {createMutation.isPending ? "Creating..." : "Create"}
              </button>
              <button
                onClick={() => { setShowCreate(false); setError(""); }}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
        </div>
      ) : (
        <div className="space-y-3">
          {vaults?.map((vault) => (
            <div key={vault.id} className="rounded-lg border border-gray-200 bg-white">
              <div className="flex items-center justify-between px-4 py-3">
                <button
                  onClick={() => setExpandedVault(expandedVault === vault.id ? null : vault.id)}
                  className="flex-1 text-left"
                >
                  <p className="font-medium text-gray-900">{vault.name}</p>
                  <p className="text-sm text-gray-500">
                    {vault.member_count} member{vault.member_count !== 1 ? "s" : ""}
                    {vault.description && ` \u2014 ${vault.description}`}
                  </p>
                </button>
                <button
                  onClick={() => {
                    if (confirm(`Delete vault "${vault.name}"?`)) {
                      deleteMutation.mutate(vault.id);
                    }
                  }}
                  className="rounded p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600"
                  title="Delete vault"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              {expandedVault === vault.id && (
                <VaultMemberPanel vaultId={vault.id} />
              )}
            </div>
          ))}
          {!vaults?.length && (
            <p className="py-8 text-center text-gray-500">No vaults yet.</p>
          )}
        </div>
      )}
    </div>
  );
}

function VaultMemberPanel({ vaultId }: { vaultId: string }) {
  const queryClient = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [selectedRole, setSelectedRole] = useState<string>("viewer");

  const { data: members } = useQuery({
    queryKey: ["vault-members", vaultId],
    queryFn: () => vaultsApi.getVaultMembers(vaultId),
  });

  const { data: allUsers } = useQuery({
    queryKey: ["users"],
    queryFn: getUsers,
    enabled: showAdd,
  });

  const addMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: string }) =>
      vaultsApi.addVaultMember(vaultId, userId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["vault-members", vaultId] });
      queryClient.invalidateQueries({ queryKey: ["admin-vaults"] });
      setShowAdd(false);
      setSelectedUserId(null);
      setSelectedRole("viewer");
    },
  });

  const updateRoleMutation = useMutation({
    mutationFn: ({ membershipId, role }: { membershipId: string; role: string }) =>
      vaultsApi.updateVaultMemberRole(vaultId, membershipId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["vault-members", vaultId] });
    },
  });

  const removeMutation = useMutation({
    mutationFn: (membershipId: string) => vaultsApi.removeVaultMember(vaultId, membershipId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["vault-members", vaultId] });
      queryClient.invalidateQueries({ queryKey: ["admin-vaults"] });
    },
  });

  const memberUserIds = new Set(members?.map((m) => m.user) ?? []);
  const availableUsers = allUsers?.filter((u) => !memberUserIds.has(u.id)) ?? [];

  return (
    <div className="border-t border-gray-200 px-4 py-3">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-sm font-medium text-gray-700">Members</h4>
        <button
          onClick={() => setShowAdd((v) => !v)}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50"
        >
          <UserPlus className="h-3.5 w-3.5" />
          Add
        </button>
      </div>

      {showAdd && (
        <div className="mb-3 flex items-center gap-2">
          <select
            value={selectedUserId ?? ""}
            onChange={(e) => setSelectedUserId(e.target.value ? Number(e.target.value) : null)}
            className="flex-1 rounded-md border border-gray-300 px-2 py-1.5 text-sm"
          >
            <option value="">Select user...</option>
            {availableUsers.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username}
              </option>
            ))}
          </select>
          <select
            value={selectedRole}
            onChange={(e) => setSelectedRole(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1.5 text-sm"
          >
            {VAULT_ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <button
            onClick={() => selectedUserId && addMutation.mutate({ userId: selectedUserId, role: selectedRole })}
            disabled={!selectedUserId || addMutation.isPending}
            className="rounded-md bg-blue-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-60"
          >
            Add
          </button>
          <button
            onClick={() => { setShowAdd(false); setSelectedUserId(null); setSelectedRole("viewer"); }}
            className="rounded p-1 text-gray-400 hover:text-gray-600"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {members?.length ? (
        <div className="space-y-1">
          {members.map((m) => (
            <div key={m.id} className="flex items-center justify-between rounded px-2 py-1.5 text-sm hover:bg-gray-50">
              <span>
                <span className="font-medium text-gray-900">{m.username}</span>
                {m.is_site_admin && (
                  <span className="ml-2 rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-600">
                    site admin
                  </span>
                )}
              </span>
              <div className="flex items-center gap-2">
                {m.is_site_admin ? (
                  <span className="px-1.5 py-0.5 text-xs text-gray-400">admin</span>
                ) : (
                  <>
                    <select
                      value={m.role}
                      onChange={(e) =>
                        updateRoleMutation.mutate({
                          membershipId: m.id,
                          role: e.target.value,
                        })
                      }
                      className="rounded border border-gray-300 px-1.5 py-0.5 text-xs focus:border-blue-500 focus:outline-none"
                    >
                      {VAULT_ROLES.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => removeMutation.mutate(m.id)}
                      className="rounded p-1 text-gray-400 hover:text-red-600"
                      title="Remove member"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-400">No members yet.</p>
      )}
    </div>
  );
}
