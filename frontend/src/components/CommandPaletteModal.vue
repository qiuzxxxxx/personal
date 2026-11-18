<script setup lang="ts">
import { ref, watch } from "vue";
import { useRouter } from "vue-router";
import { FileText, Folder, Layers, ListTodo, Search, Sparkles } from "lucide-vue-next";
import ModalShell from "@/components/ModalShell.vue";
import { searchWorkspace } from "@/api/workspace";
import { useUiStore } from "@/stores/ui";
import type { WorkspaceSearchResults } from "@/types";

const router = useRouter();
const ui = useUiStore();

const keyword = ref("");
const loading = ref(false);
const results = ref<WorkspaceSearchResults | null>(null);
let timer: number | undefined;
let searchSeq = 0;

const groups = [
  { key: "tasks", label: "任务", icon: ListTodo, route: "/tasks" },
  { key: "projects", label: "项目", icon: Folder, route: "/tasks" },
  { key: "notes", label: "笔记", icon: FileText, route: "/knowledge" },
  { key: "materials", label: "资料", icon: Layers, route: "/library" },
  { key: "memories", label: "记忆", icon: Sparkles, route: "/knowledge" },
] as const;

function titleOf(group: string, item: Record<string, unknown>): string {
  if (group === "projects") return String(item.name || "");
  if (group === "memories") return String(item.summary || "");
  return String(item.title || "");
}

function subtitleOf(group: string, item: Record<string, unknown>): string {
  if (group === "tasks") return String(item.project_name || item.status || "");
  if (group === "notes") return String(item.snippet || "");
  if (group === "materials") return `${Math.round(Number(item.file_size || 0) / 1024)} KB`;
  if (group === "memories") return String(item.status || "");
  return String(item.status || "");
}

function itemsOf(group: string): Record<string, unknown>[] {
  if (!results.value) return [];
  return (results.value[group as keyof WorkspaceSearchResults] as Record<string, unknown>[]) || [];
}

function close(): void {
  ui.closeCommandPalette();
  keyword.value = "";
  results.value = null;
}

function go(path: string): void {
  close();
  void router.push(path);
}

watch(keyword, (value) => {
  window.clearTimeout(timer);
  const query = value.trim();
  const seq = ++searchSeq;
  if (!query) {
    results.value = null;
    loading.value = false;
    return;
  }
  loading.value = true;
  timer = window.setTimeout(async () => {
    try {
      const payload = await searchWorkspace(query);
      // 只接受最新一次关键词的响应，避免慢的旧请求覆盖新结果。
      if (seq !== searchSeq) return;
      results.value = payload;
    } catch {
      if (seq !== searchSeq) return;
      results.value = null;
    } finally {
      if (seq === searchSeq) loading.value = false;
    }
  }, 250);
});
</script>

<template>
  <ModalShell
    :open="ui.commandPaletteOpen"
    title="统一搜索"
    subtitle="任务、项目、笔记、资料与记忆"
    max-width="max-w-2xl"
    @close="close"
  >
    <div class="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2">
      <Search :size="16" class="text-slate-400" />
      <input
        v-model="keyword"
        autofocus
        class="min-w-0 flex-1 bg-transparent text-sm text-slate-800 outline-none placeholder:text-slate-400"
        placeholder="输入关键词，例如：408、操作系统、资料..."
      />
      <span v-if="loading" class="text-[11px] text-slate-400">搜索中...</span>
    </div>

    <div class="mt-3 max-h-[55vh] space-y-3 overflow-y-auto">
      <p v-if="!keyword.trim()" class="py-8 text-center text-xs text-slate-400">
        输入关键词开始搜索，结果按任务 / 项目 / 笔记 / 资料 / 记忆分组，每组最多 5 条。
      </p>
      <template v-else-if="results">
        <div v-for="group in groups" :key="group.key">
          <p class="mb-1 flex items-center gap-1.5 text-[11px] font-semibold text-slate-400">
            <component :is="group.icon" :size="12" />
            {{ group.label }}
            <span class="font-normal">({{ itemsOf(group.key).length }})</span>
          </p>
          <button
            v-for="item in itemsOf(group.key)"
            :key="String(item.id)"
            type="button"
            class="mb-1 flex w-full items-start gap-2 rounded-lg border border-slate-100 px-3 py-2 text-left transition hover:border-blue-200 hover:bg-blue-50/50"
            @click="go(String(item.route || group.route))"
          >
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm text-slate-800">{{ titleOf(group.key, item) }}</span>
              <span v-if="subtitleOf(group.key, item)" class="block truncate text-[11px] text-slate-400">
                {{ subtitleOf(group.key, item) }}
              </span>
            </span>
          </button>
          <p v-if="!itemsOf(group.key).length" class="px-3 py-1 text-[11px] text-slate-300">无匹配</p>
        </div>
      </template>
    </div>

    <template #footer>
      <button type="button" class="btn-secondary" @click="close">关闭</button>
    </template>
  </ModalShell>
</template>
