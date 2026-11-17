<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Plus,
  Sparkles,
  Megaphone,
  MessagesSquare,
  HardDriveUpload,
  UserCog,
  PanelLeftClose,
  PanelLeftOpen,
  LogIn,
  LogOut,
  X,
  ChevronRight,
  ShieldCheck,
  Circle,
  Sun,
  ListTodo,
  FolderKanban,
  NotebookPen,
  FolderOpen,
  BookOpen,
  Brain,
  Loader2,
  Trash2,
} from "lucide-vue-next";
import BrandMark from "@/components/BrandMark.vue";
import ModalShell from "@/components/ModalShell.vue";
import AnnouncementBody from "@/components/AnnouncementBody.vue";
import { extractApiError } from "@/api/client";
import { useUiStore } from "@/stores/ui";
import { useAuthStore } from "@/stores/auth";
import { useAnnouncementStore } from "@/stores/announcements";
import { useAgentStore } from "@/stores/agent";
import { useToastStore } from "@/stores/toast";
import { formatRelative, initials } from "@/lib/format";

const route = useRoute();
const router = useRouter();
const ui = useUiStore();
const auth = useAuthStore();
const agent = useAgentStore();
const toast = useToastStore();
const announcements = useAnnouncementStore();
const conversationToDelete = ref<{ id: string; title: string } | null>(null);
const deletingConversation = ref(false);
const announcementOpen = ref(false);

const navItems = [
  { path: "/today", label: "今日", caption: "今日安排与待办", icon: Sun, adminOnly: false, chatOnly: false },
  { path: "/tasks", label: "任务", caption: "全部任务与筛选", icon: ListTodo, adminOnly: false, chatOnly: false },
  { path: "/projects", label: "项目", caption: "任务归类", icon: FolderKanban, adminOnly: false, chatOnly: false },
  { path: "/journal", label: "记录", caption: "每日记录", icon: NotebookPen, adminOnly: false, chatOnly: false },
  { path: "/library", label: "资料", caption: "私人资料库", icon: FolderOpen, adminOnly: false, chatOnly: false },
  { path: "/knowledge", label: "知识库", caption: "笔记与可检索资料", icon: BookOpen, adminOnly: false, chatOnly: false },
  { path: "/knowledge/memories", label: "个人记忆", caption: "偏好与长期事实", icon: Brain, adminOnly: false, chatOnly: false },
  { path: "/agent", label: "AI 对话", caption: "多模态智能助手", icon: Sparkles, adminOnly: false, chatOnly: false },
  { path: "/chat", label: "留言板", caption: "留言 · 文件互传", icon: MessagesSquare, adminOnly: false, chatOnly: true },
  { path: "/transfer", label: "文件中转站", caption: "免密上传 · 可见性控制", icon: HardDriveUpload, adminOnly: false, chatOnly: false },
  { path: "/accounts", label: "账号管理", caption: "改密 · 日志 · 仅管理员", icon: UserCog, adminOnly: true, chatOnly: false },
];

// 访客角色只使用免密中转站，工作台与知识库入口全部隐藏。
const guestOnlyPaths = ["/agent", "/today", "/tasks", "/projects", "/journal", "/library", "/knowledge", "/knowledge/memories"];

const visibleNavItems = computed(() =>
  navItems.filter((item) => {
    if (item.adminOnly && !auth.isAdmin) return false;
    if (item.chatOnly && !auth.isChatUser) return false;
    if (auth.isGuest && guestOnlyPaths.includes(item.path)) {
      return false;
    }
    return true;
  }),
);

const collapsed = computed(() => ui.sidebarCollapsed);
const currentPath = computed(() => route.path);
const canUseAgent = computed(
  () => auth.isAuthenticated && !auth.isGuest,
);

function isActive(path: string): boolean {
  return currentPath.value === path;
}

function startNewChat(): void {
  agent.startNew();
  router.push({ name: "agent" });
  ui.closeMobileSidebar();
}

function openConversation(id: string): void {
  router.push({ name: "agent", query: { c: id } });
  ui.closeMobileSidebar();
}

function closeDeleteDialog(): void {
  if (deletingConversation.value) return;
  conversationToDelete.value = null;
}

async function confirmDeleteConversation(): Promise<void> {
  const target = conversationToDelete.value;
  if (!target || deletingConversation.value) return;
  deletingConversation.value = true;
  try {
    await agent.removeConversation(target.id);
    if (route.name === "agent" && route.query.c === target.id) {
      await router.replace({ name: "agent" });
    }
    conversationToDelete.value = null;
    toast.success("对话记录已删除");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    deletingConversation.value = false;
  }
}

function goLogin(): void {
  router.push({ path: "/", query: { redirect: route.fullPath } });
  ui.closeMobileSidebar();
}

// 公告入口每次打开都重新拉取，管理员刚发布的内容无需刷新页面即可看到。
function openAnnouncement(): void {
  announcementOpen.value = true;
  ui.closeMobileSidebar();
  void announcements.load(true);
  void announcements.loadHistory(true).then(() => announcements.markSeen());
}

function logout(): void {
  void auth.logout();
  agent.reset();
  toast.success("已退出登录");
  if (route.meta.requiresAuth) {
    void router.push("/");
  }
}

onMounted(async () => {
  await auth.initialize();
  void announcements.load();
  void announcements.loadHistory();
  if (canUseAgent.value) {
    try {
      await agent.loadConversations(true);
    } catch {
      // The agent can still be used without the history list.
    }
  }
});

watch(
  () => route.path,
  () => {},
);

onBeforeUnmount(() => {});

watch(
  () => auth.user?.username,
  async (next, previous) => {
    if (next === previous) return;
    // The stores are already reset in App.vue, which is mounted in every
    // layout; only the conversation list has to be reloaded here.
    if (!canUseAgent.value) return;
    try {
      await agent.loadConversations(true);
    } catch {
      // Ignore a transient history failure; the view will retry.
    }
  },
);
</script>

<template>
  <Transition name="fade">
    <div
      v-if="ui.sidebarOpen"
      class="fixed inset-0 z-30 bg-black/20 backdrop-blur-[3px] lg:hidden"
      aria-hidden="true"
      @click="ui.closeMobileSidebar()"
    />
  </Transition>

  <aside
    class="fixed inset-y-0 left-0 z-40 flex min-h-0 flex-col border-r bg-white/80 backdrop-blur-xl transition-[transform,width] duration-300 ease-out lg:static lg:z-auto lg:translate-x-0"
    :class="[
      ui.sidebarOpen ? 'translate-x-0 shadow-elevated' : '-translate-x-full',
      collapsed ? 'lg:w-[72px] w-[260px]' : 'lg:w-[260px] w-[260px]',
    ]"
    style="border-color: var(--apple-border)"
  >
    <!-- Brand -->
    <div class="flex h-12 shrink-0 items-center gap-2 px-4" :class="{ 'lg:justify-center lg:px-0': collapsed }">
      <RouterLink
        to="/agent"
        class="flex min-w-0 items-center gap-2 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
        title="zixxx"
      >
        <BrandMark :size="28" />
        <div v-if="!collapsed" class="min-w-0 hidden lg:block">
          <p class="text-[15px] font-semibold leading-5 tracking-tight text-ink-900">zixxx</p>
        </div>
        <div class="min-w-0 lg:hidden">
          <p class="text-[15px] font-semibold leading-5 tracking-tight text-ink-900">zixxx</p>
        </div>
      </RouterLink>
      <button
        type="button"
        class="icon-button ml-auto hidden h-8 w-8 !min-h-0 !min-w-0 lg:flex"
        :title="collapsed ? '展开侧栏' : '收起侧栏'"
        @click="ui.toggleSidebar()"
      >
        <PanelLeftOpen v-if="collapsed" :size="16" />
        <PanelLeftClose v-else :size="16" />
      </button>
      <button
        type="button"
        class="icon-button ml-auto flex h-8 w-8 !min-h-0 !min-w-0 lg:hidden"
        aria-label="关闭导航"
        @click="ui.closeMobileSidebar()"
      >
        <X :size="18" />
      </button>
    </div>

    <!-- New Chat -->
    <div class="px-3" :class="{ 'px-2': collapsed }">
      <button
        type="button"
        class="group flex w-full items-center gap-2 rounded-xl bg-black/[0.03] px-3 py-2.5 text-left text-[13px] font-medium text-ink-800 transition-all duration-200 hover:bg-black/[0.06] active:scale-[0.98]"
        :class="collapsed ? 'justify-center px-0' : ''"
        :title="collapsed ? '新对话' : undefined"
        @click="startNewChat"
      >
        <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-ink-600 transition group-hover:text-accent-500" style="background: var(--apple-blue); color: white; border-radius: 8px;">
          <Plus :size="14" :stroke-width="2.2" />
        </span>
        <span v-if="!collapsed" class="min-w-0 flex-1">新对话</span>
        <span
          v-if="!collapsed"
          class="rounded-md bg-black/[0.04] px-1.5 py-0.5 font-mono text-[10px] text-ink-400"
        >N</span>
      </button>
    </div>

    <div class="sidebar-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain">
    <!-- Nav -->
    <nav class="mt-3 px-3" :class="{ 'px-2': collapsed }">
      <p
        v-if="!collapsed"
        class="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-400"
      >
        空间
      </p>
      <div class="space-y-0.5">
        <RouterLink
          v-for="item in visibleNavItems"
          :key="item.path"
          :to="item.path"
          class="group flex items-center gap-2.5 rounded-xl px-3 py-2 transition-all duration-150"
          :class="[
            isActive(item.path)
              ? 'bg-black/[0.06] text-ink-900 font-medium'
              : 'text-ink-600 hover:bg-black/[0.03] hover:text-ink-900',
            collapsed ? 'justify-center px-0' : '',
          ]"
          :title="collapsed ? item.label : undefined"
        >
          <span
            class="relative flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition"
            :class="isActive(item.path) ? 'text-accent-500' : 'text-ink-500 group-hover:text-ink-700'"
          >
            <component :is="item.icon" :size="17" :stroke-width="1.8" />
          </span>
          <span v-if="!collapsed" class="min-w-0 flex-1">
            <span class="flex items-center gap-1.5 text-[13px] leading-5">
              {{ item.label }}
            </span>
            <span class="block truncate text-[11px] leading-4 text-ink-400">{{ item.caption }}</span>
          </span>
        </RouterLink>

        <!-- 公告入口：当前公告与历史记录都可从这里回看 -->
        <button
          type="button"
          class="group flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-ink-600 transition-all duration-150 hover:bg-black/[0.03] hover:text-ink-900"
          :class="collapsed ? 'justify-center px-0' : ''"
          :title="collapsed ? '公告' : undefined"
          @click="openAnnouncement"
        >
          <span class="relative flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-ink-500 transition group-hover:text-ink-700">
            <Megaphone :size="17" :stroke-width="1.8" />
            <span
              v-if="announcements.hasUnread"
              class="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-rose-500"
              aria-hidden="true"
            />
          </span>
          <span v-if="!collapsed" class="min-w-0 flex-1">
            <span class="flex items-center gap-1.5 text-[13px] leading-5">公告</span>
            <span class="block truncate text-[11px] leading-4 text-ink-400">站点通知与历史公告</span>
          </span>
        </button>
      </div>
    </nav>

    <!-- Recent conversations -->
    <div v-if="!collapsed && canUseAgent" class="mt-4 px-4">
      <div class="mb-2 flex items-center justify-between">
        <p class="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-400">最近对话</p>
        <span v-if="agent.conversations.length" class="text-[11px] tabular-nums text-ink-300">
          {{ agent.conversations.length }}
        </span>
      </div>

      <div class="-mx-1 px-1 pb-3">
        <div v-if="agent.loadingConversations && !agent.conversations.length" class="space-y-1.5 px-1 py-2">
          <div v-for="index in 3" :key="index" class="h-8 animate-pulse rounded-lg bg-black/[0.04]" />
        </div>

        <div v-else-if="!agent.conversations.length" class="px-2 py-5">
          <div class="flex h-8 w-8 items-center justify-center rounded-xl border border-dashed text-ink-300" style="border-color: var(--apple-divider)">
            <Circle :size="12" />
          </div>
          <p class="mt-2.5 text-[12px] leading-5 text-ink-400">
            还没有对话。向 zixxx 提出第一个问题吧。
          </p>
        </div>

        <div
          v-for="conversation in agent.recentConversations"
          :key="conversation.id"
          class="group mb-px flex items-center rounded-lg transition-all duration-150"
          :class="
            route.name === 'agent' && route.query.c === conversation.id
              ? 'bg-black/[0.06] text-ink-900'
              : 'text-ink-600 hover:bg-black/[0.03] hover:text-ink-900'
          "
        >
          <button
            type="button"
            class="flex min-w-0 flex-1 items-start gap-2 rounded-lg px-2 py-1.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            @click="openConversation(conversation.id)"
          >
            <span class="mt-2 h-1 w-1 shrink-0 rounded-full bg-ink-300 transition group-hover:bg-accent-500" />
            <span class="min-w-0 flex-1">
              <span class="block truncate text-[12px] font-medium leading-5">{{ conversation.title }}</span>
              <span class="block truncate text-[10px] leading-4 text-ink-400">
                {{ formatRelative(conversation.updated_at) }}
              </span>
            </span>
          </button>
          <button
            type="button"
            class="mr-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-ink-400 transition hover:bg-rose-50 hover:text-rose-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            :aria-label="`删除对话 ${conversation.title}`"
            :title="`删除对话 ${conversation.title}`"
            @click="conversationToDelete = { id: conversation.id, title: conversation.title }"
          >
            <Trash2 :size="13" />
          </button>
        </div>
      </div>
    </div>
    </div>

    <!-- User / Login -->
    <div class="mt-auto shrink-0 border-t p-3" :class="{ 'px-2': collapsed }" style="border-color: var(--apple-border)">
      <div
        v-if="auth.isAuthenticated && auth.user"
        class="flex items-center gap-2 rounded-xl p-2"
        :class="collapsed ? 'justify-center p-0' : ''"
      >
        <RouterLink
          to="/"
          class="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 text-[11px] font-semibold text-white shadow-sm"
          :title="`${auth.user.username} · 账户`"
        >
          {{ initials(auth.user.username) }}
          <span class="absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full border-[1.5px] border-white bg-green-400" />
        </RouterLink>
        <div v-if="!collapsed" class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5">
            <p class="truncate text-[12px] font-semibold text-ink-800">{{ auth.user.username }}</p>
            <ShieldCheck v-if="auth.isQzx" :size="12" class="text-accent-500" />
          </div>
          <p class="truncate text-[10px] leading-4 text-ink-400">{{ auth.user.role }}</p>
        </div>
        <button
          v-if="!collapsed"
          type="button"
          class="rounded-lg p-1.5 text-ink-400 transition hover:bg-black/[0.04] hover:text-red-500"
          title="退出登录"
          @click="logout"
        >
          <LogOut :size="14" />
        </button>
      </div>

      <button
        v-else
        type="button"
        class="group flex w-full items-center gap-2.5 rounded-xl p-2 text-left transition hover:bg-black/[0.03]"
        :class="collapsed ? 'justify-center p-0' : ''"
        title="登录"
        @click="goLogin"
      >
        <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white" style="background: var(--apple-blue)">
          <LogIn :size="15" />
        </span>
        <span v-if="!collapsed" class="min-w-0 flex-1">
          <span class="block text-[12px] font-semibold text-ink-800">登录专属空间</span>
          <span class="mt-0.5 block truncate text-[10px] text-ink-400">聊天与文件中转站管理</span>
        </span>
        <ChevronRight v-if="!collapsed" :size="14" class="text-ink-300 transition group-hover:translate-x-0.5 group-hover:text-ink-500" />
      </button>
    </div>
  </aside>
  <ModalShell
    :open="Boolean(conversationToDelete)"
    title="删除 AI 对话记录"
    subtitle="删除后无法恢复。"
    max-width="max-w-md"
    @close="closeDeleteDialog"
  >
    <p class="break-words text-sm text-ink-700">{{ conversationToDelete?.title }}</p>
    <template #footer>
      <button type="button" class="btn-secondary" :disabled="deletingConversation" @click="closeDeleteDialog">取消</button>
      <button
        type="button"
        class="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-rose-600 px-4 text-sm font-semibold text-white transition hover:bg-rose-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:ring-offset-2 disabled:opacity-50"
        :disabled="deletingConversation"
        @click="confirmDeleteConversation"
      >
        <Loader2 v-if="deletingConversation" :size="15" class="animate-spin" />
        删除对话
      </button>
    </template>
  </ModalShell>

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
</template>
