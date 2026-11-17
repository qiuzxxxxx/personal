import api from "./client";
import type {
  AccountInfo,
  AccountLockInfo,
  ActivityLogItem,
  MaintenanceStatus,
} from "@/types";

export type AccountAccessLevel = "admin" | "member" | "guest";

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

export async function createAccount(payload: {
  username: string;
  password: string;
  access_level: AccountAccessLevel;
}): Promise<void> {
  await api.post("/auth/users/create/", payload);
}

export async function updateAccountAccess(
  username: string,
  accessLevel: AccountAccessLevel,
): Promise<AccountInfo> {
  const { data } = await api.patch<AccountInfo>(
    `/auth/users/${encodeURIComponent(username)}/`,
    { access_level: accessLevel },
  );
  return data;
}

export async function deleteAccount(username: string): Promise<void> {
  await api.delete(`/auth/users/${encodeURIComponent(username)}/`);
}

export async function updateMaintenance(payload: {
  enabled: boolean;
  reason: string;
}): Promise<MaintenanceStatus> {
  const { data } = await api.post<MaintenanceStatus>(
    "/auth/maintenance/toggle/",
    payload,
  );
  return data;
}

export async function listAccountLocks(): Promise<AccountLockInfo[]> {
  const { data } = await api.get<AccountLockInfo[]>("/auth/maintenance/locks/");
  return data;
}

export async function setAccountLock(payload: {
  username: string;
  locked: boolean;
  reason: string;
}): Promise<{ username: string; locked: boolean; reason: string }> {
  const { data } = await api.post("/auth/maintenance/lock/", payload);
  return data;
}
