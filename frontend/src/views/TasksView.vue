<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ArrowDown,
  ArrowUp,
  Check,
  Pencil,
  Plus,
  RotateCcw,
  Search,
  Trash2,
  X,
} from "lucide-vue-next";
import { extractApiError } from "@/api/client";
import { useToastStore } from "@/stores/toast";
import { newClientRequestId, useWorkspaceStore } from "@/stores/workspace";
import type { TaskPriority, TaskStatus, WorkspaceTask } from "@/types";

const store = useWorkspaceStore();
const toast = useToastStore();
const route = useRoute();
const router = useRouter();

type Filter = "all" | TaskStatus | "trash";

const filter = ref<Filter>("all");
const keyword = ref("");
const projectFilter = ref("");
const draft = ref("");
const editingId = ref<string | null>(null);
const editTitle = ref("");
const editDescription = ref("");
const editStatus = ref<TaskStatus>("todo");
const editPriority = ref<TaskPriority>("normal");
const editDate = ref("");
const editProject = ref("");
const busy = ref(false);

const statusOptions: { value: Filter; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "todo", label: "待办" },
  { value: "doing", label: "进行中" },
  { value: "done", label: "已完成" },
  { value: "cancelled", label: "已取消" },
];

const visibleTasks = computed(() => store.tasks);

async function refresh(): Promise<void> {
  try {
    await store.loadTasks({
      status: filter.value === "all" || filter.value === "trash" ? undefined : [filter.value],
      project: projectFilter.value || undefined,
      q: keyword.value.trim() || undefined,
      deleted: filter.value === "trash",
    });
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function addTask(): Promise<void> {
  const title = draft.value.trim();
  if (!title || busy.value) return;
  busy.value = true;
  try {
    await store.addTask({
      title,
      client_request_id: newClientRequestId(),
    });
    draft.value = "";
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    busy.value = false;
  }
}

function startEdit(task: WorkspaceTask): void {
  editingId.value = task.id;
  editTitle.value = task.title;
  editDescription.value = task.description;
  editStatus.value = task.status;
  editPriority.value = task.priority;
  editDate.value = task.scheduled_date || "";
  editProject.value = task.project || "";
}

function cancelEdit(): void {
  editingId.value = null;
}

async function saveEdit(task: WorkspaceTask): Promise<void> {
  if (!editTitle.value.trim()) {
    toast.error("任务标题不能为空。");
    return;
  }
  busy.value = true;
  try {
    await store.patchTask(task.id, {
      title: editTitle.value.trim(),
      description: editDescription.value,
      status: editStatus.value,
      priority: editPriority.value,
      scheduled_date: editDate.value || null,
      project: editProject.value || null,
      version: task.version,
    });
    editingId.value = null;
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    busy.value = false;
  }
}

async function quickStatus(task: WorkspaceTask, status: TaskStatus): Promise<void> {
  try {
    await store.patchTask(task.id, { status, version: task.version });
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function removeTask(task: WorkspaceTask): Promise<void> {
  try {
    await store.removeTask(task.id);
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function restoreTask(task: WorkspaceTask): Promise<void> {
  try {
    await store.restoreTask(task.id);
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function move(task: WorkspaceTask, offset: number): Promise<void> {
  const list = [...visibleTasks.value];
  const index = list.findIndex((item) => item.id === task.id);
  const target = index + offset;
  if (index < 0 || target < 0 || target >= list.length) return;
  list.splice(target, 0, ...list.splice(index, 1));
  try {
    await store.reorderTasks(list.map((item) => ({ id: item.id, version: item.version })));
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

watch(filter, () => void refresh());
watch(projectFilter, () => void refresh());

onMounted(async () => {
  await store.loadProjects();
  await refresh();
  const editId = route.query.edit;
  if (typeof editId === "string" && editId) {
    router.replace({ path: "/tasks" });
    const found = visibleTasks.value.find((item) => item.id === editId);
    if (found) startEdit(found);
  }
});
</script>

<template>
  <div class="h-full overflow-y-auto bg-canvas">
    <div class="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 lg:py-10">
      <header class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 class="text-[26px] font-semibold tracking-tight text-ink-900">全部任务</h1>
          <p class="mt-1 text-[12.5px] text-ink-400">共 {{ store.taskCount }} 条记录</p>
        </div>
        <RouterLink
          to="/today"
          class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-[12.5px] font-medium text-ink-700 shadow-sm transition hover:border-accent-200"
        >
          回到今日
        </RouterLink>
      </header>

      <form
        class="mt-6 flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-soft"
        @submit.prevent="addTask"
      >
        <input
          v-model="draft"
          type="text"
          maxlength="200"
          placeholder="新建任务标题"
          class="min-w-0 flex-1 bg-transparent px-2.5 py-2 text-[14px] text-ink-900 outline-none placeholder:text-ink-300"
        />
        <button
          type="submit"
          :disabled="busy || !draft.trim()"
          class="inline-flex h-10 items-center gap-1.5 rounded-xl bg-ink-900 px-4 text-[13px] font-medium text-white transition hover:bg-ink-800 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Plus :size="15" />
          新建
        </button>
      </form>

      <div class="mt-5 flex flex-wrap items-center gap-2">
        <button
          v-for="option in statusOptions"
          :key="option.value"
          type="button"
          class="rounded-full px-3 py-1.5 text-[12px] font-medium transition"
          :class="
            filter === option.value
              ? 'bg-ink-900 text-white'
              : 'bg-white text-ink-500 hover:bg-slate-100 hover:text-ink-800'
          "
          @click="filter = option.value"
        >
          {{ option.label }}
        </button>
        <button
          type="button"
          class="rounded-full px-3 py-1.5 text-[12px] font-medium transition"
          :class="
            filter === 'trash'
              ? 'bg-rose-600 text-white'
              : 'bg-white text-ink-500 hover:bg-slate-100 hover:text-ink-800'
          "
          @click="filter = 'trash'"
        >
          回收站
        </button>

        <div class="ml-auto flex items-center gap-2">
          <select
            v-model="projectFilter"
            class="rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-[12px] text-ink-600 outline-none"
          >
            <option value="">全部项目</option>
            <option v-for="project in store.projects" :key="project.id" :value="project.id">
              {{ project.name }}
            </option>
          </select>
          <div class="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5">
            <Search :size="14" class="text-ink-300" />
            <input
              v-model="keyword"
              type="search"
              placeholder="搜索标题或描述"
              class="w-40 bg-transparent text-[12.5px] text-ink-800 outline-none placeholder:text-ink-300"
              @keyup.enter="refresh"
            />
          </div>
        </div>
      </div>

      <div
        v-if="!visibleTasks.length"
        class="mt-6 rounded-2xl border border-dashed border-slate-300 bg-white/60 px-4 py-10 text-center text-[13px] text-ink-400"
      >
        没有符合条件的任务。
      </div>

      <ul v-else class="mt-4 space-y-2">
        <li
          v-for="task in visibleTasks"
          :key="task.id"
          class="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-soft"
        >
          <div class="flex items-center gap-3">
            <button
              type="button"
              class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-300 text-transparent transition hover:border-accent-500 hover:text-accent-500"
              :aria-label="`完成 ${task.title}`"
              @click="quickStatus(task, task.status === 'done' ? 'todo' : 'done')"
            >
              <Check :size="12" />
            </button>
            <div class="min-w-0 flex-1">
              <p
                class="truncate text-[14px] text-ink-900"
                :class="task.status === 'done' ? 'line-through text-ink-400' : ''"
              >
                {{ task.title }}
              </p>
              <p class="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-ink-400">
                <span v-if="task.scheduled_date">计划 {{ task.scheduled_date }}</span>
                <span v-if="task.project_name">{{ task.project_name }}</span>
                <span v-if="task.priority !== 'normal'">
                  {{ task.priority === "high" ? "高优先级" : "低优先级" }}
                </span>
                <span v-for="tag in task.tags" :key="tag.id">#{{ tag.name }}</span>
              </p>
            </div>

            <template v-if="filter === 'trash'">
              <button
                type="button"
                class="shrink-0 text-[11.5px] font-medium text-accent-600 hover:text-accent-700"
                @click="restoreTask(task)"
              >
                恢复
              </button>
            </template>
            <template v-else>
              <button
                type="button"
                class="shrink-0 text-ink-300 transition hover:text-ink-700"
                title="上移"
                @click="move(task, -1)"
              >
                <ArrowUp :size="14" />
              </button>
              <button
                type="button"
                class="shrink-0 text-ink-300 transition hover:text-ink-700"
                title="下移"
                @click="move(task, 1)"
              >
                <ArrowDown :size="14" />
              </button>
              <button
                type="button"
                class="shrink-0 text-ink-300 transition hover:text-accent-600"
                title="编辑"
                @click="startEdit(task)"
              >
                <Pencil :size="14" />
              </button>
              <button
                type="button"
                class="shrink-0 text-ink-300 transition hover:text-rose-500"
                title="删除"
                @click="removeTask(task)"
              >
                <Trash2 :size="14" />
              </button>
            </template>
          </div>

          <div
            v-if="editingId === task.id"
            class="mt-3 space-y-2 border-t border-slate-100 pt-3"
          >
            <input
              v-model="editTitle"
              type="text"
              maxlength="200"
              class="w-full rounded-xl border border-slate-200 px-3 py-2 text-[13.5px] outline-none focus:border-accent-300"
            />
            <textarea
              v-model="editDescription"
              rows="3"
              maxlength="20000"
              placeholder="详细描述"
              class="w-full rounded-xl border border-slate-200 px-3 py-2 text-[13px] outline-none focus:border-accent-300"
            />
            <div class="flex flex-wrap items-center gap-2">
              <select
                v-model="editStatus"
                class="rounded-lg border border-slate-200 px-2 py-1.5 text-[12px] outline-none"
              >
                <option value="todo">待办</option>
                <option value="doing">进行中</option>
                <option value="done">已完成</option>
                <option value="cancelled">已取消</option>
              </select>
              <select
                v-model="editPriority"
                class="rounded-lg border border-slate-200 px-2 py-1.5 text-[12px] outline-none"
              >
                <option value="low">低优先级</option>
                <option value="normal">普通</option>
                <option value="high">高优先级</option>
              </select>
              <input
                v-model="editDate"
                type="date"
                class="rounded-lg border border-slate-200 px-2 py-1.5 text-[12px] outline-none"
              />
              <select
                v-model="editProject"
                class="rounded-lg border border-slate-200 px-2 py-1.5 text-[12px] outline-none"
              >
                <option value="">无项目</option>
                <option v-for="project in store.projects" :key="project.id" :value="project.id">
                  {{ project.name }}
                </option>
              </select>
              <div class="ml-auto flex items-center gap-2">
                <button
                  type="button"
                  class="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[12px] text-ink-500 transition hover:bg-slate-100"
                  @click="cancelEdit"
                >
                  <X :size="13" />
                  取消
                </button>
                <button
                  type="button"
                  :disabled="busy"
                  class="inline-flex items-center gap-1 rounded-lg bg-ink-900 px-3 py-1.5 text-[12px] font-medium text-white transition hover:bg-ink-800 disabled:opacity-50"
                  @click="saveEdit(task)"
                >
                  <Check :size="13" />
                  保存
                </button>
              </div>
            </div>
          </div>
        </li>
      </ul>

      <p v-if="filter === 'trash'" class="mt-4 flex items-center gap-1.5 text-[12px] text-ink-400">
        <RotateCcw :size="13" />
        回收站中的任务不会出现在今日清单里，恢复后重新按计划日期显示。
      </p>
    </div>
  </div>
</template>
