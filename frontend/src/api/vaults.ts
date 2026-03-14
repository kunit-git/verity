import api from "./client";
import type { PaginatedResponse, Vault, VaultAuditLogEntry, VaultMembership } from "../types";

export async function getMyVaults() {
  const { data } = await api.get<Vault[]>("/vaults/my/");
  return data;
}

export async function selectVault(vaultId: string) {
  const { data } = await api.post<{ detail: string; vault_id: string; vault_name: string }>(
    "/vaults/select/",
    { vault_id: vaultId }
  );
  return data;
}

export async function getVaults() {
  const { data } = await api.get<Vault[]>("/vaults/");
  return data;
}

export async function createVault(payload: { name: string; slug: string; description?: string }) {
  const { data } = await api.post<Vault>("/vaults/", payload);
  return data;
}

export async function updateVault(id: string, payload: { name?: string; slug?: string; description?: string }) {
  const { data } = await api.patch<Vault>(`/vaults/${id}/`, payload);
  return data;
}

export async function deleteVault(id: string) {
  await api.delete(`/vaults/${id}/`);
}

export async function getVaultMembers(vaultId: string) {
  const { data } = await api.get<VaultMembership[]>(`/vaults/${vaultId}/members/`);
  return data;
}

export async function addVaultMember(vaultId: string, userId: number, role: string = "viewer") {
  const { data } = await api.post<VaultMembership>(`/vaults/${vaultId}/members/`, { user: userId, role });
  return data;
}

export async function updateVaultMemberRole(vaultId: string, membershipId: string, role: string) {
  const { data } = await api.patch<VaultMembership>(
    `/vaults/${vaultId}/members/${membershipId}/`,
    { role }
  );
  return data;
}

export async function removeVaultMember(vaultId: string, membershipId: string) {
  await api.delete(`/vaults/${vaultId}/members/${membershipId}/`);
}

export async function lockVault(id: string) {
  const { data } = await api.post<{ detail: string }>(`/vaults/${id}/lock/`);
  return data;
}

export async function unlockVault(id: string) {
  const { data } = await api.post<{ detail: string }>(`/vaults/${id}/unlock/`);
  return data;
}

export async function getVaultAuditLog(vaultId: string, page = 1) {
  const { data } = await api.get<PaginatedResponse<VaultAuditLogEntry>>(
    `/vaults/${vaultId}/audit-log/`,
    { params: { page } }
  );
  return data;
}
