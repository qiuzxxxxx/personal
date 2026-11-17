<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  Brain,
  Check,
  CircleSlash,
  Eraser,
  Loader2,
  Plus,
  Save,
  Sparkles,
  Trash2,
  X,
} from "lucide-vue-next";
import ModalShell from "@/components/ModalShell.vue";
import { extractApiError } from "@/api/client";
import {
  acceptMemory,
  createMemory,
  deleteMemory,
  disableMemory,
  forgetMemory,
  updateMemory,
} from "@/api/knowledge";
import type { MemoryStatus, PersonalMemory } from "@/api/knowledge";
import { useToastStore } from "@/stores/toast";
import { useKnowledgeStore } from "@/stores/knowledge";
import { useWorkspaceStore } from "@/stores/workspace";

const router = useRouter();
const toast = useToastStore();
const knowledge = useKnowledgeStore();
const workspace = useWorkspaceStore();

const statusFilter = ref<MemoryStatus | "">("");
const showCreate = ref(false);
const draftKey = ref("");
const draftContent = ref("");
const draftKind = ref<"fact" | "preference" | "goal">("preference");
const draftScope = ref<"global" | "project">("global");
const draftProject = ref("");
const editing = ref<PersonalMemory | null>(null);
const editContent = ref("");
const busyId = ref("");
const pendingDelete = ref<PersonalMemory | null>(null);
const page = ref(1);

const statusLabels: Record<string, string> = {
  suggested: "候选",
  active: "已启用",
  disabled: "已停用",
  superseded: "已被替代",
  forgotten: "已忘记",
};

const statusClasses: Record<string, string> = {
  suggested: "bg-amber-50 text-amber-600",
  active: "bg-emerald-50 text-emerald-600",
  disabled: "bg-slate-100 text-ink-500",
  superseded: "bg-slate-100 text-ink-500",
  forgotten: "bg-rose-50 text-rose-500",
};

const kindLabels: Record<string, string> = {
  fact: "事实",
  preference: "偏好",
  goal: "目标",
};

const visibleMemories = computed(() => knowledge.memories);

async function refresh(): Promise<void> {
  await knowledge.loadMemories(statusFilter.value || undefined, page.value);
}

async function changePage(next: number): Promise<void> {
  page.value = Math.min(Math.max(1, next), Math.max(1, knowledge.memoryPages));
  await refresh();
}

async function submitCreate(): Promise<void> {
  const key = draftKey.value.trim();
  const content = draftContent.value.trim();
  if (!key || !content) {
    toast.error("请填写标识和内容。");
    return;
  }
  try {
    await createMemory({
      key,
      content,
      kind: draftKind.value,
      scope_type: draftScope.value,
      project: draftScope.value === "project" ? draftProject.value || null : null,
      evidence_type: "user_explicit",
    });
    toast.success("记忆已保存。");
    showCreate.value = false;
    draftKey.value = "";
    draftContent.value = "";
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

function startEdit(memory: PersonalMemory): void {
  editing.value = memory;
  editContent.value = memory.content;
}

async function saveEdit(): Promise<void> {
  if (!editing.value) return;
  try {
    await updateMemory(editing.value.id, {
      content: editContent.value,
      version: editing.value.version,
    });
    toast.success("记忆已更新。");
    editing.value = null;
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function runAction(
  memory: PersonalMemory,
  action: "accept" | "disable" | "forget",
): Promise<void> {
  busyId.value = memory.id;
  try {
    if (action === "accept") {
      await acceptMemory(memory.id, memory.version);
    } else if (action === "disable") {
      await disableMemory(memory.id, memory.version);
    } else {
      await forgetMemory(memory.id, memory.version);
    }
    toast.success(
      action === "accept" ? "记忆已启用。" : action === "disable" ? "记忆已停用。" : "记忆已忘记。",
    );
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    busyId.value = "";
  }
}

function askDelete(memory: PersonalMemory): void {
  pendingDelete.value = memory;
}

function closeDelete(): void {
  if (pendingDelete.value && busyId.value === pendingDelete.value.id) return;
  pendingDelete.value = null;
}

async function confirmDelete(): Promise<void> {
  const target = pendingDelete.value;
  if (!target || busyId.value) return;
  busyId.value = target.id;
  try {
    await deleteMemory(target.id, target.version);
    knowledge.memories = knowledge.memories.filter((memory) => memory.id !== target.id);
    if (editing.value?.id === target.id) editing.value = null;
    pendingDelete.value = null;
    toast.success("记忆及其记录已彻底删除。");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    busyId.value = "";
  }
}

onMounted(async () => {
  await workspace.loadProjects();
  await refresh();
});
</script>

<template>
  <div class="h-full overflow-y-auto bg-canvas">
    <div class="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6 lg:py-10">
      <header class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 class="text-[26px] font-semibold tracking-tight text-ink-900">个人记忆</h1>
          <p class="mt-1 text-[12.5px] text-ink-400">
            只有你确认过的条目会作为背景提供给 AI，随时可以修改、停用、忘记或彻底删除。
          </p>
        </div>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="inline-flex h-10 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 text-[12.5px] font-medium text-ink-700 shadow-sm transition hover:border-accent-200"
            @click="router.push('/knowledge')"
          >
            <Sparkles :size="15" />
            知识库
          </button>
          <button
            type="button"
            class="inline-flex h-10 items-center gap-1.5 rounded-xl bg-ink-900 px-4 text-[13px] font-medium text-white transition hover:bg-ink-800"
            @click="showCreate = true"
          >
            <Plus :size="15" />
            新增记忆
          </button>
        </div>
      </header>

      <div class="mt-6 flex flex-wrap items-center gap-2">
        <button
          type="button"
          class="rounded-full px-3 py-1.5 text-[12px] font-medium transition"
          :class="statusFilter === '' ? 'bg-ink-900 text-white' : 'bg-white text-ink-500 hover:bg-slate-100'"
          @click="statusFilter = ''; page = 1; refresh()"
        >
          全部
        </button>
        <button
          v-for="status in (['active', 'suggested', 'disabled', 'forgotten'] as MemoryStatus[])"
          :key="status"
          type="button"
          class="rounded-full px-3 py-1.5 text-[12px] font-medium transition"
          :class="statusFilter === status ? 'bg-ink-900 text-white' : 'bg-white text-ink-500 hover:bg-slate-100'"
          @click="statusFilter = status; page = 1; refresh()"
        >
          {{ statusLabels[status] }}
        </button>
        <span class="ml-auto text-[12px] text-ink-400">
          {{ knowledge.memoryCount }} 条记忆
        </span>
      </div>

      <div
        v-if="!visibleMemories.length"
        class="mt-4 rounded-2xl border border-dashed border-slate-300 bg-white/60 px-4 py-12 text-center text-[13px] text-ink-400"
      >
        {{ knowledge.loading ? "加载中…" : "还没有记忆条目，新增一条让 AI 更懂你。" }}
      </div>

      <ul v-else class="mt-4 space-y-2">
        <li
          v-for="memory in visibleMemories"
          :key="memory.id"
          class="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-soft"
        >
          <div class="flex flex-wrap items-start gap-3">
            <span class="mt-0.5 shrink-0 text-ink-400">
              <Brain :size="16" />
            </span>
            <div class="min-w-0 flex-1">
              <p class="flex flex-wrap items-center gap-2 text-[13px] font-medium text-ink-900">
                <span class="font-mono text-[11.5px] text-ink-500">{{ memory.key }}</span>
                <span
                  class="rounded-md px-1.5 py-0.5 text-[10.5px]"
                  :class="statusClasses[memory.status] || 'bg-slate-100 text-ink-500'"
                >
                  {{ statusLabels[memory.status] || memory.status }}
                </span>
                <span class="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10.5px] text-ink-500">
                  {{ kindLabels[memory.kind] }}
                </span>
                <span class="text-[11px] font-normal text-ink-400">
                  {{ memory.scope_type === "global" ? "全局" : memory.project_name || "项目" }}
                </span>
              </p>
              <p class="mt-1 whitespace-pre-wrap break-words text-[12.5px] leading-6 text-ink-700">
                {{ memory.content || "（内容已清空）" }}
              </p>
              <p v-if="memory.source_ref" class="mt-1 text-[11px] text-ink-400">
                来源：{{ memory.source_ref }}
              </p>
            </div>
            <div class="ml-auto flex shrink-0 flex-wrap items-center justify-end gap-1.5">
              <button
                v-if="memory.status === 'suggested'"
                type="button"
                class="inline-flex items-center gap-1 rounded-lg bg-emerald-50 px-2 py-1 text-[11.5px] font-medium text-emerald-600 transition hover:bg-emerald-100"
                :disabled="busyId === memory.id"
                @click="runAction(memory, 'accept')"
              >
                <Check :size="12" />
                启用
              </button>
              <button
                v-if="memory.status === 'active'"
                type="button"
                class="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-2 py-1 text-[11.5px] font-medium text-ink-500 transition hover:bg-slate-200"
                :disabled="busyId === memory.id"
                @click="runAction(memory, 'disable')"
              >
                <CircleSlash :size="12" />
                停用
              </button>
              <button
                v-if="memory.status !== 'forgotten'"
                type="button"
                class="text-[11.5px] font-medium text-ink-500 transition hover:text-accent-600"
                @click="startEdit(memory)"
              >
                编辑
              </button>
              <button
                v-if="memory.status !== 'forgotten'"
                type="button"
                class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11.5px] font-medium text-ink-400 transition hover:bg-slate-100 hover:text-ink-700 disabled:opacity-50"
                title="忘记这条记忆"
                :aria-label="`忘记记忆 ${memory.key}`"
                :disabled="busyId === memory.id"
                @click="runAction(memory, 'forget')"
              >
                <Eraser :size="13" />
                忘记
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11.5px] font-medium text-rose-500 transition hover:bg-rose-50 hover:text-rose-700 disabled:opacity-50"
                title="彻底删除这条记忆及其记录"
                :aria-label="`彻底删除记忆 ${memory.key}`"
                :disabled="Boolean(busyId)"
                @click="askDelete(memory)"
              >
                <Trash2 :size="13" />
                彻底删除
              </button>
            </div>
          </div>
        </li>
      </ul>
      <nav
        v-if="knowledge.memoryPages > 1"
        class="mt-5 flex items-center justify-center gap-3"
        aria-label="记忆分页"
      >
        <button type="button" class="btn-secondary !h-9 !min-h-9 !px-3" :disabled="knowledge.memoryPage <= 1" @click="changePage(knowledge.memoryPage - 1)">上一页</button>
        <span class="text-[12px] tabular-nums text-ink-500">第 {{ knowledge.memoryPage }} / {{ knowledge.memoryPages }} 页</span>
        <button type="button" class="btn-secondary !h-9 !min-h-9 !px-3" :disabled="knowledge.memoryPage >= knowledge.memoryPages" @click="changePage(knowledge.memoryPage + 1)">下一页</button>
      </nav>
    </div>

    <div
      v-if="showCreate"
      class="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/60 p-4"
      @click.self="showCreate = false"
    >
      <div class="w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-xl">
        <div class="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <p class="text-[13.5px] font-medium text-ink-900">新增记忆</p>
          <button type="button" class="text-ink-400 hover:text-ink-700" @click="showCreate = false">
            <X :size="17" />
          </button>
        </div>
        <div class="p-4">
          <input
            v-model="draftKey"
            type="text"
            maxlength="128"
            placeholder="标识，例如 answer_language"
            class="w-full rounded-xl border border-slate-200 px-3 py-2 text-[13px] outline-none focus:border-accent-300"
          />
          <textarea
            v-model="draftContent"
            rows="4"
            maxlength="20000"
            placeholder="记忆内容，例如：回答时使用简体中文并给出处。"
            class="mt-3 w-full resize-y rounded-xl border border-slate-200 px-3 py-2 text-[12.5px] leading-6 outline-none focus:border-accent-300"
          ></textarea>
          <div class="mt-3 flex flex-wrap items-center gap-3">
            <select
              v-model="draftKind"
              class="rounded-xl border border-slate-200 px-3 py-2 text-[12.5px] text-ink-700 outline-none focus:border-accent-300"
            >
              <option value="preference">偏好</option>
              <option value="fact">事实</option>
              <option value="goal">目标</option>
            </select>
            <select
              v-model="draftScope"
              class="rounded-xl border border-slate-200 px-3 py-2 text-[12.5px] text-ink-700 outline-none focus:border-accent-300"
            >
              <option value="global">全局范围</option>
              <option value="project">项目范围</option>
            </select>
            <select
              v-if="draftScope === 'project'"
              v-model="draftProject"
              class="rounded-xl border border-slate-200 px-3 py-2 text-[12.5px] text-ink-700 outline-none focus:border-accent-300"
            >
              <option value="">选择项目</option>
              <option v-for="project in workspace.projects" :key="project.id" :value="project.id">
                {{ project.name }}
              </option>
            </select>
          </div>
        </div>
        <div class="flex justify-end gap-2 border-t border-slate-100 px-4 py-3">
          <button
            type="button"
            class="rounded-xl border border-slate-200 px-3.5 py-2 text-[12.5px] font-medium text-ink-600"
            @click="showCreate = false"
          >
            取消
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-xl bg-ink-900 px-4 py-2 text-[12.5px] font-medium text-white"
            @click="submitCreate"
          >
            <Save :size="13" />
            保存
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="editing"
      class="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/60 p-4"
      @click.self="editing = null"
    >
      <div class="w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-xl">
        <div class="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <p class="text-[13.5px] font-medium text-ink-900">
            编辑记忆 · <span class="font-mono text-[12px] text-ink-500">{{ editing.key }}</span>
          </p>
          <button type="button" class="text-ink-400 hover:text-ink-700" @click="editing = null">
            <X :size="17" />
          </button>
        </div>
        <div class="p-4">
          <textarea
            v-model="editContent"
            rows="5"
            maxlength="20000"
            class="w-full resize-y rounded-xl border border-slate-200 px-3 py-2 text-[12.5px] leading-6 outline-none focus:border-accent-300"
          ></textarea>
        </div>
        <div class="flex justify-end gap-2 border-t border-slate-100 px-4 py-3">
          <button
            type="button"
            class="rounded-xl border border-slate-200 px-3.5 py-2 text-[12.5px] font-medium text-ink-600"
            @click="editing = null"
          >
            取消
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-xl bg-ink-900 px-4 py-2 text-[12.5px] font-medium text-white"
            @click="saveEdit"
          >
            <Save :size="13" />
            保存
          </button>
        </div>
      </div>
    </div>

    <ModalShell
      :open="Boolean(pendingDelete)"
      title="彻底删除这条记忆？"
      subtitle="此操作无法撤销，也不会保留在已忘记或修改记录中。"
      max-width="max-w-md"
      :hide-close="Boolean(pendingDelete && busyId === pendingDelete.id)"
      @close="closeDelete"
    >
      <div v-if="pendingDelete" class="rounded-2xl border border-rose-100 bg-rose-50/70 p-4">
        <p class="break-all text-[12px] font-semibold text-ink-800">{{ pendingDelete.key }}</p>
        <p class="mt-2 line-clamp-3 whitespace-pre-wrap break-words text-[11.5px] leading-5 text-ink-500">
          {{ pendingDelete.content || "（内容已清空）" }}
        </p>
      </div>
      <p class="mt-3 text-[11.5px] leading-5 text-ink-500">
        删除后，这条记忆及其全部修改记录会从服务器物理移除，并立即停止向 AI 提供相关背景。
      </p>

      <template #footer>
        <button type="button" class="btn-secondary" :disabled="Boolean(busyId)" @click="closeDelete">
          取消
        </button>
        <button
          type="button"
          class="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-rose-600 px-4 text-[12px] font-semibold text-white shadow-sm transition hover:bg-rose-700 disabled:opacity-60"
          :disabled="Boolean(busyId)"
          @click="confirmDelete"
        >
          <Loader2 v-if="busyId" :size="13" class="animate-spin" />
          <Trash2 v-else :size="13" />
          永久删除
        </button>
      </template>
    </ModalShell>
  </div>
</template>
