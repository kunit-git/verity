import api from "./client";
import type { User } from "../types";

export async function login(username: string, password: string) {
  const { data } = await api.post<{ access: string; refresh: string }>(
    "/auth/login/",
    { username, password }
  );
  localStorage.setItem("access_token", data.access);
  localStorage.setItem("refresh_token", data.refresh);
  return data;
}

export async function register(
  username: string,
  email: string,
  password: string
) {
  const { data } = await api.post("/auth/register/", {
    username,
    email,
    password,
  });
  return data;
}

export async function getMe() {
  const { data } = await api.get<User>("/auth/me/");
  return data;
}

export function logout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}
