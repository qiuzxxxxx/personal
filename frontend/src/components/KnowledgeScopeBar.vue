<script setup lang="ts">
import { computed, ref } from "vue";
import { BookOpen, Brain, ChevronDown, ListTodo, ShieldQuestion } from "lucide-vue-next";
import { useKnowledgeStore } from "@/stores/knowledge";
import type { KnowledgeScope } from "@/types";

const props = defineProps<{ scope: KnowledgeScope }>();
const emit = defineEmits<{ (event: "change", value: KnowledgeScope): void }>();

const knowledge = useKnowledgeStore();
const showPanel = ref(false);

const scopeOptions = computed(() => [
  {
    key: "enabled" as const,
    label: "知识库",
    hint: "检索已允许 AI 使用的笔记与资料",
    icon: BookOpen,
    active: props.scope.enabled,
  },
  {
    key: "use_personal_memory" as const,
    label: "个人记忆",
    hint: "使用你已确认的长期偏好",
    icon: Brain,
    active: props.scope.use_personal_memory,
  },
  {
    key: "use_workspace" as const,
    label: "当前工作台",
    hint: "实时读取今天的任务安排",
    icon: ListTodo,
    active: props.scope.use_workspace,
  },
]);

function toggle(key: "enabled" | "use_personal_memory" | "use_workspace"): void {
  emit("change", { ...props.scope, [key]: !props.scope[key] });
}

function setScope(value: "all" | "collections"): void {
  emit("change", { ...props.scope, scope: value });
}

function toggleCollection(id: string): void {
  const current = props.scope.collection_ids;
  const next = current.includes(id)
    ? current.filter((item) => item !== id)
    : [...current, id];
  emit("change", { ...props.scope, collection_ids: next });
}
</script>

<template>
  <div class="relative">
    <div class="flex flex-wrap items-center gap-1.5">
      <button
        v-for="option in scopeOptions"
        :key="option.key"
        type="button"
        class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium transition"
        :class="
          option.active
            ? 'border-accent-200 bg-accent-50 text-accent-700'
            : 'border-white/80 bg-white/70 text-ink-500 hover:bg-white'
        "
        :title="option.hint"
        @click="toggle(option.key)"
      >
        <component :is="option.icon" :size="12" />
        {{ option.label }}
      </button>

      <button
        v-if="scope.enabled"
        type="button"
        class="inline-flex items-center gap-1 rounded-full border border-white/80 bg-white/70 px-2 py-1 text-[11px] font-medium text-ink-500 transition hover:bg-white"
        title="选择检索范围"
        @click="showPanel = !showPanel"
      >
        {{ scope.scope === "all" ? "全部集合" : `${scope.collection_ids.length} 个集合` }}
        <ChevronDown :size="11" />
      </button>

      <button
        v-if="scope.enabled"
        type="button"
        class="inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[11px] font-medium transition"
        :class="
          scope.strict_sources
            ? 'border-amber-200 bg-amber-50 text-amber-700'
            : 'border-white/80 bg-white/70 text-ink-500 hover:bg-white'
        "
        title="只依据本轮资料作答，资料不足时直接说明"
        @click="emit('change', { ...scope, strict_sources: !scope.strict_sources })"
      >
        <ShieldQuestion :size="12" />
        严格来源
      </button>
    </div>

    <div
      v-if="showPanel"
      class="absolute bottom-full left-0 z-30 mb-2 w-[260px] max-w-[calc(100vw-2rem)] rounded-2xl border border-slate-200 bg-white p-3 shadow-xl"
    >
      <p class="px-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-ink-400">
        检索范围
      </p>
      <div class="mt-2 space-y-1">
        <label class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-[12px] text-ink-600 hover:bg-slate-50">
          <input
            type="radio"
            :checked="scope.scope === 'all'"
            class="accent-ink-900"
            @change="setScope('all')"
          />
          全部已授权集合
        </label>
        <label class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-[12px] text-ink-600 hover:bg-slate-50">
          <input
            type="radio"
            :checked="scope.scope === 'collections'"
            class="accent-ink-900"
            @change="setScope('collections')"
          />
          仅指定集合
        </label>
      </div>
      <div v-if="knowledge.collections.length" class="mt-2 border-t border-slate-100 pt-2">
        <label
          v-for="collection in knowledge.collections"
          :key="collection.id"
          class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-[12px] text-ink-600 hover:bg-slate-50"
        >
          <input
            type="checkbox"
            class="accent-ink-900"
            :checked="scope.collection_ids.includes(collection.id)"
            @change="toggleCollection(collection.id)"
          />
          <span class="truncate">{{ collection.name }}</span>
        </label>
      </div>
      <p v-else class="mt-2 border-t border-slate-100 pt-2 text-[11px] text-ink-400">
        还没有知识集合，先到知识库创建一个。
      </p>
    </div>
  </div>
</template>
