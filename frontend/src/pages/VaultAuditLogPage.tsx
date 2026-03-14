import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import * as vaultsApi from "../api/vaults";
import type { VaultAuditLogEntry } from "../types";

const EVENT_LABELS: Record<string, string> = {
  vault_created: "Vault created",
  member_added: "Member added",
  member_removed: "Member removed",
  member_role_changed: "Member role changed",
  vault_locked: "Vault locked",
  vault_unlocked: "Vault unlocked",
};

function formatDetail(entry: VaultAuditLogEntry): string {
  const d = entry.detail;
  switch (entry.event) {
    case "member_added":
      return `${d.user} added as ${d.role}`;
    case "member_removed":
      return `${d.user} removed`;
    case "member_role_changed":
      return `${d.user}: ${d.old_role} \u2192 ${d.new_role}`;
    default:
      return "";
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

export default function VaultAuditLogPage() {
  const { id } = useParams<{ id: string }>();

  const { data: vault } = useQuery({
    queryKey: ["vault-detail-for-audit", id],
    queryFn: () => vaultsApi.getMyVaults().then((vaults) => vaults.find((v) => v.id === id)),
    enabled: !!id,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["vault-audit-log", id],
    queryFn: () => vaultsApi.getVaultAuditLog(id!),
    enabled: !!id,
  });

  const entries = data?.results ?? [];

  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="mb-6">
        <Link
          to="/manage/vaults"
          className="mb-3 inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to vaults
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">
          Audit Log {vault ? `\u2014 ${vault.name}` : ""}
        </h1>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
        </div>
      ) : entries.length === 0 ? (
        <p className="py-8 text-center text-gray-500">No audit log entries yet.</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-gray-200 bg-gray-50">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium text-gray-600">Time</th>
                <th className="px-4 py-2.5 text-left font-medium text-gray-600">Event</th>
                <th className="px-4 py-2.5 text-left font-medium text-gray-600">User</th>
                <th className="px-4 py-2.5 text-left font-medium text-gray-600">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {entries.map((entry) => (
                <tr key={entry.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-4 py-2.5 text-gray-500">
                    {formatDate(entry.created_at)}
                  </td>
                  <td className="px-4 py-2.5 font-medium text-gray-900">
                    {EVENT_LABELS[entry.event] ?? entry.event}
                  </td>
                  <td className="px-4 py-2.5 text-gray-700">{entry.actor_username}</td>
                  <td className="px-4 py-2.5 text-gray-500">{formatDetail(entry)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
