<script setup lang="ts">
import { computed, watch } from "vue";
import { useRoute } from "vue-router";
import { Menu, LogIn } from "lucide-vue-next";
import Sidebar from "@/components/Sidebar.vue";
import ToastHost from "@/components/ToastHost.vue";
import BrandMark from "@/components/BrandMark.vue";
import SiteFooter from "@/components/SiteFooter.vue";
import { useUiStore } from "@/stores/ui";
import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const ui = useUiStore();
const auth = useAuthStore();

// 未登录访客（免密中转站）不得看到任何功能入口：整体走 bare 布局。
const isBare = computed(() => Boolean(route.meta.bare) || !auth.isAuthenticated);

/**
 * Section views are kept alive so switching tabs never remounts them:
 * no skeleton flashes, no list refetches, no WebSocket reconnects.
 */
const cachedViews = [
  "AgentChatView",
  "DirectChatView",
  "TransferStation",
  "AccountsView",
];

watch(
  () => route.fullPath,
  () => ui.closeMobileSidebar(),
);
</script>

<template>
  <div class="app-frame">
    <Sidebar v-if="!isBare" />

    <div class="app-column">
      <header
        v-if="!isBare"
        class="flex h-16 shrink-0 items-center gap-3 border-b border-slate-200/70 bg-white/75 px-4 backdrop-blur-xl lg:hidden"
      >
        <button
          type="button"
          class="icon-button h-10 w-10"
          aria-label="打开导航"
          @click="ui.openMobileSidebar()"
        >
          <Menu :size="20" />
        </button>
        <RouterLink to="/agent" class="flex items-center gap-2.5">
          <BrandMark :size="28" />
          <span class="text-[15px] font-semibold tracking-tight text-ink-900">zixxx</span>
        </RouterLink>
        <div class="ml-auto">
          <RouterLink
            v-if="!auth.isAuthenticated"
            to="/"
            class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-ink-700 shadow-sm"
          >
            <LogIn :size="14" />
            登录
          </RouterLink>
          <RouterLink
            v-else
            to="/"
            class="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-sky-500 text-xs font-semibold text-white shadow-sm"
            :title="auth.user?.username"
          >
            {{ (auth.user?.username || "N").slice(0, 1).toUpperCase() }}
          </RouterLink>
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
  </div>
</template>