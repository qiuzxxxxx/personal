<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { CalendarClock, Check, MessageSquare, Sparkles, X } from "lucide-vue-next";
import { fetchAgentSuggestions } from "@/api/agent";
import { extractApiError } from "@/api/client";
import { useAgentStore } from "@/stores/agent";
import { useCalendarStore } from "@/stores/calendar";
import { useReviewsStore } from "@/stores/reviews";
import { useToastStore } from "@/stores/toast";
import { useUiStore } from "@/stores/ui";
import { useWorkspaceStore } from "@/stores/workspace";
import type { AgentSuggestion } from "@/types";

type TabKey = "schedule" | "tasks" | "review" | "chat";

const router = useRouter();
const ui = useUiStore();
const agent = useAgentStore();
const calendar = useCalendarStore();
const reviews = useReviewsStore();
const toast = useToastStore();
const workspace = useWorkspaceStore();

const activeTab = ref<TabKey>("schedule");
const suggestions = ref<AgentSuggestion[]>([]);
const loadingSuggestions = ref(false);
const chatText = ref("");

const tabs: { key: TabKey; label: string }[] = [
  { key: "schedule", label: "日程建议" },
  { key: "tasks", label: "任务提议" },
  { key: "review", label: "复习提醒" },
  { key: "chat", label: "对话" },
];

const longTasks = computed(() =>
  workspace.openTasks.filter((task) => task.estimated_minutes >= 60).slice(0, 4),
);

async function loadSuggestions(): Promise<void> {
  if (loadingSuggestions.value) return;
  loadingSuggestions.value = true;
  try {
    suggestions.value = await fetchAgentSuggestions();
  } catch {
    suggestions.value = [];
  } finally {
    loadingSuggestions.value = false;
  }
}

function preview(suggestion: AgentSuggestion): void {
  calendar.setPreviewSlot({
    day_date: suggestion.day_date,
    start_time: suggestion.start_time,
    title: suggestion.title,
    duration_minutes: suggestion.duration_minutes,
  });
  void router.push("/calendar");
  toast.success("已在日历中预览排期");
}

async function confirm(suggestion: AgentSuggestion): Promise<void> {
  try {
    await calendar.createBlock({
      task_id: suggestion.task_id,
      title: suggestion.title,
      day_date: suggestion.day_date,
      start_time: suggestion.start_time,
      end_time: suggestion.end_time,
    });
    toast.success("已安排到日历");
    // 重拉建议列表：刚创建的日程块已占用该时段，旧建议的时段可能已失效。
    suggestions.value = suggestions.value.filter(
      (item) => item.task_id !== suggestion.task_id,
    );
    void loadSuggestions();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

function openAgent(): void {
  const query = chatText.value.trim() ? { q: chatText.value.trim() } : undefined;
  chatText.value = "";
  void router.push({ path: "/agent", query });
}

onMounted(() => {
  void loadSuggestions();
  void reviews.load().catch(() => undefined);
  if (!workspace.tasks.length) {
    void workspace.loadTasks({ status: ["todo", "doing"], page_size: 100 }).catch(() => undefined);
  }
});
</script>

<template>
  <aside class="flex w-80 max-w-[90vw] shrink-0 flex-col border-l border-white/80 bg-white/78 backdrop-blur-2xl">
    <div class="flex h-12 items-center gap-2 border-b border-slate-100 px-4">
      <Sparkles :size="16" class="text-[#9b72cb]" />
      <span class="gemini-text text-sm font-bold">AI 助手</span>
      <span class="gemini-badge rounded-full px-2 py-0.5 text-[10px] font-medium">DeepSeek 4.1</span>
      <button
        type="button"
        class="ml-auto rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
        aria-label="收起 AI 助手"
        @click="ui.toggleCopilot()"
      >
        <X :size="15" />
      </button>
    </div>

    <div class="grid grid-cols-4 border-b border-slate-100 text-xs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="px-2 py-2.5 transition"
        :class="
          activeTab === tab.key
            ? 'border-b-2 border-[#9b72cb] font-semibold text-[#5348c7]'
            : 'text-slate-500 hover:text-slate-800'
        "
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto p-3">
      <template v-if="activeTab === 'schedule'">
        <div v-if="loadingSuggestions" class="space-y-2">
          <div v-for="index in 2" :key="index" class="h-24 animate-pulse rounded-xl bg-slate-100" />
        </div>
        <div v-else-if="!suggestions.length" class="rounded-xl border border-dashed border-slate-200 p-4 text-xs leading-5 text-slate-400">
          暂无待安排任务。先去「项目与任务」创建几个待办吧。
        </div>
        <div
          v-for="suggestion in suggestions"
          :key="suggestion.task_id"
          class="mb-2 rounded-xl border border-purple-200/70 bg-gradient-to-br from-[#4285f4]/[0.08] via-[#9b72cb]/[0.08] to-[#d96570]/[0.06] p-3 shadow-sm"
        >
          <p class="flex items-center gap-1.5 text-xs font-semibold text-blue-900">
            <CalendarClock :size="13" />
            {{ suggestion.title }}
          </p>
          <p class="mt-1 text-[11px] text-blue-700">
            {{ suggestion.day_date }} · {{ suggestion.start_time }} - {{ suggestion.end_time }}
            （{{ suggestion.duration_minutes }} 分钟）
          </p>
          <div class="mt-2 flex gap-2">
            <button
              type="button"
              class="rounded-lg border border-blue-200 bg-white px-2.5 py-1 text-[11px] text-blue-700 transition hover:bg-blue-50"
              @click="preview(suggestion)"
            >
              预览调整
            </button>
            <button
              type="button"
              class="inline-flex items-center gap-1 rounded-lg bg-gradient-to-r from-[#4285f4] via-[#9b72cb] to-[#d96570] px-2.5 py-1 text-[11px] text-white shadow-sm transition hover:brightness-105"
              @click="confirm(suggestion)"
            >
              <Check :size="11" />
              确认安排
            </button>
          </div>
        </div>
      </template>

      <template v-else-if="activeTab === 'tasks'">
        <p class="mb-2 text-[11px] font-semibold text-slate-400">预计耗时 ≥ 60 分钟的待办</p>
        <div v-if="!longTasks.length" class="rounded-xl border border-dashed border-slate-200 p-4 text-xs text-slate-400">
          暂无长耗时待办。
        </div>
        <div v-for="task in longTasks" :key="task.id" class="mb-2 rounded-xl border border-slate-200 p-3">
          <p class="text-xs font-medium text-slate-800">{{ task.title }}</p>
          <p class="mt-1 text-[11px] text-slate-400">
            预计 {{ task.estimated_minutes }} 分钟 · 建议拆成 2-3 个 25 分钟专注块
          </p>
        </div>
      </template>

      <template v-else-if="activeTab === 'review'">
        <div class="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p class="text-xs font-semibold text-amber-900">今日待复习 {{ reviews.cards.length }} 张</p>
          <p class="mt-1 text-[11px] leading-5 text-amber-700">
            按 SM-2 记忆曲线安排，先完成最短的一组复习。
          </p>
          <button
            type="button"
            class="mt-3 w-full rounded-lg bg-amber-500 py-1.5 text-xs font-medium text-white transition hover:bg-amber-600"
            @click="router.push('/reviews')"
          >
            立即开始 5 分钟复习
          </button>
        </div>
      </template>

      <template v-else>
        <div class="space-y-1.5">
          <button
            v-for="conversation in agent.recentConversations.slice(0, 5)"
            :key="conversation.id"
            type="button"
            class="flex w-full items-center gap-2 rounded-lg border border-slate-100 px-2.5 py-2 text-left text-xs text-slate-600 transition hover:bg-slate-50"
            @click="router.push({ path: '/agent', query: { c: conversation.id } })"
          >
            <MessageSquare :size="13" class="shrink-0 text-slate-400" />
            <span class="min-w-0 flex-1 truncate">{{ conversation.title }}</span>
          </button>
          <p v-if="!agent.recentConversations.length" class="px-1 py-3 text-xs text-slate-400">
            还没有对话记录。
          </p>
        </div>
        <div class="mt-3 flex items-end gap-2">
          <textarea
            v-model="chatText"
            rows="2"
            class="min-h-[44px] flex-1 resize-none rounded-xl border border-slate-200 px-3 py-2 text-xs outline-none focus:border-blue-400"
            placeholder="向 AI 提问..."
            @keydown.enter.exact.prevent="openAgent"
          />
          <button
            type="button"
            class="rounded-lg bg-gradient-to-r from-[#4285f4] via-[#9b72cb] to-[#d96570] px-3 py-2 text-xs font-medium text-white shadow-sm transition hover:brightness-105"
            @click="openAgent"
          >
            发送
          </button>
        </div>
      </template>
    </div>

    <div class="flex items-center gap-2 border-t border-slate-100 p-3">
      <div class="flex-1 rounded-xl bg-slate-50 px-3 py-2 text-[11px] leading-4 text-slate-500">
        需要我继续为你优化本周计划吗？
      </div>
      <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-tr from-[#4285f4] via-[#9b72cb] to-[#d96570] font-mono text-xs font-bold text-white shadow-sm">
        &gt;_
      </div>
    </div>
  </aside>
</template>
