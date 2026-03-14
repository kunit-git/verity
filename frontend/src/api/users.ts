import api from "./client";
import type { User } from "../types";

export async function getUsers(): Promise<User[]> {
  const { data } = await api.get<User[]>("/auth/users/");
  return data;
}

export async function updateUserSiteAdmin(
  id: number,
  is_site_admin: boolean
): Promise<User> {
  const { data } = await api.patch<User>(`/auth/users/${id}/`, { is_site_admin });
  return data;
}

export async function changeOwnPassword(
  currentPassword: string,
  newPassword: string
): Promise<void> {
  await api.post("/auth/me/password/", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function adminChangePassword(
  userId: number,
  newPassword: string
): Promise<void> {
  await api.post(`/auth/users/${userId}/password/`, {
    new_password: newPassword,
  });
}

export interface SiteSettings {
  registration_enabled: boolean;
  mailbox_limit: number;
}

export async function getSiteSettings(): Promise<SiteSettings> {
  const { data } = await api.get<SiteSettings>("/auth/settings/");
  return data;
}

export async function updateSiteSettings(
  patch: Partial<SiteSettings>
): Promise<SiteSettings> {
  const { data } = await api.patch<SiteSettings>("/auth/settings/", patch);
  return data;
}

export async function createUser(payload: {
  username: string;
  email: string;
  password: string;
}): Promise<User> {
  const { data } = await api.post<User>("/auth/users/create/", payload);
  return data;
}

export async function lockUser(id: number): Promise<User> {
  const { data } = await api.post<User>(`/auth/users/${id}/lock/`);
  return data;
}

export async function unlockUser(id: number): Promise<User> {
  const { data } = await api.post<User>(`/auth/users/${id}/unlock/`);
  return data;
}

export async function deleteUser(id: number): Promise<User> {
  const { data } = await api.post<User>(`/auth/users/${id}/delete/`);
  return data;
}
