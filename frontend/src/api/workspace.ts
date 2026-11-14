import api from "./client";
import type {
  PagedResult,
  TodayPayload,
  TaskPriority,
  TaskStatus,
  WorkspaceJournal,
  WorkspaceProject,
  WorkspaceTask,
  WorkspaceTag,
} from "@/types";

export interface TaskListQuery {
  scheduled_date?: string;
  status?: TaskStatus[];
  project?: string;
  tag?: string;
  q?: string;
  deleted?: boolean;
  page?: number;
  page_size?: number;
}

export interface TaskWritePayload {
  title?: string;
  description?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  scheduled_date?: string | null;
  due_at?: string | null;
  project?: string | null;
  tags?: string[];
  client_request_id?: string;
  version?: number;
}

export async function fetchToday(date?: string): Promise<TodayPayload> {
  const { data } = await api.get<TodayPayload>("/workspace/today/", {
    params: date ? { date } : undefined,
  });
  return data;
}

export async function fetchTasks(
  query: TaskListQuery = {},
): Promise<PagedResult<WorkspaceTask>> {
  const params: Record<string, unknown> = {};
  if (query.scheduled_date) params.scheduled_date = query.scheduled_date;
  if (query.status?.length) params.status = query.status.join(",");
  if (query.project) params.project = query.project;
  if (query.tag) params.tag = query.tag;
  if (query.q) params.q = query.q;
  if (query.deleted) params.deleted = "true";
  if (query.page) params.page = query.page;
  if (query.page_size) params.page_size = query.page_size;
  const { data } = await api.get<PagedResult<WorkspaceTask>>("/tasks/", { params });
  return data;
}

export async function createTask(payload: TaskWritePayload): Promise<WorkspaceTask> {
  const { data } = await api.post<WorkspaceTask>("/tasks/", payload);
  return data;
}

export async function updateTask(
  id: string,
  payload: TaskWritePayload,
): Promise<WorkspaceTask> {
  const { data } = await api.patch<WorkspaceTask>(`/tasks/${id}/`, payload);
  return data;
}

export async function deleteTask(id: string): Promise<WorkspaceTask> {
  const { data } = await api.delete<WorkspaceTask>(`/tasks/${id}/`);
  return data;
}

export async function restoreTask(id: string): Promise<WorkspaceTask> {
  const { data } = await api.post<WorkspaceTask>(`/tasks/${id}/restore/`);
  return data;
}

export async function reorderTasks(
  items: { id: string; version: number }[],
): Promise<WorkspaceTask[]> {
  const { data } = await api.post<{ results: WorkspaceTask[] }>("/tasks/reorder/", {
    items,
  });
  return data.results;
}

export async function fetchProjects(): Promise<WorkspaceProject[]> {
  const { data } = await api.get<PagedResult<WorkspaceProject>>("/projects/", {
    params: { page_size: 100 },
  });
  return data.results;
}

export async function createProject(payload: {
  name: string;
  description?: string;
  color?: string;
}): Promise<WorkspaceProject> {
  const { data } = await api.post<WorkspaceProject>("/projects/", payload);
  return data;
}

export async function updateProject(
  id: string,
  payload: {
    name?: string;
    description?: string;
    color?: string;
    status?: "active" | "archived";
    version: number;
  },
): Promise<WorkspaceProject> {
  const { data } = await api.patch<WorkspaceProject>(`/projects/${id}/`, payload);
  return data;
}

export async function deleteProject(id: string): Promise<WorkspaceProject> {
  const { data } = await api.delete<WorkspaceProject>(`/projects/${id}/`);
  return data;
}

export async function fetchTags(): Promise<WorkspaceTag[]> {
  const { data } = await api.get<PagedResult<WorkspaceTag>>("/tags/", {
    params: { page_size: 100 },
  });
  return data.results;
}

export async function createTag(payload: {
  name: string;
  color?: string;
}): Promise<WorkspaceTag> {
  const { data } = await api.post<WorkspaceTag>("/tags/", payload);
  return data;
}

export async function fetchJournal(date: string): Promise<WorkspaceJournal> {
  const { data } = await api.get<WorkspaceJournal>(`/journal/${date}/`);
  return data;
}

export async function saveJournal(
  date: string,
  payload: { content: string; version?: number },
): Promise<WorkspaceJournal> {
  const { data } = await api.put<WorkspaceJournal>(`/journal/${date}/`, payload);
  return data;
}
