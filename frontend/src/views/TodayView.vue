<script setup lang="ts">
import { computed, onActivated, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  CalendarDays,
  Check,
  ChevronDown,
  ChevronUp,
  CircleAlert,
  ListTodo,
  NotebookPen,
  Plus,
  Trash2,
} from "lucide-vue-next";
import { extractApiError } from "@/api/client";
import { useToastStore } from "@/stores/toast";
import { newClientRequestId, useWorkspaceStore } from "@/stores/workspace";
import type { WorkspaceTask } from "@/types";

const store = useWorkspaceStore();
const toast = useToastStore();
const router = useRouter();

const draft = ref("");
const submitting = ref(false);
const showUnscheduled = ref(false);
const busyIds = ref<string[]>([]);

const today = computed(() => store.today);
const openTasks = computed(() =>
  (today.value?.tasks || []).filter(
    (task) => task.status === "todo" || task.status === "doing",
  ),
);
const doneTasks = computed(() =>
  (today.value?.tasks || []).filter((task) => task.status === "done"),
);
const unscheduledTasks = computed(() =>
  store.tasks.filter(
    (task) =>
      !task.scheduled_date &&
      (task.status === "todo" || task.status === "doing"),
  ),
);

function isBusy(id: string): boolean {
  return busyIds.value.includes(id);
}

async function refresh(): Promise<void> {
  await store.loadToday();
  if (showUnscheduled.value) {
    await store.loadTasks({ status: ["todo", "doing"] });
  }
}

async function addTask(): Promise<void> {
  const title = draft.value.trim();
  if (!title || submitting.value) return;
  submitting.value = true;
  try {
    await store.addTask({
      title,
      scheduled_date: today.value?.date || null,
      client_request_id: newClientRequestId(),
    });
    draft.value = "";
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    submitting.value = false;
  }
}

async function toggleTask(task: WorkspaceTask): Promise<void> {
  if (isBusy(task.id)) return;
  busyIds.value = [...busyIds.value, task.id];
  const next = task.status === "done" ? "todo" : "done";
  try {
    await store.patchTask(task.id, { status: next, version: task.version });
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    busyIds.value = busyIds.value.filter((id) => id !== task.id);
  }
}

async function moveToToday(task: WorkspaceTask): Promise<void> {
  if (isBusy(task.id)) return;
  busyIds.value = [...busyIds.value, task.id];
  try {
    await store.patchTask(task.id, {
      scheduled_date: today.value?.date || null,
      version: task.version,
    });
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    busyIds.value = busyIds.value.filter((id) => id !== task.id);
  }
}

async function removeTask(task: WorkspaceTask): Promise<void> {
  if (isBusy(task.id)) return;
  busyIds.value = [...busyIds.value, task.id];
  try {
    await store.removeTask(task.id);
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    busyIds.value = busyIds.value.filter((id) => id !== task.id);
  }
}

async function toggleUnscheduled(): Promise<void> {
  showUnscheduled.value = !showUnscheduled.value;
  if (showUnscheduled.value) {
    try {
      await store.loadTasks({ status: ["todo", "doing"] });
    } catch (error) {
      toast.error(extractApiError(error));
    }
  }
}

function openJournal(): void {
  router.push({ path: "/journal", query: { date: today.value?.date } });
}

let timer: number | undefined;

function scheduleRefresh(): void {
  window.clearInterval(timer);
  timer = window.setInterval(() => {
    if (document.visibilityState === "visible") {
      void refresh();
    }
  }, 60000);
}

onMounted(async () => {
  await refresh();
  scheduleRefresh();
});

// KeepAlive 缓存页：任务 version 可能已被日历排期等操作在服务端递增，
// 重新进入时重拉数据，避免点击任务按钮时一直 409“任务已被其他设备修改”。
onActivated(() => {
  void refresh();
});

onUnmounted(() => {
  window.clearInterval(timer);
});
</script>

<template>
  <div class="h-full overflow-y-auto bg-canvas">
    <div class="mx-auto w-full max-w-5xl px-3 py-4 sm:px-6 sm:py-6 lg:py-10">
      <header class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p class="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-400">
            <CalendarDays :size="14" />
            {{ today?.date || "—" }} · {{ today?.weekday || "" }}
          </p>
          <h1 class="mt-2 text-[22px] font-semibold tracking-tight text-ink-900 sm:text-[26px]">今日工作台</h1>
          <p class="mt-1 text-[12.5px] text-ink-400">
            今日完成 {{ today?.completed_today || 0 }} 项 ·
            逾期 {{ today?.overdue_count || 0 }} 项 ·
            待安排 {{ today?.unscheduled_count || 0 }} 项
          </p>
        </div>
        <RouterLink
          to="/journal"
          class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-[12.5px] font-medium text-ink-700 shadow-sm transition hover:border-accent-200 hover:text-ink-900"
        >
          <NotebookPen :size="15" />
          每日记录
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
          placeholder="添加任务，回车即可保存"
          class="min-w-0 flex-1 bg-transparent px-2.5 py-2 text-[14px] text-ink-900 outline-none placeholder:text-ink-300"
        />
        <button
          type="submit"
          :disabled="submitting || !draft.trim()"
          class="inline-flex h-10 items-center gap-1.5 rounded-xl bg-ink-900 px-4 text-[13px] font-medium text-white transition hover:bg-ink-800 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Plus :size="15" />
          添加
        </button>
      </form>

      <section v-if="today?.overdue?.length" class="mt-6 rounded-2xl border border-rose-200 bg-rose-50/60 p-4">
        <h2 class="flex items-center gap-2 text-[13px] font-semibold text-rose-700">
          <CircleAlert :size="15" />
          逾期事项（{{ today.overdue.length }}）
        </h2>
        <ul class="mt-3 space-y-2">
          <li
            v-for="task in today.overdue"
            :key="task.id"
            class="flex items-center gap-3 rounded-xl bg-white/80 px-3 py-2"
          >
            <button
              type="button"
              class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-rose-300 text-transparent transition hover:border-rose-500"
              :aria-label="`完成 ${task.title}`"
              @click="toggleTask(task)"
            >
              <Check :size="12" />
            </button>
            <span class="min-w-0 flex-1 truncate text-[13.5px] text-ink-800">{{ task.title }}</span>
            <span class="shrink-0 text-[11px] text-rose-500">已过期</span>
            <button
              type="button"
              class="shrink-0 text-[11.5px] font-medium text-accent-600 hover:text-accent-700"
              @click="moveToToday(task)"
            >
              移到今天
            </button>
          </li>
        </ul>
      </section>

      <section class="mt-6">
        <h2 class="flex items-center gap-2 text-[13px] font-semibold text-ink-700">
          <ListTodo :size="15" />
          今天安排
          <span class="text-[11.5px] font-normal text-ink-400">{{ openTasks.length }} 项</span>
        </h2>
        <div
          v-if="!openTasks.length"
          class="mt-3 rounded-2xl border border-dashed border-slate-300 bg-white/60 px-4 py-8 text-center text-[13px] text-ink-400"
        >
          今天还没有安排任务，先添加第一条吧。
        </div>
        <ul v-else class="mt-3 space-y-2">
          <li
            v-for="task in openTasks"
            :key="task.id"
            class="group flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-3 shadow-soft transition hover:border-accent-200 sm:px-4"
          >
            <button
              type="button"
              class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-300 text-transparent transition hover:border-accent-500 hover:text-accent-500"
              :aria-label="`完成 ${task.title}`"
              @click="toggleTask(task)"
            >
              <Check :size="12" />
            </button>
            <div class="min-w-0 flex-1">
              <p class="truncate text-[14px] text-ink-900">{{ task.title }}</p>
              <p class="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-ink-400">
                <span v-if="task.project_name">
                  {{ task.project_deleted ? `${task.project_name}（已删除）` : task.project_name }}
                </span>
                <span v-if="task.priority !== 'normal'">
                  {{ task.priority === "high" ? "高优先级" : "低优先级" }}
                </span>
                <span>预计 {{ task.estimated_minutes }} 分钟</span>
                <span v-for="tag in task.tags" :key="tag.id">#{{ tag.name }}</span>
              </p>
            </div>
            <RouterLink
              :to="{ path: '/tasks', query: { edit: task.id } }"
              class="shrink-0 text-[11.5px] font-medium text-ink-400 transition hover:text-accent-600"
            >
              编辑
            </RouterLink>
            <button
              type="button"
              class="shrink-0 text-ink-300 transition hover:text-rose-500"
              :aria-label="`删除 ${task.title}`"
              @click="removeTask(task)"
            >
              <Trash2 :size="15" />
            </button>
          </li>
        </ul>
      </section>

      <section class="mt-6">
        <button
          type="button"
          class="flex w-full items-center gap-2 rounded-2xl border border-slate-200 bg-white/70 px-4 py-3 text-left text-[13px] font-medium text-ink-600 transition hover:border-accent-200"
          @click="toggleUnscheduled"
        >
          <ChevronUp v-if="showUnscheduled" :size="15" />
          <ChevronDown v-else :size="15" />
          待安排任务
          <span class="text-[11.5px] font-normal text-ink-400">
            {{ today?.unscheduled_count || 0 }} 项
          </span>
        </button>
        <ul v-if="showUnscheduled" class="mt-2 space-y-2">
          <li
            v-for="task in unscheduledTasks"
            :key="task.id"
            class="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-3 sm:px-4"
          >
            <div class="min-w-0 flex-1">
              <p class="truncate text-[13.5px] text-ink-800">{{ task.title }}</p>
            </div>
            <button
              type="button"
              class="shrink-0 text-[11.5px] font-medium text-accent-600 hover:text-accent-700"
              @click="moveToToday(task)"
            >
              安排到今天
            </button>
          </li>
        </ul>
      </section>

      <section v-if="doneTasks.length" class="mt-6">
        <h2 class="text-[13px] font-semibold text-ink-700">
          今天已完成
          <span class="text-[11.5px] font-normal text-ink-400">{{ doneTasks.length }} 项</span>
        </h2>
        <ul class="mt-3 space-y-1.5">
          <li
            v-for="task in doneTasks"
            :key="task.id"
            class="flex items-center gap-3 rounded-xl px-3 py-2 text-ink-400"
          >
            <Check :size="14" class="text-emerald-500" />
            <span class="min-w-0 flex-1 truncate text-[13px] line-through">{{ task.title }}</span>
            <button
              type="button"
              class="shrink-0 text-[11.5px] font-medium text-ink-400 hover:text-accent-600"
              @click="toggleTask(task)"
            >
              重新打开
            </button>
          </li>
        </ul>
      </section>

      <section
        v-if="today?.journal"
        class="mt-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-soft"
      >
        <h2 class="text-[13px] font-semibold text-ink-700">今日记录</h2>
        <p class="mt-2 whitespace-pre-wrap text-[13px] leading-6 text-ink-600">
          {{ today.journal.summary || "（还没有内容）" }}
        </p>
        <button
          type="button"
          class="mt-3 text-[11.5px] font-medium text-accent-600 hover:text-accent-700"
          @click="openJournal"
        >
          继续编辑
        </button>
      </section>
    </div>
  </div>
</template>
