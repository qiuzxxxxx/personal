<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Bell,
  Calendar,
  LogOut,
  Menu,
  Search,
  Settings,
  Sparkles,
  UserCog,
} from "lucide-vue-next";
import ModalShell from "@/components/ModalShell.vue";
import AnnouncementBody from "@/components/AnnouncementBody.vue";
import brandMark from "@/assets/brand/zixxx-mark.png";
import { useAnnouncementStore } from "@/stores/announcements";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toast";
import { useUiStore } from "@/stores/ui";

const route = useRoute();
const router = useRouter();
const ui = useUiStore();
const auth = useAuthStore();
const announcements = useAnnouncementStore();
const toast = useToastStore();

const announcementOpen = ref(false);
const profileOpen = ref(false);

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

function onKeydown(event: KeyboardEvent): void {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    ui.openCommandPalette();
  }
  if (event.key === "Escape") profileOpen.value = false;
}

async function logout(): Promise<void> {
  profileOpen.value = false;
  void auth.logout();
  toast.success("已退出登录");
  await router.replace("/");
}

function go(path: string): void {
  profileOpen.value = false;
  void router.push(path);
}

let timer: number | undefined;

function onVisibilityChange(): void {
  // 切回标签页立即刷新公告，不再等最长 2 分钟的定时器。
  if (!document.hidden) refreshAnnouncements();
}

onMounted(() => {
  document.addEventListener("keydown", onKeydown);
  document.addEventListener("visibilitychange", onVisibilityChange);
  refreshAnnouncements();
  timer = window.setInterval(() => {
    if (!document.hidden) refreshAnnouncements();
  }, 120_000);
});

onUnmounted(() => {
  document.removeEventListener("keydown", onKeydown);
  document.removeEventListener("visibilitychange", onVisibilityChange);
  if (timer) window.clearInterval(timer);
});
</script>

<template>
  <header class="flex h-14 shrink-0 items-center gap-3 border-b border-white/80 bg-white/75 px-4 shadow-[0_4px_24px_-12px_rgba(66,133,244,0.12)] backdrop-blur-xl">
    <button
      type="button"
      class="icon-button h-10 w-10 lg:hidden"
      aria-label="打开导航"
      @click="ui.openMobileSidebar()"
    >
      <Menu :size="19" />
    </button>

    <RouterLink to="/today" class="flex shrink-0 items-center gap-2">
      <img
        :src="brandMark"
        alt="缺页中断"
        class="h-8 w-8 rounded-lg object-contain drop-shadow-[0_4px_8px_rgba(59,101,246,0.14)]"
      />
      <span class="gemini-text text-lg font-bold tracking-tight">缺页中断</span>
    </RouterLink>

    <span class="hidden h-4 w-px bg-slate-200 xl:block" />
    <span class="hidden text-xs text-slate-400 xl:inline-block">
      个人生产力 · 学习 · 知识 · AI 工作台
    </span>

    <!-- 手机端空间有限：搜索只留图标按钮，日历/设置快捷入口从侧栏进入 -->
    <button
      type="button"
      class="icon-button mx-auto h-9 w-9 !min-h-0 !min-w-0 sm:hidden"
      aria-label="搜索"
      @click="ui.openCommandPalette()"
    >
      <Search :size="16" />
    </button>
    <button
      type="button"
      class="mx-auto hidden h-9 w-full min-w-0 max-w-xl items-center gap-2 rounded-full border border-indigo-200/60 bg-white/85 px-3.5 text-left text-xs text-slate-500 shadow-[0_2px_14px_-4px_rgba(66,133,244,0.12)] backdrop-blur transition hover:border-purple-300/80 hover:bg-white hover:shadow-[0_6px_20px_-6px_rgba(155,114,203,0.22)] sm:flex"
      @click="ui.openCommandPalette()"
    >
      <Search :size="14" />
      <span class="min-w-0 flex-1 truncate">统一搜索：任务、项目、笔记、资料、对话与记忆...</span>
      <kbd class="rounded border border-slate-300 bg-white px-1.5 py-0.5 text-[10px] text-slate-400">⌘ K</kbd>
    </button>

    <div class="flex shrink-0 items-center gap-1">
      <button
        type="button"
        class="icon-button hidden h-9 w-9 !min-h-0 !min-w-0 sm:flex"
        title="日历与计划"
        @click="go('/calendar')"
      >
        <Calendar :size="17" />
      </button>
      <button
        type="button"
        class="icon-button relative h-9 w-9 !min-h-0 !min-w-0"
        title="公告"
        @click="openAnnouncement"
      >
        <Bell :size="17" />
        <span
          v-if="announcements.hasUnread"
          class="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-gradient-to-r from-[#4285f4] to-[#d96570]"
        />
      </button>
      <button
        type="button"
        class="icon-button hidden h-9 w-9 !min-h-0 !min-w-0 sm:flex"
        title="工作区配置"
        @click="go('/settings')"
      >
        <Settings :size="17" />
      </button>
      <button
        type="button"
        class="gemini-badge ml-1 hidden items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium shadow-sm transition hover:brightness-95 sm:flex"
        @click="ui.toggleCopilot()"
      >
        <Sparkles :size="14" />
        AI 助手
      </button>

      <div class="relative ml-1">
        <button
          type="button"
          class="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-tr from-[#4285f4] via-[#9b72cb] to-[#d96570] text-xs font-semibold text-white shadow-[0_4px_12px_-2px_rgba(155,114,203,0.4)]"
          :title="`${auth.user?.username || '用户'} · ${auth.user?.role || ''}`"
          @click="profileOpen = !profileOpen"
        >
          {{ (auth.user?.username || "Q").slice(0, 1).toUpperCase() }}
        </button>
        <div
          v-if="profileOpen"
          class="absolute right-0 top-full z-50 mt-2 w-48 rounded-xl border border-slate-200 bg-white p-1.5 shadow-lg"
        >
          <div class="border-b border-slate-100 px-3 py-2">
            <p class="truncate text-sm font-semibold text-slate-800">{{ auth.user?.username }}</p>
            <p class="truncate text-xs text-slate-400">{{ auth.user?.role }}</p>
          </div>
          <button
            v-if="auth.isAdmin"
            type="button"
            class="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-50"
            @click="go('/accounts')"
          >
            <UserCog :size="15" />
            账号管理
          </button>
          <button
            type="button"
            class="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-50"
            @click="logout"
          >
            <LogOut :size="15" />
            退出登录
          </button>
        </div>
      </div>
    </div>

    <ModalShell
      :open="announcementOpen"
      title="公告"
      subtitle="当前公告与历史记录"
      max-width="max-w-xl"
      @close="announcementOpen = false"
    >
      <AnnouncementBody />
      <template #footer>
        <button type="button" class="btn-secondary" @click="announcementOpen = false">关闭</button>
      </template>
    </ModalShell>
  </header>
</template>
