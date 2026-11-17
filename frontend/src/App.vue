<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Menu, LogIn, LogOut, Megaphone } from "lucide-vue-next";
import Sidebar from "@/components/Sidebar.vue";
import ToastHost from "@/components/ToastHost.vue";
import BrandMark from "@/components/BrandMark.vue";
import SiteFooter from "@/components/SiteFooter.vue";
import ModalShell from "@/components/ModalShell.vue";
import AnnouncementBody from "@/components/AnnouncementBody.vue";
import { useUiStore } from "@/stores/ui";
import { useAnnouncementStore } from "@/stores/announcements";
import { useAuthStore } from "@/stores/auth";
import { useWorkspaceStore } from "@/stores/workspace";
import { useKnowledgeStore } from "@/stores/knowledge";
import { useAgentStore } from "@/stores/agent";
import { useConfigStore } from "@/stores/config";
import { useToastStore } from "@/stores/toast";

const route = useRoute();
const router = useRouter();
const ui = useUiStore();
const auth = useAuthStore();
const announcements = useAnnouncementStore();
const toast = useToastStore();
const workspace = useWorkspaceStore();
const knowledge = useKnowledgeStore();
const agent = useAgentStore();
const configStore = useConfigStore();
const profileMenuOpen = ref(false);
const profileMenuRef = ref<HTMLElement | null>(null);
const announcementOpen = ref(false);

const announcementSummary = computed(() =>
  (announcements.latestCurrent?.content || "").replace(/\s+/g, " "),
);

function refreshAnnouncements(): void {
  void announcements.load(true);
  void announcements.loadHistory(true);
}

function openAnnouncement(): void {
  announcementOpen.value = true;
  announcements.markSeen();
  void announcements.loadHistory(true).then(() => announcements.markSeen());
}

function onAnnouncementVisibilityChange(): void {
  if (!document.hidden) refreshAnnouncements();
}

function onDocumentPointerDown(event: PointerEvent): void {
  if (profileMenuOpen.value && !profileMenuRef.value?.contains(event.target as Node)) {
    profileMenuOpen.value = false;
  }
}

function onDocumentKeyDown(event: KeyboardEvent): void {
  if (event.key === "Escape") profileMenuOpen.value = false;
}

async function logoutFromHeader(): Promise<void> {
  profileMenuOpen.value = false;
  void auth.logout();
  ui.closeMobileSidebar();
  toast.success("已退出登录");
  await router.replace("/");
}

let announcementTimer: number | undefined;

onMounted(() => {
  document.addEventListener("pointerdown", onDocumentPointerDown);
  document.addEventListener("keydown", onDocumentKeyDown);
  document.addEventListener("visibilitychange", onAnnouncementVisibilityChange);
  refreshAnnouncements();
  // 长会话中也能收到新公告提醒，而不是只有刷新页面才更新。
  announcementTimer = window.setInterval(() => {
    if (!document.hidden) refreshAnnouncements();
  }, 120_000);
});
onUnmounted(() => {
  document.removeEventListener("pointerdown", onDocumentPointerDown);
  document.removeEventListener("keydown", onDocumentKeyDown);
  document.removeEventListener("visibilitychange", onAnnouncementVisibilityChange);
  if (announcementTimer) window.clearInterval(announcementTimer);
});

// 未登录访客（免密中转站）不得看到任何功能入口：整体走 bare 布局。
const isBare = computed(() => Boolean(route.meta.bare) || !auth.isAuthenticated);

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
];

// 账号切换时清空工作台缓存，避免上一个账号的任务与记录继续留在内存中。
// 这里必须放在 App.vue：登录页是 bare 布局，Sidebar 不存在，它的 watch 不会
// 触发，新账号会直接读到上一个账号缓存的会话与消息。
watch(
  () => auth.user?.id,
  () => {
    workspace.reset();
    knowledge.reset();
    agent.reset();
    configStore.reset();
  },
);

watch(
  () => route.fullPath,
  () => {
    ui.closeMobileSidebar();
    profileMenuOpen.value = false;
  },
);
</script>

<template>
  <div class="app-frame">
    <Sidebar v-if="!isBare" />

    <div class="app-column">
      <header
        v-if="!isBare"
        class="relative z-30 flex h-12 shrink-0 items-center gap-3 border-b bg-white/80 px-4 backdrop-blur-xl lg:justify-end lg:px-6"
        style="border-color: var(--apple-border)"
      >
        <button
          type="button"
          class="icon-button h-10 w-10 lg:hidden"
          aria-label="打开导航"
          @click="ui.openMobileSidebar()"
        >
          <Menu :size="20" />
        </button>
        <RouterLink to="/today" class="flex items-center gap-2 lg:hidden">
          <BrandMark :size="26" />
          <span class="text-[15px] font-semibold tracking-tight text-ink-900">zixxx</span>
        </RouterLink>

        <!-- 顶部居中公告：有新公告时显示红点与“新”标记 -->
        <button
          v-if="announcements.latestCurrent"
          type="button"
          class="absolute left-1/2 top-1/2 hidden max-w-[46vw] -translate-x-1/2 -translate-y-1/2 items-center gap-2 rounded-full border px-3 py-1.5 text-[11.5px] shadow-sm transition md:flex lg:max-w-[520px]"
          :class="
            announcements.hasUnread
              ? 'border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100'
              : 'border-slate-200 bg-white/80 text-ink-600 hover:border-slate-300 hover:text-ink-800'
          "
          :title="`查看公告：${announcementSummary}`"
          @click="openAnnouncement"
        >
          <span class="relative flex shrink-0 items-center justify-center">
            <Megaphone :size="13" />
            <span
              v-if="announcements.hasUnread"
              class="absolute -right-1 -top-1 h-1.5 w-1.5 rounded-full bg-rose-500"
            />
          </span>
          <span class="min-w-0 truncate">{{ announcementSummary }}</span>
          <span
            v-if="announcements.hasUnread"
            class="shrink-0 rounded-full bg-rose-500 px-1.5 py-0.5 text-[8px] font-semibold leading-none text-white"
          >
            新
          </span>
        </button>

        <div class="ml-auto flex items-center gap-2">
          <button
            v-if="announcements.latestCurrent || announcements.hasHistory"
            type="button"
            class="relative flex h-9 w-9 items-center justify-center rounded-full text-ink-500 transition hover:bg-black/[0.04] hover:text-ink-800 md:hidden"
            aria-label="查看公告"
            @click="openAnnouncement"
          >
            <Megaphone :size="16" />
            <span
              v-if="announcements.hasUnread"
              class="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-rose-500"
            />
          </button>
          <div ref="profileMenuRef" class="relative">
          <RouterLink
            v-if="!auth.isAuthenticated"
            to="/"
            class="inline-flex items-center gap-1.5 rounded-full bg-black/[0.03] px-3.5 py-1.5 text-[13px] font-medium text-ink-700 transition hover:bg-black/[0.06]"
          >
            <LogIn :size="14" />
            登录
          </RouterLink>
          <button
            v-else
            type="button"
            class="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 text-[12px] font-semibold text-white shadow-sm outline-none transition active:scale-95 focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
            :aria-label="`${auth.user?.username || '用户'}的账户菜单`"
            aria-controls="mobile-profile-menu"
            aria-haspopup="menu"
            :aria-expanded="profileMenuOpen"
            @click="profileMenuOpen = !profileMenuOpen"
          >
            {{ (auth.user?.username || "N").slice(0, 1).toUpperCase() }}
          </button>
          <div
            v-if="profileMenuOpen && auth.isAuthenticated"
            id="mobile-profile-menu"
            role="menu"
            class="absolute right-0 top-full z-50 mt-2 w-52 rounded-2xl border bg-white/95 p-1.5 shadow-elevated backdrop-blur-xl"
            style="border-color: var(--apple-border)"
          >
            <div class="border-b px-3 py-2.5" style="border-color: var(--apple-border)">
              <p class="truncate text-[14px] font-semibold text-ink-900">{{ auth.user?.username }}</p>
              <p class="truncate text-[12px] text-ink-500">{{ auth.user?.role }}</p>
            </div>
            <button
              type="button"
              role="menuitem"
              class="mt-1 flex min-h-[44px] w-full items-center gap-2.5 rounded-xl px-3 text-left text-[14px] text-ink-700 outline-none transition hover:bg-black/[0.04] focus-visible:bg-black/[0.04]"
              @click="logoutFromHeader"
            >
              <LogOut :size="16" />
              退出登录
            </button>
          </div>
          </div>
        </div>
      </header>

      <main class="min-h-0 flex-1 overflow-hidden">
        <RouterView v-slot="{ Component }">
          <KeepAlive :include="cachedViews">
            <component :is="Component" />
          </KeepAlive>
        </RouterView>
      </main>

      <SiteFooter v-if="!isBare" />
    </div>

    <ToastHost />

    <ModalShell
      :open="announcementOpen"
      title="公告"
      subtitle="当前公告与历史记录"
      max-width="max-w-xl"
      @close="announcementOpen = false"
    >
      <AnnouncementBody />
      <template #footer>
        <button type="button" class="btn-secondary" @click="announcementOpen = false">
          关闭
        </button>
      </template>
    </ModalShell>
  </div>
</template>
