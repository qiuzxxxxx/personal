<script setup lang="ts">
import { computed, watch } from "vue";
import { useRoute } from "vue-router";
import Sidebar from "@/components/Sidebar.vue";
import TopHeader from "@/components/TopHeader.vue";
import GuestTopBar from "@/components/GuestTopBar.vue";
import FocusTimerBar from "@/components/FocusTimerBar.vue";
import AiCopilotDrawer from "@/components/AiCopilotDrawer.vue";
import CommandPaletteModal from "@/components/CommandPaletteModal.vue";
import ToastHost from "@/components/ToastHost.vue";
import { useAuthStore } from "@/stores/auth";
import { useWorkspaceStore } from "@/stores/workspace";
import { useKnowledgeStore } from "@/stores/knowledge";
import { useAgentStore } from "@/stores/agent";
import { useConfigStore } from "@/stores/config";
import { useCalendarStore } from "@/stores/calendar";
import { useFocusStore } from "@/stores/focus";
import { useReviewsStore } from "@/stores/reviews";
import { useUiStore } from "@/stores/ui";

const route = useRoute();
const ui = useUiStore();
const auth = useAuthStore();
const workspace = useWorkspaceStore();
const knowledge = useKnowledgeStore();
const agent = useAgentStore();
const configStore = useConfigStore();
const calendar = useCalendarStore();
const focus = useFocusStore();
const reviews = useReviewsStore();

// 正式工作台外壳只对已登录的非访客账号挂载；登录页、手机上传页与访客
// 中转站走独立裸布局，绝不渲染侧栏、底部专注条与 AI 抽屉。
const isWorkbench = computed(
  () => Boolean(auth.isAuthenticated && !auth.isGuest && !route.meta.bare),
);

// 裸布局下已登录访客按修正 N1 挂载极简顶栏（品牌 + 公告铃铛 + 退出登录），
// 否则访客在 /transfer 没有任何退出登录入口。
const showGuestBar = computed(
  () => Boolean(auth.isAuthenticated && auth.isGuest && !route.meta.bare),
);

/**
 * Section views are kept alive so switching tabs never remounts them:
 * no skeleton flashes, no list refetches, no WebSocket reconnects.
 */
const cachedViews = [
  "TodayView",
  "TasksView",
  "ProjectsView",
  "JournalView",
  "LibraryView",
  "KnowledgeView",
  "KnowledgeMemoriesView",
  "AgentChatView",
  "DirectChatView",
  "TransferStation",
  "AccountsView",
  "CalendarPlanView",
  "FocusStatsView",
  "SpacedRepetitionView",
  "WorkspaceConfigView",
];

// 账号切换时清空工作台缓存，避免上一个账号的任务与记录继续留在内存中。
watch(
  () => auth.user?.id,
  () => {
    workspace.reset();
    knowledge.reset();
    agent.reset();
    configStore.reset();
    calendar.reset();
    focus.reset();
    reviews.reset();
  },
);
</script>

<template>
  <div v-if="isWorkbench" class="relative flex h-screen flex-col overflow-hidden bg-[#f6f8fc]">
    <div class="gemini-global-aura" aria-hidden="true" />
    <TopHeader class="relative z-20" />
    <div class="relative z-10 flex min-h-0 flex-1 overflow-hidden">
      <Sidebar />
      <div class="flex min-w-0 flex-1 flex-col">
        <main class="min-h-0 flex-1 overflow-y-auto">
          <RouterView v-slot="{ Component }">
            <KeepAlive :include="cachedViews">
              <component :is="Component" />
            </KeepAlive>
          </RouterView>
        </main>
        <FocusTimerBar />
      </div>
      <!-- 手机端 Copilot 为覆盖层：补一层遮罩，点击即收起 -->
      <div
        v-if="ui.copilotOpen"
        class="fixed inset-0 z-20 bg-black/20 backdrop-blur-[3px] lg:hidden"
        aria-hidden="true"
        @click="ui.toggleCopilot()"
      />
      <AiCopilotDrawer
        v-show="ui.copilotOpen"
        class="fixed inset-y-0 right-0 z-30 w-80 max-w-[90vw] shadow-2xl xl:static xl:shadow-none"
      />
    </div>
    <CommandPaletteModal v-if="ui.commandPaletteOpen" />
    <ToastHost />
  </div>

  <div v-else class="relative flex h-[100dvh] w-full flex-col overflow-hidden bg-[#f6f8fc]">
    <div class="gemini-global-aura" aria-hidden="true" />
    <GuestTopBar v-if="showGuestBar" class="relative z-20" />
    <div class="relative z-10 min-h-0 flex-1 overflow-y-auto">
      <RouterView />
    </div>
    <ToastHost />
  </div>
</template>
