<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { BarChart3, Check, Clock, History, Pause, Play, RotateCcw } from "lucide-vue-next";
import { useFocusStore } from "@/stores/focus";
import { useToastStore } from "@/stores/toast";
import { useWorkspaceStore } from "@/stores/workspace";
import { extractApiError } from "@/api/client";

const router = useRouter();
const focus = useFocusStore();
const workspace = useWorkspaceStore();
const toast = useToastStore();

const targetModel = computed({
  get: () => focus.targetTaskId ?? "",
  set: (value: string) => {
    focus.targetTaskId = value || null;
  },
});

async function finish(): Promise<void> {
  try {
    const minutes = await focus.finishAndLog();
    if (minutes > 0) toast.success(`已记录 ${minutes} 分钟专注`);
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

onMounted(() => {
  if (!workspace.tasks.length) {
    void workspace.loadTasks({ status: ["todo", "doing"], page_size: 100 }).catch(() => undefined);
  }
});
</script>

<template>
  <div class="flex shrink-0 flex-wrap items-center gap-2 border-t border-white/80 bg-white/78 px-4 py-2.5 shadow-[0_-4px_24px_-12px_rgba(66,133,244,0.12)] backdrop-blur-xl">
    <div class="flex items-center gap-2">
      <span class="flex items-center gap-1.5 text-xs font-medium text-slate-500">
        <Clock :size="14" />
        专注计时
      </span>
      <span class="gemini-text font-mono text-xl font-bold tabular-nums">
        {{ focus.formattedTime }}
      </span>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-[#4285f4] via-[#9b72cb] to-[#d96570] px-3.5 py-1.5 text-xs font-medium text-white shadow-[0_4px_14px_-3px_rgba(155,114,203,0.45)] transition hover:brightness-105"
        @click="focus.startOrPause()"
      >
        <Pause v-if="focus.running" :size="13" />
        <Play v-else :size="13" />
        {{ focus.running ? "暂停专注" : "开始专注" }}
      </button>
      <button
        v-if="focus.hasElapsed"
        type="button"
        class="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 transition hover:bg-emerald-100"
        @click="finish"
      >
        <Check :size="13" />
        完成记录
      </button>
      <button
        type="button"
        class="inline-flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-600 transition hover:bg-slate-50"
        @click="focus.resetTimer()"
      >
        <RotateCcw :size="13" />
        重置
      </button>
    </div>

    <label class="flex min-w-0 items-center gap-1.5 text-xs text-slate-500">
      专注目标
      <select
        v-model="targetModel"
        class="h-8 max-w-[220px] rounded-lg border border-slate-200 bg-white px-2 text-xs text-slate-700 outline-none focus:border-blue-400"
      >
        <option value="">自由专注</option>
        <option v-for="task in workspace.openTasks" :key="task.id" :value="task.id">
          {{ task.title }}
        </option>
      </select>
    </label>

    <div class="ml-auto flex items-center gap-1">
      <button
        type="button"
        class="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
        @click="router.push('/focus')"
      >
        <BarChart3 :size="14" />
        <span class="hidden sm:inline">专注统计</span>
      </button>
      <button
        type="button"
        class="hidden items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 sm:inline-flex"
        @click="router.push('/focus')"
      >
        <History :size="14" />
        专注记录
      </button>
    </div>
  </div>
</template>
