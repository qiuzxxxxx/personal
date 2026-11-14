import { defineStore } from "pinia";
import { ref } from "vue";
import * as workspaceApi from "@/api/workspace";
import type { TaskListQuery, TaskWritePayload } from "@/api/workspace";
import { useAuthStore } from "@/stores/auth";
import type {
  TodayPayload,
  WorkspaceJournal,
  WorkspaceProject,
  WorkspaceTask,
  WorkspaceTag,
} from "@/types";

export function newClientRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/**
 * Workspace state is owner scoped: switching accounts clears every cached
 * list so a previous account's data can never be shown to the next one.
 */
export const useWorkspaceStore = defineStore("workspace", () => {
  const auth = useAuthStore();

  const today = ref<TodayPayload | null>(null);
  const tasks = ref<WorkspaceTask[]>([]);
  const taskCount = ref(0);
  const projects = ref<WorkspaceProject[]>([]);
  const tags = ref<WorkspaceTag[]>([]);
  const journal = ref<WorkspaceJournal | null>(null);
  const loading = ref(false);
  const saving = ref(false);

  let ownerId: number | null = null;

  function reset(): void {
    today.value = null;
    tasks.value = [];
    taskCount.value = 0;
    projects.value = [];
    tags.value = [];
    journal.value = null;
    loading.value = false;
    saving.value = false;
  }

  /** Returns false when the active account changed while a request was in flight. */
  function ensureOwner(): boolean {
    const current = auth.user?.id ?? null;
    if (current !== ownerId) {
      reset();
      ownerId = current;
    }
    return current !== null;
  }

  async function loadToday(date?: string): Promise<TodayPayload | null> {
    if (!ensureOwner()) return null;
    loading.value = true;
    try {
      const payload = await workspaceApi.fetchToday(date);
      if (!ensureOwner()) return null;
      today.value = payload;
      return payload;
    } finally {
      loading.value = false;
    }
  }

  async function loadTasks(query: TaskListQuery = {}): Promise<void> {
    if (!ensureOwner()) return;
    loading.value = true;
    try {
      const page = await workspaceApi.fetchTasks(query);
      if (!ensureOwner()) return;
      tasks.value = page.results;
      taskCount.value = page.count;
    } finally {
      loading.value = false;
    }
  }

  async function loadProjects(): Promise<void> {
    if (!ensureOwner()) return;
    const list = await workspaceApi.fetchProjects();
    if (!ensureOwner()) return;
    projects.value = list;
  }

  async function loadTags(): Promise<void> {
    if (!ensureOwner()) return;
    const list = await workspaceApi.fetchTags();
    if (!ensureOwner()) return;
    tags.value = list;
  }

  async function loadJournal(date: string): Promise<WorkspaceJournal | null> {
    if (!ensureOwner()) return null;
    const entry = await workspaceApi.fetchJournal(date);
    if (!ensureOwner()) return null;
    journal.value = entry;
    return entry;
  }

  async function saveJournal(
    date: string,
    content: string,
    version?: number,
  ): Promise<WorkspaceJournal | null> {
    if (!ensureOwner()) return null;
    saving.value = true;
    try {
      const entry = await workspaceApi.saveJournal(date, { content, version });
      if (!ensureOwner()) return null;
      journal.value = entry;
      return entry;
    } finally {
      saving.value = false;
    }
  }

  async function addTask(payload: TaskWritePayload): Promise<WorkspaceTask | null> {
    if (!ensureOwner()) return null;
    const task = await workspaceApi.createTask(payload);
    if (!ensureOwner()) return null;
    tasks.value = [task, ...tasks.value];
    taskCount.value += 1;
    return task;
  }

  async function patchTask(
    id: string,
    payload: TaskWritePayload,
  ): Promise<WorkspaceTask | null> {
    if (!ensureOwner()) return null;
    const task = await workspaceApi.updateTask(id, payload);
    if (!ensureOwner()) return null;
    tasks.value = tasks.value.map((item) => (item.id === task.id ? task : item));
    if (today.value) {
      today.value = {
        ...today.value,
        tasks: today.value.tasks.map((item) => (item.id === task.id ? task : item)),
        overdue: today.value.overdue.map((item) => (item.id === task.id ? task : item)),
      };
    }
    return task;
  }

  async function removeTask(id: string): Promise<void> {
    if (!ensureOwner()) return;
    const task = await workspaceApi.deleteTask(id);
    if (!ensureOwner()) return;
    tasks.value = tasks.value.filter((item) => item.id !== id);
    taskCount.value = Math.max(0, taskCount.value - 1);
    if (today.value) {
      today.value = {
        ...today.value,
        tasks: today.value.tasks.filter((item) => item.id !== id),
        overdue: today.value.overdue.filter((item) => item.id !== id),
      };
    }
    void task;
  }

  async function restoreTask(id: string): Promise<void> {
    if (!ensureOwner()) return;
    await workspaceApi.restoreTask(id);
  }

  async function reorderTasks(
    items: { id: string; version: number }[],
  ): Promise<void> {
    if (!ensureOwner()) return;
    const updated = await workspaceApi.reorderTasks(items);
    if (!ensureOwner()) return;
    const byId = new Map(updated.map((task) => [task.id, task]));
    tasks.value = tasks.value.map((task) => byId.get(task.id) ?? task);
  }

  return {
    today,
    tasks,
    taskCount,
    projects,
    tags,
    journal,
    loading,
    saving,
    reset,
    loadToday,
    loadTasks,
    loadProjects,
    loadTags,
    loadJournal,
    saveJournal,
    addTask,
    patchTask,
    removeTask,
    restoreTask,
    reorderTasks,
  };
});
