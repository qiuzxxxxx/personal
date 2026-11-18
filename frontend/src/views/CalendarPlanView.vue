<script setup lang="ts">
import { computed, onActivated, onMounted, ref, watch } from "vue";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  GripVertical,
  Plus,
  Trash2,
} from "lucide-vue-next";
import ModalShell from "@/components/ModalShell.vue";
import { extractApiError } from "@/api/client";
import * as workspaceApi from "@/api/workspace";
import { localDateIso } from "@/lib/format";
import { useCalendarStore } from "@/stores/calendar";
import { useToastStore } from "@/stores/toast";
import { useWorkspaceStore } from "@/stores/workspace";
import type { CalendarBlock, CalendarSubView, WorkspaceTask } from "@/types";

const calendar = useCalendarStore();
const workspace = useWorkspaceStore();
const toast = useToastStore();

const HOURS = [
  "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
];
// 周一索引的星期名常量；周视图逐格按真实日期取标签，月视图表头按用户
// 偏好 week_starts_on 旋转（0=周日 / 1=周一 / 6=周六，与后端一致）。
const WEEK_LABELS_MONDAY = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const WEEKDAY_LABELS_BY_GETDAY = [
  "周日", "周一", "周二", "周三", "周四", "周五", "周六",
];
const WEEK_LABELS = computed(() => {
  const start = weekStartsOn.value;
  const offset = (start + 6) % 7; // 转成周一索引：周日→6，周一→0，周六→5
  return [...WEEK_LABELS_MONDAY.slice(offset), ...WEEK_LABELS_MONDAY.slice(0, offset)];
});

const draggingTaskId = ref<string | null>(null);
const dropActive = ref("");
const newTaskOpen = ref(false);
const newBlockOpen = ref(false);
const saving = ref(false);

const newTaskTitle = ref("");
const newTaskMinutes = ref(45);
const blockTitle = ref("");
const blockDate = ref("");
const blockStart = ref("14:00");
const blockEnd = ref("15:00");

const todayIso = localDateIso();
const monthCursor = ref(`${todayIso.slice(0, 7)}-01`);
let monthInitialized = false;
const weekStartsOn = ref(1);

watch(
  () => calendar.weekStart,
  (value) => {
    if (value && !monthInitialized) {
      monthCursor.value = `${value.slice(0, 7)}-01`;
      monthInitialized = true;
    }
  },
  { immediate: true },
);

const weekDays = computed(() => {
  const start = calendar.weekStart || todayIso;
  const base = new Date(`${start}T00:00:00`);
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(base);
    date.setDate(base.getDate() + index);
    const iso = localDateIso(date);
    return {
      iso,
      label: WEEKDAY_LABELS_BY_GETDAY[date.getDay()],
      dayNumber: date.getDate(),
      isToday: iso === todayIso,
    };
  });
});

const monthAnchor = computed(() => new Date(`${monthCursor.value}T00:00:00`));
const monthTitle = computed(
  () => `${monthAnchor.value.getFullYear()} 年 ${monthAnchor.value.getMonth() + 1} 月`,
);
const monthCells = computed(() => {
  const first = new Date(monthAnchor.value.getFullYear(), monthAnchor.value.getMonth(), 1);
  // 月视图首列从用户偏好起始日开始（0=周日 / 1=周一 / 6=周六，恰为 getDay 值）。
  const offset = (first.getDay() - weekStartsOn.value + 7) % 7;
  const start = new Date(first);
  start.setDate(first.getDate() - offset);
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(start);
    date.setDate(start.getDate() + index);
    const iso = localDateIso(date);
    return {
      iso,
      dayNumber: date.getDate(),
      inMonth: date.getMonth() === monthAnchor.value.getMonth(),
      isToday: iso === todayIso,
      blocks: calendar.monthBlocks.filter((block) => block.day_date === iso),
    };
  });
});

const sortedBlocks = computed(() =>
  [...calendar.blocks].sort((a, b) =>
    `${a.day_date} ${a.start_time}`.localeCompare(`${b.day_date} ${b.start_time}`),
  ),
);

function blocksAt(iso: string, hour: string): CalendarBlock[] {
  return calendar.blocks.filter(
    (block) => block.day_date === iso && block.start_time.slice(0, 2) === hour,
  );
}

function setSubView(view: CalendarSubView): void {
  calendar.subView = view;
  if (view === "month") void calendar.loadMonth(monthCursor.value);
}

function onDragStart(event: DragEvent, taskId: string): void {
  draggingTaskId.value = taskId;
  event.dataTransfer?.setData("text/plain", taskId);
  if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
}

async function onDrop(iso: string, hour: string, event: DragEvent): Promise<void> {
  event.preventDefault();
  const taskId = event.dataTransfer?.getData("text/plain") || draggingTaskId.value;
  draggingTaskId.value = null;
  dropActive.value = "";
  if (!taskId) return;
  const task = calendar.unscheduledTasks.find((item) => item.id === taskId);
  if (!task) return;
  try {
    await calendar.createBlock({
      task_id: task.id,
      title: task.title,
      day_date: iso,
      start_time: `${hour}:00`,
      duration_minutes: task.estimated_minutes || 45,
    });
    toast.success(`已安排「${task.title}」`);
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function toggleTask(task: WorkspaceTask): Promise<void> {
  try {
    await workspace.patchTask(task.id, {
      status: task.status === "done" ? "todo" : "done",
      version: task.version,
    });
    await calendar.load(calendar.weekStart);
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function toggleBlock(block: CalendarBlock): Promise<void> {
  try {
    await calendar.toggleBlock(block);
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function removeBlock(block: CalendarBlock): Promise<void> {
  try {
    await calendar.removeBlock(block);
    toast.success("日程已删除");
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

function openBlockModal(iso?: string): void {
  blockTitle.value = "";
  blockDate.value = iso || calendar.weekStart || todayIso;
  blockStart.value = "14:00";
  blockEnd.value = "15:00";
  newBlockOpen.value = true;
}

async function submitTask(): Promise<void> {
  const title = newTaskTitle.value.trim();
  if (!title) return;
  saving.value = true;
  try {
    await workspace.addTask({
      title,
      estimated_minutes: Math.max(1, Math.min(720, newTaskMinutes.value || 45)),
      status: "todo",
      client_request_id: crypto.randomUUID?.() || `task-${Date.now()}`,
    });
    await calendar.load(calendar.weekStart);
    newTaskTitle.value = "";
    newTaskMinutes.value = 45;
    newTaskOpen.value = false;
    toast.success("任务已创建");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    saving.value = false;
  }
}

async function submitBlock(): Promise<void> {
  const title = blockTitle.value.trim();
  if (!title) return;
  saving.value = true;
  try {
    await calendar.createBlock({
      title,
      day_date: blockDate.value,
      start_time: blockStart.value,
      end_time: blockEnd.value,
      block_type: "study",
    });
    newBlockOpen.value = false;
    toast.success("日程已添加");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    saving.value = false;
  }
}

async function shiftMonth(delta: number): Promise<void> {
  const target = new Date(monthAnchor.value.getFullYear(), monthAnchor.value.getMonth() + delta, 1);
  monthCursor.value = localDateIso(target);
  await calendar.loadMonth(monthCursor.value);
}

onMounted(() => {
  void calendar.load().catch((error) => toast.error(extractApiError(error)));
  if (calendar.subView === "month") void calendar.loadMonth(monthCursor.value);
  // 周起始日偏好驱动周/月视图表头与月网格起始列。
  void workspaceApi.fetchPreferences()
    .then((preference) => {
      weekStartsOn.value = preference.week_starts_on;
    })
    .catch(() => undefined);
});

// KeepAlive 缓存页：重新进入时重拉，同步其他页面（AI 助手确认安排等）
// 产生的排期变化，并拿到最新的任务 version。
onActivated(() => {
  if (calendar.weekStart) void calendar.load(calendar.weekStart);
  if (calendar.subView === "month") void calendar.loadMonth(monthCursor.value);
});
</script>

<template>
  <div class="space-y-4 p-4 sm:p-5">
    <div class="flex flex-wrap items-center gap-3">
      <div>
        <h1 class="text-lg font-semibold text-slate-900">时间轴计划工作台</h1>
        <p class="text-xs text-slate-400">拖拽待办到日历格子即可排期</p>
      </div>
      <div class="flex rounded-xl border border-slate-200 bg-white p-1">
        <button
          v-for="item in [
            { key: 'week', label: '周视图' },
            { key: 'month', label: '月视图' },
            { key: 'list', label: '列表' },
          ]"
          :key="item.key"
          type="button"
          class="rounded-lg px-3 py-1.5 text-xs transition"
          :class="calendar.subView === item.key ? 'bg-blue-600 text-white' : 'text-slate-500 hover:text-slate-800'"
          @click="setSubView(item.key as CalendarSubView)"
        >
          {{ item.label }}
        </button>
      </div>
      <span class="ml-auto rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] text-slate-500">
        02 / 时间轴计划工作台
      </span>
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12">
      <section class="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm xl:col-span-3">
        <div class="flex items-center gap-2">
          <h2 class="text-sm font-semibold text-slate-800">待安排</h2>
          <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">
            {{ calendar.unscheduledTasks.length }}
          </span>
          <button
            type="button"
            class="ml-auto inline-flex items-center gap-1 rounded-lg bg-blue-600 px-2.5 py-1.5 text-[11px] font-medium text-white transition hover:bg-blue-700"
            @click="newTaskOpen = true"
          >
            <Plus :size="12" />
            新任务
          </button>
        </div>

        <div class="mt-3 space-y-2">
          <div
            v-for="task in calendar.unscheduledTasks"
            :key="task.id"
            draggable="true"
            class="cursor-grab rounded-xl border border-slate-200 bg-white p-2.5 transition hover:border-blue-300 hover:shadow-sm active:cursor-grabbing"
            @dragstart="onDragStart($event, task.id)"
          >
            <div class="flex items-center gap-2">
              <GripVertical :size="13" class="shrink-0 text-slate-300" />
              <input
                type="checkbox"
                class="h-3.5 w-3.5 rounded border-slate-300"
                :checked="task.status === 'done'"
                @click.stop
                @change="toggleTask(task)"
              />
              <p class="min-w-0 flex-1 truncate text-xs font-medium text-slate-800">
                {{ task.title }}
              </p>
            </div>
            <div class="mt-1.5 flex items-center gap-1.5 pl-5">
              <span
                v-if="task.tags.length"
                class="rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] text-blue-600"
              >
                {{ task.tags[0].name }}
              </span>
              <span class="text-[10px] text-slate-400">预计 {{ task.estimated_minutes }} 分钟</span>
            </div>
          </div>

          <div
            v-if="!calendar.unscheduledTasks.length"
            class="rounded-xl border border-dashed border-slate-200 p-4 text-center text-[11px] text-slate-400"
          >
            暂无待安排任务
          </div>
        </div>

        <div class="mt-3 rounded-xl border-2 border-dashed border-blue-200 bg-blue-50/30 p-3 text-center text-[11px] text-blue-500">
          📅 拖入右侧日历格子即可排期
        </div>
      </section>

      <section class="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm xl:col-span-9">
        <div class="flex flex-wrap items-center gap-2">
          <h2 class="text-sm font-semibold text-slate-800">本周计划</h2>
          <span class="text-[11px] text-emerald-600">
            ✓ 本周已安排 {{ calendar.totalScheduledHours }} 小时
          </span>
          <div class="ml-auto flex items-center gap-1">
            <button
              type="button"
              class="rounded-lg border border-slate-200 p-1.5 text-slate-500 transition hover:bg-slate-50"
              title="上一周"
              @click="calendar.shiftWeek(-7)"
            >
              <ChevronLeft :size="14" />
            </button>
            <button
              type="button"
              class="rounded-lg border border-slate-200 px-2 py-1.5 text-[11px] text-slate-500 transition hover:bg-slate-50"
              @click="calendar.load()"
            >
              本周
            </button>
            <button
              type="button"
              class="rounded-lg border border-slate-200 p-1.5 text-slate-500 transition hover:bg-slate-50"
              title="下一周"
              @click="calendar.shiftWeek(7)"
            >
              <ChevronRight :size="14" />
            </button>
            <button
              type="button"
              class="ml-1 inline-flex items-center gap-1 rounded-lg bg-blue-600 px-2.5 py-1.5 text-[11px] font-medium text-white transition hover:bg-blue-700"
              @click="openBlockModal()"
            >
              <Plus :size="12" />
              添加日程
            </button>
          </div>
        </div>

        <div v-if="calendar.subView === 'week'" class="mt-3 overflow-x-auto">
          <div class="min-w-[720px]">
            <div class="grid grid-cols-[56px_repeat(7,minmax(0,1fr))] gap-1">
              <div />
              <div
                v-for="day in weekDays"
                :key="day.iso"
                class="rounded-lg px-1 py-1.5 text-center"
                :class="day.isToday ? 'bg-blue-50/90 text-blue-700' : 'text-slate-500'"
              >
                <p class="text-[11px] font-medium">{{ day.label }}</p>
                <p class="text-[10px] text-slate-400">{{ day.dayNumber }}</p>
              </div>

              <template v-for="hour in HOURS" :key="hour">
                <div class="pt-1 text-right text-[10px] tabular-nums text-slate-400">
                  {{ hour }}:00
                </div>
                <div
                  v-for="day in weekDays"
                  :key="`${day.iso}-${hour}`"
                  class="min-h-[58px] rounded-lg border border-slate-100 bg-slate-50/40 p-1 transition"
                  :class="{
                    'drop-active': dropActive === `${day.iso}-${hour}`,
                    'preview-highlight':
                      calendar.previewSlot?.day_date === day.iso &&
                      calendar.previewSlot?.start_time?.slice(0, 2) === hour,
                  }"
                  @dragover.prevent="dropActive = `${day.iso}-${hour}`"
                  @dragleave="dropActive = ''"
                  @drop="onDrop(day.iso, hour, $event)"
                >
                  <button
                    v-for="block in blocksAt(day.iso, hour)"
                    :key="block.id"
                    type="button"
                    class="group mb-1 block w-full rounded-md border px-1.5 py-1 text-left text-[10px] leading-4 transition"
                    :class="
                      block.is_completed
                        ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                        : 'border-blue-200 bg-blue-100/80 text-blue-950'
                    "
                    @click="toggleBlock(block)"
                  >
                    <span class="flex items-center gap-1">
                      <span>{{ block.is_completed ? "✅" : "🕒" }}</span>
                      <span class="min-w-0 flex-1 truncate">{{ block.title }}</span>
                      <span
                        class="hidden shrink-0 text-slate-400 group-hover:inline"
                        @click.stop="removeBlock(block)"
                      >
                        <Trash2 :size="10" />
                      </span>
                    </span>
                    <span class="block truncate text-[9px] opacity-70">
                      {{ block.start_time }} - {{ block.end_time }}
                    </span>
                  </button>
                  <div
                    v-if="calendar.previewSlot?.day_date === day.iso && calendar.previewSlot?.start_time?.slice(0, 2) === hour"
                    class="rounded-md border border-dashed border-blue-400 bg-blue-50 px-1.5 py-1 text-[10px] text-blue-700"
                  >
                    {{ calendar.previewSlot.title }} · {{ calendar.previewSlot.duration_minutes }} 分钟
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>

        <div v-else-if="calendar.subView === 'month'" class="mt-3">
          <div class="mb-2 flex items-center justify-between">
            <p class="text-xs font-medium text-slate-600">{{ monthTitle }}</p>
            <div class="flex gap-1">
              <button type="button" class="rounded-lg border border-slate-200 p-1.5" @click="shiftMonth(-1)">
                <ChevronLeft :size="13" />
              </button>
              <button type="button" class="rounded-lg border border-slate-200 p-1.5" @click="shiftMonth(1)">
                <ChevronRight :size="13" />
              </button>
            </div>
          </div>
          <div class="grid grid-cols-7 gap-1 text-center text-[10px] text-slate-400">
            <span v-for="label in WEEK_LABELS" :key="label">{{ label }}</span>
          </div>
          <div class="mt-1 grid grid-cols-7 gap-1">
            <div
              v-for="cell in monthCells"
              :key="cell.iso"
              class="min-h-[72px] rounded-lg border p-1"
              :class="
                cell.isToday
                  ? 'border-blue-400 bg-blue-50/50'
                  : cell.inMonth
                    ? 'border-slate-100 bg-white'
                    : 'border-slate-50 bg-slate-50/50 text-slate-300'
              "
            >
              <p class="text-[10px] font-medium">{{ cell.dayNumber }}</p>
              <p
                v-for="block in cell.blocks.slice(0, 2)"
                :key="block.id"
                class="mt-0.5 truncate rounded bg-blue-100/80 px-1 py-0.5 text-[9px] text-blue-900"
              >
                {{ block.start_time }} {{ block.title }}
              </p>
              <p v-if="cell.blocks.length > 2" class="mt-0.5 text-[9px] text-slate-400">
                +{{ cell.blocks.length - 2 }} 项
              </p>
            </div>
          </div>
        </div>

        <div v-else class="mt-3 space-y-1.5">
          <div
            v-for="block in sortedBlocks"
            :key="block.id"
            class="flex items-center gap-2 rounded-xl border border-slate-100 px-3 py-2"
          >
            <input
              type="checkbox"
              :checked="block.is_completed"
              class="h-3.5 w-3.5 rounded border-slate-300"
              @change="toggleBlock(block)"
            />
            <div class="min-w-0 flex-1">
              <p class="truncate text-xs font-medium text-slate-800">{{ block.title }}</p>
              <p class="text-[10px] text-slate-400">
                {{ block.day_date }} · {{ block.start_time }} - {{ block.end_time }}
              </p>
            </div>
            <button
              type="button"
              class="rounded-lg p-1.5 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
              @click="removeBlock(block)"
            >
              <Trash2 :size="13" />
            </button>
          </div>
          <div v-if="!sortedBlocks.length" class="py-8 text-center text-xs text-slate-400">
            本周还没有日程，拖拽左侧任务开始安排。
          </div>
        </div>
      </section>
    </div>

    <ModalShell :open="newTaskOpen" title="新建待办" subtitle="创建后会出现在左侧待安排列表" max-width="max-w-md" @close="newTaskOpen = false">
      <div class="space-y-3">
        <label class="block space-y-1 text-xs text-slate-500">
          任务标题
          <input v-model="newTaskTitle" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400" />
        </label>
        <label class="block space-y-1 text-xs text-slate-500">
          预计分钟
          <input v-model.number="newTaskMinutes" type="number" min="1" max="720" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400" />
        </label>
      </div>
      <template #footer>
        <button type="button" class="btn-secondary" @click="newTaskOpen = false">取消</button>
        <button type="button" class="btn-primary" :disabled="saving" @click="submitTask">创建</button>
      </template>
    </ModalShell>

    <ModalShell :open="newBlockOpen" title="添加日程" subtitle="手动添加一个时间块" max-width="max-w-md" @close="newBlockOpen = false">
      <div class="space-y-3">
        <label class="block space-y-1 text-xs text-slate-500">
          标题
          <input v-model="blockTitle" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400" />
        </label>
        <label class="block space-y-1 text-xs text-slate-500">
          日期
          <input v-model="blockDate" type="date" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400" />
        </label>
        <div class="grid grid-cols-2 gap-2">
          <label class="block space-y-1 text-xs text-slate-500">
            开始
            <input v-model="blockStart" type="time" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400" />
          </label>
          <label class="block space-y-1 text-xs text-slate-500">
            结束
            <input v-model="blockEnd" type="time" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400" />
          </label>
        </div>
      </div>
      <template #footer>
        <button type="button" class="btn-secondary" @click="newBlockOpen = false">取消</button>
        <button type="button" class="btn-primary" :disabled="saving" @click="submitBlock">添加</button>
      </template>
    </ModalShell>
  </div>
</template>
