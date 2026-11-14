<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Plus,
  Sparkles,
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
} from "lucide-vue-next";
import BrandMark from "@/components/BrandMark.vue";
import { useUiStore } from "@/stores/ui";
import { useAuthStore } from "@/stores/auth";
import { useAgentStore } from "@/stores/agent";
import { useConfigStore } from "@/stores/config";
import { useToastStore } from "@/stores/toast";
import { formatRelative, initials } from "@/lib/format";

const route = useRoute();
const router = useRouter();
const ui = useUiStore();
const auth = useAuthStore();
const agent = useAgentStore();
const configStore = useConfigStore();
const toast = useToastStore();

const navItems = [
  { path: "/agent", label: "AI 对话", caption: "多模态智能助手", icon: Sparkles, adminOnly: false },
  { path: "/chat", label: "双人密聊", caption: "qzx ↔ sqx", icon: MessagesSquare, adminOnly: false },
  { path: "/transfer", label: "文件中转站", caption: "免密上传 · 可见性控制", icon: HardDriveUpload, adminOnly: false },
  { path: "/accounts", label: "账号管理", caption: "改密 · 日志 · 仅管理员", icon: UserCog, adminOnly: true },
];

const visibleNavItems = computed(() =>
  navItems.filter((item) => {
    if (item.adminOnly && !auth.isAdmin) return false;
    // 游客 yk 与 AI 对话、双人密聊完全隔离，入口一并隐藏。
    if (
      auth.user?.username === "yk" &&
      (item.path === "/agent" || item.path === "/chat")
    ) {
      return false;
    }
    return true;
  }),
);

const collapsed = computed(() => ui.sidebarCollapsed);
const currentPath = computed(() => route.path);
const canUseAgent = computed(
  () => auth.isAuthenticated && auth.user?.username !== "yk",
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

function goLogin(): void {
  router.push({ path: "/", query: { redirect: route.fullPath } });
  ui.closeMobileSidebar();
}

async function logout(): Promise<void> {
  await auth.logout();
  agent.reset();
  toast.success("已退出登录");
  if (route.meta.requiresAuth) {
    router.push("/");
  }
}

onMounted(async () => {
  await auth.initialize();
  if (canUseAgent.value) {
    try {
      await agent.loadConversations(true);
    } catch {
      // The agent can still be used without the history list.
    }
  }
});

watch(
  () => auth.user?.username,
  async (next, previous) => {
    if (next === previous) return;
    agent.reset();
    configStore.reset();
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
      class="fixed inset-0 z-30 bg-ink-950/30 backdrop-blur-[2px] lg:hidden"
      aria-hidden="true"
      @click="ui.closeMobileSidebar()"
    />
  </Transition>

  <aside
    class="fixed inset-y-0 left-0 z-40 flex w-[280px] flex-col border-r border-slate-200/70 bg-[#f3f5f8] transition-[transform,width] duration-300 ease-out lg:static lg:z-auto lg:translate-x-0"
    :class="[
      ui.sidebarOpen ? 'translate-x-0 shadow-2xl shadow-slate-900/20' : '-translate-x-full',
      collapsed ? 'lg:w-[88px]' : 'lg:w-[280px]',
    ]"
  >
    <div class="flex h-[74px] shrink-0 items-center gap-2.5 px-4" :class="{ 'lg:px-3': collapsed }">
      <RouterLink
        to="/agent"
        class="flex min-w-0 items-center gap-2.5 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-accent-400"
        title="zixxx"
      >
        <BrandMark :size="31" />
        <div v-if="!collapsed" class="min-w-0">
          <p class="text-[15px] font-semibold leading-5 tracking-tight text-ink-900">zixxx</p>
          <p class="mt-0.5 text-[10px] font-medium uppercase tracking-[0.16em] text-ink-400">Personal AI Space</p>
        </div>
      </RouterLink>
      <button
        type="button"
        class="icon-button ml-auto hidden h-8 w-8 lg:flex"
        :title="collapsed ? '展开侧栏' : '收起侧栏'"
        @click="ui.toggleSidebar()"
      >
        <PanelLeftOpen v-if="collapsed" :size="17" />
        <PanelLeftClose v-else :size="17" />
      </button>
      <button
        type="button"
        class="icon-button ml-auto flex h-8 w-8 lg:hidden"
        aria-label="关闭导航"
        @click="ui.closeMobileSidebar()"
      >
        <X :size="18" />
      </button>
    </div>

    <div class="px-3" :class="{ 'px-2': collapsed }">
      <button
        type="button"
        class="group flex w-full items-center gap-2.5 rounded-2xl border border-slate-200/90 bg-white px-3.5 py-3 text-left text-[13px] font-medium text-ink-800 shadow-sm transition hover:-translate-y-px hover:border-accent-200 hover:shadow-md"
        :class="collapsed ? 'justify-center px-0' : ''"
        :title="collapsed ? '新对话' : undefined"
        @click="startNewChat"
      >
        <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-ink-900 text-white transition group-hover:bg-accent-600">
          <Plus :size="15" :stroke-width="2.2" />
        </span>
        <span v-if="!collapsed" class="min-w-0 flex-1">新对话</span>
        <span
          v-if="!collapsed"
          class="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-ink-400"
        >N</span>
      </button>
    </div>

    <nav class="mt-4 px-3" :class="{ 'px-2': collapsed }">
      <p
        v-if="!collapsed"
        class="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-400"
      >
        空间
      </p>
      <div class="space-y-1">
        <RouterLink
          v-for="item in visibleNavItems"
          :key="item.path"
          :to="item.path"
          class="group flex items-center gap-3 rounded-2xl px-3 py-2.5 transition"
          :class="[
            isActive(item.path)
              ? 'bg-white text-ink-900 shadow-[0_4px_18px_-10px_rgba(15,23,42,.35)]'
              : 'text-ink-600 hover:bg-white/65 hover:text-ink-900',
            collapsed ? 'justify-center px-0' : '',
          ]"
          :title="collapsed ? item.label : undefined"
        >
          <span
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition"
            :class="isActive(item.path) ? 'bg-accent-50 text-accent-600' : 'text-ink-400 group-hover:text-ink-700'"
          >
            <component :is="item.icon" :size="18" :stroke-width="1.9" />
          </span>
          <span v-if="!collapsed" class="min-w-0 flex-1">
            <span class="flex items-center gap-1.5 text-[13.5px] font-medium leading-5">
              {{ item.label }}
            </span>
            <span class="block truncate text-[10.5px] leading-4 text-ink-400">{{ item.caption }}</span>
          </span>
          <ChevronRight
            v-if="!collapsed && isActive(item.path)"
            :size="14"
            class="shrink-0 text-ink-300"
          />
        </RouterLink>
      </div>
    </nav>

    <div v-if="!collapsed && canUseAgent" class="mt-6 flex min-h-0 flex-1 flex-col px-5">
      <div class="mb-2.5 flex items-center justify-between">
        <p class="text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-400">最近对话</p>
        <span v-if="agent.conversations.length" class="text-[10px] tabular-nums text-ink-300">
          {{ agent.conversations.length }}
        </span>
      </div>

      <div class="sidebar-scroll -mx-2 min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        <div v-if="agent.loadingConversations && !agent.conversations.length" class="space-y-2 px-1 py-2">
          <div v-for="index in 3" :key="index" class="h-9 animate-pulse rounded-xl bg-slate-200/60" />
        </div>

        <div v-else-if="!agent.conversations.length" class="px-2 py-6">
          <div class="flex h-9 w-9 items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white/50 text-ink-300">
            <Circle :size="13" />
          </div>
          <p class="mt-3 text-[11.5px] leading-5 text-ink-400">
            还没有对话。向 zixxx 提出第一个问题吧。
          </p>
        </div>

        <button
          v-for="conversation in agent.recentConversations"
          :key="conversation.id"
          type="button"
          class="group mb-0.5 flex w-full items-start gap-2.5 rounded-xl px-2.5 py-2 text-left transition"
          :class="
            route.name === 'agent' && route.query.c === conversation.id
              ? 'bg-white/90 text-ink-900 shadow-sm'
              : 'text-ink-600 hover:bg-white/55 hover:text-ink-900'
          "
          @click="openConversation(conversation.id)"
        >
          <span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-300 transition group-hover:bg-accent-400" />
          <span class="min-w-0 flex-1">
            <span class="block truncate text-[12px] font-medium leading-5">{{ conversation.title }}</span>
            <span class="block truncate text-[10px] leading-4 text-ink-400">
              {{ formatRelative(conversation.updated_at) }}
            </span>
          </span>
        </button>
      </div>
    </div>

    <div class="mt-auto shrink-0 border-t border-slate-200/70 p-3" :class="{ 'px-2': collapsed }">
      <div
        v-if="auth.isAuthenticated && auth.user"
        class="flex items-center gap-2.5 rounded-2xl border border-white/75 bg-white/65 p-2.5"
        :class="collapsed ? 'justify-center border-transparent bg-transparent p-0' : ''"
      >
        <RouterLink
          to="/"
          class="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 via-blue-500 to-cyan-400 text-[12px] font-semibold text-white shadow-sm"
          :title="`${auth.user.username} · 账户`"
        >
          {{ initials(auth.user.username) }}
          <span class="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-emerald-400" />
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
          class="rounded-lg p-1.5 text-ink-400 transition hover:bg-slate-100 hover:text-rose-500"
          title="退出登录"
          @click="logout"
        >
          <LogOut :size="15" />
        </button>
      </div>

      <button
        v-else
        type="button"
        class="group flex w-full items-center gap-3 rounded-2xl border border-slate-200/80 bg-white/70 p-2.5 text-left transition hover:border-accent-200 hover:bg-white"
        :class="collapsed ? 'justify-center border-transparent bg-transparent p-0' : ''"
        title="登录"
        @click="goLogin"
      >
        <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink-900 text-white">
          <LogIn :size="16" />
        </span>
        <span v-if="!collapsed" class="min-w-0 flex-1">
          <span class="block text-[12px] font-semibold text-ink-800">登录专属空间</span>
          <span class="mt-0.5 block truncate text-[10px] text-ink-400">密聊与文件中转站管理</span>
        </span>
        <ChevronRight v-if="!collapsed" :size="14" class="text-ink-300 transition group-hover:translate-x-0.5 group-hover:text-ink-500" />
      </button>

      <p v-if="!collapsed" class="mt-3 px-2 text-center text-[9px] tracking-wide text-ink-300">
        zixxx · SELF-HOSTED
      </p>
    </div>
  </aside>
</template>