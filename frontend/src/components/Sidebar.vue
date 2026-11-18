<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import {
  BarChart2,
  BookOpen,
  Calendar,
  CheckSquare,
  Folder,
  Home,
  Layers,
  LayoutGrid,
  MessageSquare,
  Repeat,
  Sparkles,
  Info,
  X,
} from "lucide-vue-next";
import { useUiStore } from "@/stores/ui";

const route = useRoute();
const ui = useUiStore();

const primaryNav = [
  { path: "/today", label: "工作台", icon: Home },
  { path: "/tasks", label: "项目与任务", icon: CheckSquare },
  { path: "/knowledge", label: "知识与记忆", icon: Layers },
  { path: "/library", label: "资料库", icon: Folder },
  { path: "/transfer", label: "文件中转", icon: Repeat },
  { path: "/chat", label: "留言板", icon: MessageSquare },
];

const workspaceNav = [
  { path: "/calendar", label: "日历与计划", icon: Calendar },
  { path: "/focus", label: "专注与统计", icon: BarChart2 },
  { path: "/reviews", label: "间隔复习", icon: BookOpen },
  { path: "/agent", label: "AI 对话", icon: Sparkles },
  { path: "/settings", label: "工作区配置", icon: LayoutGrid },
  { path: "/about", label: "关于", icon: Info },
];

const currentPath = computed(() => route.path);

function isActive(path: string): boolean {
  if (path === "/knowledge") {
    return currentPath.value.startsWith("/knowledge");
  }
  return currentPath.value === path;
}
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
    class="fixed inset-y-0 left-0 z-40 flex min-h-0 w-56 shrink-0 flex-col border-r border-slate-200/80 bg-white transition-transform duration-300 ease-out lg:static lg:z-auto lg:translate-x-0"
    :class="ui.sidebarOpen ? 'translate-x-0 shadow-xl' : '-translate-x-full'"
  >
    <div class="flex h-14 shrink-0 items-center gap-2 px-3">
      <div class="min-w-0 flex-1">
        <p class="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">空间</p>
        <p class="truncate text-sm font-semibold text-slate-800">我的工作区</p>
      </div>
      <button
        type="button"
        class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 lg:hidden"
        aria-label="关闭导航"
        @click="ui.closeMobileSidebar()"
      >
        <X :size="17" />
      </button>
    </div>

    <nav class="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
      <RouterLink
        v-for="item in primaryNav"
        :key="item.path"
        :to="item.path"
        class="group mb-0.5 flex items-center gap-2.5 rounded-xl px-3 py-2 transition"
        :class="
          isActive(item.path)
            ? 'bg-blue-50 font-medium text-blue-700'
            : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'
        "
        @click="ui.closeMobileSidebar()"
      >
        <component
          :is="item.icon"
          :size="17"
          :stroke-width="1.8"
          :class="isActive(item.path) ? 'text-blue-600' : 'text-slate-400'"
        />
        <span class="min-w-0 flex-1 text-[13px]">{{ item.label }}</span>
      </RouterLink>

      <p class="mb-1 mt-4 px-3 text-[11px] font-semibold text-slate-400">我的工作区</p>
      <RouterLink
        v-for="item in workspaceNav"
        :key="item.path"
        :to="item.path"
        class="group mb-0.5 flex items-center gap-2.5 rounded-xl px-3 py-2 transition"
        :class="
          isActive(item.path)
            ? 'bg-blue-50 font-medium text-blue-700'
            : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'
        "
        @click="ui.closeMobileSidebar()"
      >
        <component
          :is="item.icon"
          :size="17"
          :stroke-width="1.8"
          :class="isActive(item.path) ? 'text-blue-600' : 'text-slate-400'"
        />
        <span class="min-w-0 flex-1 text-[13px]">{{ item.label }}</span>
      </RouterLink>
    </nav>

    <div class="shrink-0 border-t border-slate-100 p-3">
      <div class="flex items-center gap-2.5 rounded-xl bg-slate-50 p-2.5">
        <span class="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
          <Layers :size="16" />
        </span>
        <div class="min-w-0">
          <p class="truncate text-xs font-semibold text-slate-800">我的工作区</p>
          <p class="truncate text-[10px] text-slate-400">学习 · 科研 · 项目</p>
        </div>
      </div>
    </div>
  </aside>
</template>
