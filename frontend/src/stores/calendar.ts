import { defineStore } from "pinia";
import { computed, ref } from "vue";
import * as workspaceApi from "@/api/workspace";
import { localDateIso, shiftIsoDays } from "@/lib/format";
import type {
  CalendarBlock,
  CalendarPreviewSlot,
  CalendarSubView,
  WorkspaceTask,
} from "@/types";

export const useCalendarStore = defineStore("calendar", () => {
  const blocks = ref<CalendarBlock[]>([]);
  const monthBlocks = ref<CalendarBlock[]>([]);
  const month = ref("");
  const unscheduledTasks = ref<WorkspaceTask[]>([]);
  const weekStart = ref("");
  const weekEnd = ref("");
  const totalScheduledMinutes = ref(0);
  const subView = ref<CalendarSubView>("week");
  const previewSlot = ref<CalendarPreviewSlot | null>(null);
  const loading = ref(false);

  let sessionEpoch = 0;

  const totalScheduledHours = computed(() => {
    const hours = totalScheduledMinutes.value / 60;
    return Number.isInteger(hours) ? String(hours) : hours.toFixed(1);
  });

  function reset(): void {
    sessionEpoch += 1;
    blocks.value = [];
    monthBlocks.value = [];
    month.value = "";
    unscheduledTasks.value = [];
    weekStart.value = "";
    weekEnd.value = "";
    totalScheduledMinutes.value = 0;
    previewSlot.value = null;
    loading.value = false;
  }

  async function load(anchor?: string): Promise<void> {
    const epoch = sessionEpoch;
    loading.value = true;
    try {
      const payload = await workspaceApi.fetchCalendar(anchor);
      if (epoch !== sessionEpoch) return;
      blocks.value = payload.blocks;
      unscheduledTasks.value = payload.unscheduled_tasks;
      weekStart.value = payload.week_start;
      weekEnd.value = payload.week_end;
      totalScheduledMinutes.value = payload.total_scheduled_minutes;
    } finally {
      if (epoch === sessionEpoch) loading.value = false;
    }
  }

  async function shiftWeek(days: number): Promise<void> {
    const anchor = weekStart.value || localDateIso();
    await load(shiftIsoDays(anchor, days));
  }

  async function loadMonth(monthIso?: string): Promise<void> {
    const epoch = sessionEpoch;
    loading.value = true;
    try {
      const payload = await workspaceApi.fetchCalendarMonth(
        monthIso || month.value || localDateIso().slice(0, 7),
      );
      if (epoch !== sessionEpoch) return;
      month.value = payload.month;
      monthBlocks.value = payload.blocks;
    } finally {
      if (epoch === sessionEpoch) loading.value = false;
    }
  }

  async function createBlock(payload: {
    task_id?: string | null;
    title?: string;
    block_type?: "task" | "study" | "habit" | "sleep" | "wash";
    day_date: string;
    start_time: string;
    end_time?: string;
    duration_minutes?: number;
  }): Promise<CalendarBlock> {
    const block = await workspaceApi.createCalendarBlock(payload);
    previewSlot.value = null;
    await load(weekStart.value || payload.day_date);
    if (month.value) await loadMonth(month.value);
    return block;
  }

  async function toggleBlock(block: CalendarBlock): Promise<void> {
    const updated = await workspaceApi.updateCalendarBlock(block.id, {
      is_completed: !block.is_completed,
      version: block.version,
    });
    blocks.value = blocks.value.map((item) => (item.id === updated.id ? updated : item));
    monthBlocks.value = monthBlocks.value.map((item) =>
      item.id === updated.id ? updated : item,
    );
  }

  async function removeBlock(block: CalendarBlock): Promise<void> {
    await workspaceApi.deleteCalendarBlock(block.id);
    blocks.value = blocks.value.filter((item) => item.id !== block.id);
    monthBlocks.value = monthBlocks.value.filter((item) => item.id !== block.id);
    await load(weekStart.value);
    if (month.value) await loadMonth(month.value);
  }

  function setPreviewSlot(slot: CalendarPreviewSlot | null): void {
    previewSlot.value = slot;
  }

  return {
    blocks,
    monthBlocks,
    month,
    unscheduledTasks,
    weekStart,
    weekEnd,
    totalScheduledMinutes,
    totalScheduledHours,
    subView,
    previewSlot,
    loading,
    load,
    loadMonth,
    shiftWeek,
    createBlock,
    toggleBlock,
    removeBlock,
    setPreviewSlot,
    reset,
  };
});
