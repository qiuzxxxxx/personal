import api, { requestPath } from "./client";
import type {
  CalendarBlock,
  CalendarMonthPayload,
  CalendarPayload,
  FocusPayload,
  PagedResult,
  TodayPayload,
  TaskPriority,
  TaskStatus,
  WorkspaceJournal,
  WorkspaceProject,
  WorkspaceSearchResults,
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
  estimated_minutes?: number;
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

export interface LibraryFolder {
  id: string;
  name: string;
  position: number;
  version: number;
  material_count: number;
  created_at: string;
  updated_at: string;
}

export interface LibraryMaterial {
  id: string;
  original_name: string;
  extension: string;
  detected_mime: string;
  size_bytes: number;
  sha256: string;
  remark: string;
  source: "desktop" | "qr" | "transfer_copy";
  state: string;
  folder: string | null;
  folder_name: string;
  tags: WorkspaceTag[];
  version: number;
  is_previewable: boolean;
  download_url: string;
  preview_url: string;
  created_at: string;
  updated_at: string;
}

export async function fetchFolders(): Promise<LibraryFolder[]> {
  const { data } = await api.get<PagedResult<LibraryFolder>>("/library/folders/", {
    params: { page_size: 100 },
  });
  return data.results;
}

export async function createFolder(name: string): Promise<LibraryFolder> {
  const { data } = await api.post<LibraryFolder>("/library/folders/", { name });
  return data;
}

export async function deleteFolder(id: string): Promise<LibraryFolder> {
  const { data } = await api.delete<LibraryFolder>(`/library/folders/${id}/`);
  return data;
}

export async function updateFolder(
  id: string,
  payload: { name: string; version: number },
): Promise<LibraryFolder> {
  const { data } = await api.patch<LibraryFolder>(`/library/folders/${id}/`, payload);
  return data;
}

export async function fetchMaterials(query: {
  folder?: string;
  tag?: string;
  type?: string;
  q?: string;
  deleted?: boolean;
  created_after?: string;
  created_before?: string;
  page?: number;
  page_size?: number;
} = {}): Promise<PagedResult<LibraryMaterial>> {
  const params: Record<string, unknown> = {};
  Object.entries(query).forEach(([key, value]) => {
    if (value) params[key] = value;
  });
  const { data } = await api.get<PagedResult<LibraryMaterial>>("/library/materials/", {
    params,
  });
  return data;
}

export async function uploadMaterial(
  file: File,
  options: { folder?: string; remark?: string; tags?: string[]; task?: string } = {},
): Promise<LibraryMaterial> {
  const form = new FormData();
  form.append("file", file);
  if (options.folder) form.append("folder", options.folder);
  if (options.remark) form.append("remark", options.remark);
  if (options.tags?.length) form.append("tags", options.tags.join(","));
  if (options.task) form.append("task", options.task);
  const { data } = await api.post<LibraryMaterial>("/library/materials/", form);
  if (options.task) {
    await api.post(`/tasks/${options.task}/materials/`, { material: data.id });
  }
  return data;
}

export async function deleteMaterial(id: string): Promise<LibraryMaterial> {
  const { data } = await api.delete<LibraryMaterial>(`/library/materials/${id}/`);
  return data;
}

export async function restoreMaterial(id: string): Promise<LibraryMaterial> {
  const { data } = await api.post<LibraryMaterial>(`/library/materials/${id}/restore/`);
  return data;
}

export async function updateMaterial(
  id: string,
  payload: {
    original_name?: string;
    folder?: string | null;
    remark?: string;
    version: number;
  },
): Promise<LibraryMaterial> {
  const { data } = await api.patch<LibraryMaterial>(`/library/materials/${id}/`, payload);
  return data;
}

export async function fetchTaskMaterials(taskId: string): Promise<LibraryMaterial[]> {
  const { data } = await api.get<LibraryMaterial[]>(`/tasks/${taskId}/materials/`);
  return data;
}

export async function attachTaskMaterial(taskId: string, materialId: string): Promise<void> {
  await api.post(`/tasks/${taskId}/materials/`, { material: materialId });
}

export async function detachTaskMaterial(taskId: string, materialId: string): Promise<void> {
  await api.delete(`/tasks/${taskId}/materials/${materialId}/`);
}

export interface WorkspacePreference {
  id: string;
  timezone: string;
  week_starts_on: number;
  default_task_priority: TaskPriority;
}

export async function fetchPreferences(): Promise<WorkspacePreference> {
  const { data } = await api.get<WorkspacePreference>("/workspace/preferences/");
  return data;
}

export async function savePreferences(payload: {
  timezone: string;
  week_starts_on: number;
  default_task_priority: TaskPriority;
}): Promise<WorkspacePreference> {
  const { data } = await api.patch<WorkspacePreference>("/workspace/preferences/", payload);
  return data;
}

export async function fetchCalendar(weekStart?: string): Promise<CalendarPayload> {
  const { data } = await api.get<CalendarPayload>("/workspace/calendar/", {
    params: weekStart ? { week_start: weekStart } : undefined,
  });
  return data;
}

export async function fetchCalendarMonth(month: string): Promise<CalendarMonthPayload> {
  const { data } = await api.get<CalendarMonthPayload>("/workspace/calendar/month/", {
    params: { month },
  });
  return data;
}

export async function createCalendarBlock(payload: {
  task_id?: string | null;
  title?: string;
  block_type?: "task" | "study" | "habit" | "sleep" | "wash";
  day_date: string;
  start_time: string;
  end_time?: string;
  duration_minutes?: number;
}): Promise<CalendarBlock> {
  const { data } = await api.post<CalendarBlock>("/workspace/calendar/blocks/", payload);
  return data;
}

export async function updateCalendarBlock(
  id: string,
  payload: {
    title?: string;
    block_type?: "task" | "study" | "habit" | "sleep" | "wash";
    day_date?: string;
    start_time?: string;
    end_time?: string;
    duration_minutes?: number;
    is_completed?: boolean;
    version: number;
  },
): Promise<CalendarBlock> {
  const { data } = await api.patch<CalendarBlock>(
    `/workspace/calendar/blocks/${id}/`,
    payload,
  );
  return data;
}

export async function deleteCalendarBlock(id: string): Promise<CalendarBlock> {
  const { data } = await api.delete<CalendarBlock>(`/workspace/calendar/blocks/${id}/`);
  return data;
}

export async function fetchFocusStats(): Promise<FocusPayload> {
  const { data } = await api.get<FocusPayload>("/workspace/focus/");
  return data;
}

export async function createFocusSession(payload: {
  task_id?: string | null;
  target_title: string;
  minutes: number;
}): Promise<void> {
  await api.post("/workspace/focus/", payload);
}

export async function searchWorkspace(q: string): Promise<WorkspaceSearchResults> {
  const { data } = await api.get<WorkspaceSearchResults>("/workspace/search/", {
    params: { q },
  });
  return data;
}

export async function downloadMaterial(material: LibraryMaterial): Promise<void> {
  const response = await api.get<Blob>(requestPath(material.download_url), {
    responseType: "blob",
  });
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = material.original_name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

