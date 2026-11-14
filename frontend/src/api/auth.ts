import api from "./client";
import type { AuthResponse, User } from "@/types";

export async function loginRequest(username: string, password: string): Promise<AuthResponse> {
  const { data } = await api.post<AuthResponse>("/auth/login/", { username, password });
  return data;
}

export async function fetchMe(): Promise<User> {
  const { data } = await api.get<{ user: User }>("/auth/me/");
  return data.user;
}

export async function logoutRequest(): Promise<void> {
  await api.post("/auth/logout/");
}