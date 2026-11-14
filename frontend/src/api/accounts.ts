import api from "./client";
import type { AccountInfo, ActivityLogItem } from "@/types";

export async function listAccounts(): Promise<AccountInfo[]> {
  const { data } = await api.get<AccountInfo[]>("/auth/users/");
  return data;
}

export async function fetchLogs(
  username?: string,
  limit = 200,
): Promise<ActivityLogItem[]> {
  const { data } = await api.get<ActivityLogItem[]>("/auth/logs/", {
    params: { username, limit },
  });
  return data;
}

export async function changeAccountPassword(
  username: string,
  newPassword: string,
): Promise<{ detail: string }> {
  const { data } = await api.post<{ detail: string }>(
    `/auth/${encodeURIComponent(username)}/password/`,
    { new_password: newPassword },
  );
  return data;
}