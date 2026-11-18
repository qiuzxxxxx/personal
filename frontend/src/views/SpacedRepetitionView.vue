<script setup lang="ts">
import { onMounted, ref } from "vue";
import { BookOpen, Plus } from "lucide-vue-next";
import ModalShell from "@/components/ModalShell.vue";
import { createReviewCard } from "@/api/knowledge";
import { extractApiError } from "@/api/client";
import { useReviewsStore } from "@/stores/reviews";
import { useToastStore } from "@/stores/toast";
import type { ReviewGrade } from "@/types";

const reviews = useReviewsStore();
const toast = useToastStore();

const createOpen = ref(false);
const front = ref("");
const back = ref("");
const tag = ref("408复习");
const saving = ref(false);

const grades: { key: ReviewGrade; label: string; hint: string; className: string }[] = [
  { key: "again", label: "重来", hint: "10m", className: "bg-rose-50 text-rose-700 border-rose-200" },
  { key: "hard", label: "困难", hint: "1d", className: "bg-amber-50 text-amber-700 border-amber-200" },
  { key: "good", label: "良好", hint: "3d", className: "bg-blue-50 text-blue-700 border-blue-200" },
  { key: "easy", label: "记住", hint: "7d", className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
];

async function grade(key: ReviewGrade): Promise<void> {
  try {
    await reviews.gradeCurrent(key);
    toast.success("已更新下次复习时间");
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function submitCard(): Promise<void> {
  if (!front.value.trim() || !back.value.trim()) return;
  saving.value = true;
  try {
    await createReviewCard({
      front: front.value.trim(),
      back: back.value.trim(),
      tag: tag.value.trim() || "408复习",
    });
    front.value = "";
    back.value = "";
    createOpen.value = false;
    await reviews.load();
    toast.success("复习卡已创建");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  void reviews.load().catch((error) => toast.error(extractApiError(error)));
});
</script>

<template>
  <div class="space-y-4 p-3 sm:p-5">
    <div class="flex flex-wrap items-center gap-3">
      <div>
        <h1 class="text-lg font-semibold text-slate-900">间隔复习（SM-2 记忆曲线）</h1>
        <p class="text-xs text-slate-400">{{ reviews.progressLabel }}</p>
      </div>
      <button
        type="button"
        class="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-[#4285f4] via-[#9b72cb] to-[#d96570] shadow-sm px-3 py-2 text-xs font-medium text-white transition hover:bg-blue-700"
        @click="createOpen = true"
      >
        <Plus :size="13" />
        新建复习卡
      </button>
    </div>

    <div v-if="reviews.loading" class="mx-auto h-72 max-w-2xl animate-pulse rounded-2xl bg-white" />

    <div
      v-else-if="reviews.current"
      class="mx-auto max-w-2xl rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm sm:p-6"
    >
      <div class="flex items-center gap-2">
        <span class="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-medium text-blue-700">
          {{ reviews.current.tag }}
        </span>
        <span class="text-[11px] text-slate-400">当前间隔：{{ reviews.current.interval_days }} 天</span>
      </div>

      <div class="mt-6 min-h-[120px]">
        <p class="text-center text-lg font-semibold leading-8 text-slate-900">
          {{ reviews.current.front }}
        </p>
      </div>

      <div v-if="reviews.revealed" class="mt-4 rounded-xl bg-slate-50 p-4 text-sm leading-7 text-slate-700">
        {{ reviews.current.back }}
      </div>

      <button
        v-if="!reviews.revealed"
        type="button"
        class="mt-6 w-full rounded-xl bg-gradient-to-r from-[#4285f4] via-[#9b72cb] to-[#d96570] shadow-sm py-2.5 text-sm font-medium text-white transition hover:bg-blue-700"
        @click="reviews.flip()"
      >
        显示答案
      </button>

      <div v-else class="mt-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <button
          v-for="item in grades"
          :key="item.key"
          type="button"
          class="rounded-xl border px-2 py-2.5 text-xs font-medium transition hover:brightness-95 disabled:opacity-50"
          :class="item.className"
          :disabled="reviews.grading"
          @click="grade(item.key)"
        >
          <span class="block">{{ item.label }}</span>
          <span class="mt-0.5 block text-[10px] opacity-70">{{ item.hint }}</span>
        </button>
      </div>
    </div>

    <div v-else class="mx-auto max-w-2xl rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
      <BookOpen :size="28" class="mx-auto text-slate-300" />
      <p class="mt-3 text-sm font-medium text-slate-600">今日没有待复习卡片</p>
      <p class="mt-1 text-xs text-slate-400">新建复习卡后，会按 SM-2 记忆曲线安排复习时间。</p>
    </div>

    <ModalShell :open="createOpen" title="新建复习卡" subtitle="正面问题，背面答案" max-width="max-w-lg" @close="createOpen = false">
      <div class="space-y-3">
        <label class="block space-y-1 text-xs text-slate-500">
          正面问题
          <textarea v-model="front" rows="2" class="w-full resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400" />
        </label>
        <label class="block space-y-1 text-xs text-slate-500">
          背面答案
          <textarea v-model="back" rows="4" class="w-full resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400" />
        </label>
        <label class="block space-y-1 text-xs text-slate-500">
          分类标签
          <input v-model="tag" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400" />
        </label>
      </div>
      <template #footer>
        <button type="button" class="btn-secondary" @click="createOpen = false">取消</button>
        <button type="button" class="btn-primary" :disabled="saving" @click="submitCard">创建</button>
      </template>
    </ModalShell>
  </div>
</template>
