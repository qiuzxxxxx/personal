<script setup lang="ts">
import { onMounted, ref } from "vue";
import { Archive, FolderPlus, Pencil, Trash2 } from "lucide-vue-next";
import { extractApiError } from "@/api/client";
import { createProject, deleteProject, updateProject } from "@/api/workspace";
import { useToastStore } from "@/stores/toast";
import { useWorkspaceStore } from "@/stores/workspace";
import type { WorkspaceProject } from "@/types";

const store = useWorkspaceStore();
const toast = useToastStore();

const name = ref("");
const description = ref("");
const busy = ref(false);
const editingId = ref<string | null>(null);
const editName = ref("");
const editDescription = ref("");

async function refresh(): Promise<void> {
  try {
    await store.loadProjects();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function addProject(): Promise<void> {
  const value = name.value.trim();
  if (!value || busy.value) return;
  busy.value = true;
  try {
    await createProject({ name: value, description: description.value.trim() });
    name.value = "";
    description.value = "";
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    busy.value = false;
  }
}

function startEdit(project: WorkspaceProject): void {
  editingId.value = project.id;
  editName.value = project.name;
  editDescription.value = project.description;
}

async function saveEdit(project: WorkspaceProject): Promise<void> {
  if (!editName.value.trim()) {
    toast.error("项目名称不能为空。");
    return;
  }
  busy.value = true;
  try {
    await updateProject(project.id, {
      name: editName.value.trim(),
      description: editDescription.value,
      version: project.version,
    });
    editingId.value = null;
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    busy.value = false;
  }
}

async function toggleArchive(project: WorkspaceProject): Promise<void> {
  try {
    await updateProject(project.id, {
      status: project.status === "active" ? "archived" : "active",
      version: project.version,
    });
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function removeProject(project: WorkspaceProject): Promise<void> {
  try {
    await deleteProject(project.id);
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

onMounted(refresh);
</script>

<template>
  <div class="h-full overflow-y-auto bg-canvas">
    <div class="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6 lg:py-10">
      <header>
        <h1 class="text-[26px] font-semibold tracking-tight text-ink-900">项目</h1>
        <p class="mt-1 text-[12.5px] text-ink-400">
          项目用于归类任务，归档后仍可查询原有任务。
        </p>
      </header>

      <form
        class="mt-6 space-y-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-soft"
        @submit.prevent="addProject"
      >
        <input
          v-model="name"
          type="text"
          maxlength="120"
          placeholder="新建项目名称"
          class="w-full rounded-xl border border-slate-200 px-3 py-2 text-[13.5px] outline-none focus:border-accent-300"
        />
        <div class="flex items-center gap-2">
          <input
            v-model="description"
            type="text"
            maxlength="10000"
            placeholder="项目说明（可选）"
            class="min-w-0 flex-1 rounded-xl border border-slate-200 px-3 py-2 text-[13px] outline-none focus:border-accent-300"
          />
          <button
            type="submit"
            :disabled="busy || !name.trim()"
            class="inline-flex h-10 items-center gap-1.5 rounded-xl bg-ink-900 px-4 text-[13px] font-medium text-white transition hover:bg-ink-800 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <FolderPlus :size="15" />
            添加
          </button>
        </div>
      </form>

      <div
        v-if="!store.projects.length"
        class="mt-6 rounded-2xl border border-dashed border-slate-300 bg-white/60 px-4 py-10 text-center text-[13px] text-ink-400"
      >
        还没有项目。可以先创建「工作台项目」这样的容器。
      </div>

      <ul v-else class="mt-5 space-y-2">
        <li
          v-for="project in store.projects"
          :key="project.id"
          class="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-soft"
        >
          <div class="flex items-center gap-3">
            <div class="min-w-0 flex-1">
              <p class="truncate text-[14px] text-ink-900">
                {{ project.name }}
                <span
                  v-if="project.status === 'archived'"
                  class="ml-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10.5px] text-ink-500"
                >
                  已归档
                </span>
              </p>
              <p class="mt-0.5 text-[11.5px] text-ink-400">
                {{ project.task_count }} 项任务
                <span v-if="project.description"> · {{ project.description }}</span>
              </p>
            </div>
            <RouterLink
              :to="{ path: '/tasks', query: { project: project.id } }"
              class="shrink-0 text-[11.5px] font-medium text-accent-600 hover:text-accent-700"
            >
              查看任务
            </RouterLink>
            <button
              type="button"
              class="shrink-0 text-ink-300 transition hover:text-ink-700"
              title="编辑"
              @click="startEdit(project)"
            >
              <Pencil :size="14" />
            </button>
            <button
              type="button"
              class="shrink-0 text-ink-300 transition hover:text-ink-700"
              :title="project.status === 'active' ? '归档' : '恢复'"
              @click="toggleArchive(project)"
            >
              <Archive :size="14" />
            </button>
            <button
              type="button"
              class="shrink-0 text-ink-300 transition hover:text-rose-500"
              title="删除"
              @click="removeProject(project)"
            >
              <Trash2 :size="14" />
            </button>
          </div>

          <div
            v-if="editingId === project.id"
            class="mt-3 space-y-2 border-t border-slate-100 pt-3"
          >
            <input
              v-model="editName"
              type="text"
              maxlength="120"
              class="w-full rounded-xl border border-slate-200 px-3 py-2 text-[13.5px] outline-none focus:border-accent-300"
            />
            <textarea
              v-model="editDescription"
              rows="2"
              maxlength="10000"
              class="w-full rounded-xl border border-slate-200 px-3 py-2 text-[13px] outline-none focus:border-accent-300"
            />
            <div class="flex justify-end">
              <button
                type="button"
                :disabled="busy"
                class="rounded-lg bg-ink-900 px-3 py-1.5 text-[12px] font-medium text-white transition hover:bg-ink-800 disabled:opacity-50"
                @click="saveEdit(project)"
              >
                保存
              </button>
            </div>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>
