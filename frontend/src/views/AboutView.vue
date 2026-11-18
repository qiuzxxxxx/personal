<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  Check,
  Contact,
  ExternalLink,
  Info,
  ListChecks,
  Pencil,
  Plus,
  ScrollText,
  Tag,
  Trash2,
  User,
  X,
} from "lucide-vue-next";
import ModalShell from "@/components/ModalShell.vue";
import BrandMark from "@/components/BrandMark.vue";
import { extractApiError } from "@/api/client";
import { fetchSiteAbout, saveSiteAbout } from "@/api/about";
import type { SiteAboutContent, SiteAboutLink } from "@/api/about";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toast";

const auth = useAuthStore();
const toast = useToastStore();

const content = ref<SiteAboutContent | null>(null);
const loading = ref(false);
const loadFailed = ref(false);

const editOpen = ref(false);
const saving = ref(false);
const form = ref<SiteAboutContent | null>(null);

const featureLines = computed(() =>
  (content.value?.features || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean),
);

const hasContent = computed(() => {
  const item = content.value;
  if (!item) return false;
  return Boolean(
    item.site_name ||
      item.tagline ||
      item.intro ||
      item.features ||
      item.developer ||
      item.contact ||
      item.app_version ||
      item.guide ||
      item.links.length,
  );
});

async function load(): Promise<void> {
  loading.value = true;
  loadFailed.value = false;
  try {
    content.value = await fetchSiteAbout();
  } catch {
    loadFailed.value = true;
  } finally {
    loading.value = false;
  }
}

function startEdit(): void {
  if (!content.value) return;
  form.value = { ...content.value, links: content.value.links.map((link) => ({ ...link })) };
  editOpen.value = true;
}

function addLink(): void {
  if (!form.value) return;
  form.value.links = [...form.value.links, { label: "", url: "" }];
}

function removeLink(index: number): void {
  if (!form.value) return;
  form.value.links = form.value.links.filter((_, i) => i !== index);
}

async function save(): Promise<void> {
  if (!form.value || saving.value) return;
  saving.value = true;
  try {
    const payload: SiteAboutContent = {
      ...form.value,
      links: form.value.links
        .map((link) => ({ label: link.label.trim(), url: link.url.trim() }))
        .filter((link) => link.label && link.url)
        .slice(0, 10),
    };
    content.value = await saveSiteAbout(payload);
    editOpen.value = false;
    toast.success("关于页面已更新");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="h-full overflow-y-auto bg-canvas">
    <div class="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 lg:py-12">
      <header class="flex items-center justify-between gap-3">
        <RouterLink to="/" class="inline-flex items-center gap-2">
          <BrandMark :size="24" />
        </RouterLink>
        <button
          v-if="auth.isSuper && content"
          type="button"
          class="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-[12.5px] font-medium text-ink-700 shadow-sm transition hover:border-accent-200"
          @click="startEdit"
        >
          <Pencil :size="14" />
          编辑内容
        </button>
      </header>

      <div v-if="loading" class="mt-10 space-y-3">
        <div class="h-8 w-56 animate-pulse rounded-full bg-slate-200/70" />
        <div class="h-4 w-80 animate-pulse rounded-full bg-slate-200/50" />
        <div class="h-24 w-full animate-pulse rounded-2xl bg-slate-200/40" />
      </div>

      <div v-else-if="loadFailed" class="mt-10 rounded-2xl border border-dashed border-slate-300 bg-white/60 px-4 py-10 text-center text-[13px] text-ink-400">
        关于内容加载失败，请稍后重试。
      </div>

      <template v-else-if="hasContent && content">
        <section class="mt-8 text-center">
          <h1 class="text-[30px] font-bold tracking-tight text-ink-900">
            {{ content.site_name || "缺页中断" }}
          </h1>
          <p v-if="content.tagline" class="mt-2 text-[14px] text-ink-500">{{ content.tagline }}</p>
          <p v-if="content.app_version" class="mt-3 inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-[11.5px] text-ink-500">
            <Tag :size="12" />
            {{ content.app_version }}
          </p>
        </section>

        <section v-if="content.intro" class="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
          <h2 class="flex items-center gap-2 text-[14px] font-semibold text-ink-900">
            <Info :size="15" class="text-accent-600" />
            站点介绍
          </h2>
          <p class="mt-2.5 whitespace-pre-wrap break-words text-[13.5px] leading-7 text-ink-600">{{ content.intro }}</p>
        </section>

        <section v-if="featureLines.length" class="mt-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
          <h2 class="flex items-center gap-2 text-[14px] font-semibold text-ink-900">
            <ListChecks :size="15" class="text-accent-600" />
            功能亮点
          </h2>
          <ul class="mt-3 space-y-2">
            <li v-for="(line, index) in featureLines" :key="index" class="flex items-start gap-2 text-[13.5px] leading-6 text-ink-600">
              <Check :size="15" class="mt-1 shrink-0 text-emerald-500" />
              <span class="min-w-0 break-words">{{ line }}</span>
            </li>
          </ul>
        </section>

        <section v-if="content.guide" class="mt-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
          <h2 class="flex items-center gap-2 text-[14px] font-semibold text-ink-900">
            <ScrollText :size="15" class="text-accent-600" />
            使用说明
          </h2>
          <p class="mt-2.5 whitespace-pre-wrap break-words text-[13.5px] leading-7 text-ink-600">{{ content.guide }}</p>
        </section>

        <section
          v-if="content.developer || content.contact || content.links.length"
          class="mt-4 grid gap-4 sm:grid-cols-2"
        >
          <div v-if="content.developer || content.contact" class="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
            <h2 class="flex items-center gap-2 text-[14px] font-semibold text-ink-900">
              <User :size="15" class="text-accent-600" />
              开发与联系
            </h2>
            <p v-if="content.developer" class="mt-2.5 text-[13.5px] leading-6 text-ink-600">
              <span class="text-ink-400">开发者：</span>{{ content.developer }}
            </p>
            <p v-if="content.contact" class="mt-1.5 flex items-start gap-1.5 text-[13.5px] leading-6 text-ink-600">
              <Contact :size="14" class="mt-1 shrink-0 text-ink-300" />
              <span class="min-w-0 break-words">{{ content.contact }}</span>
            </p>
          </div>
          <div v-if="content.links.length" class="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
            <h2 class="flex items-center gap-2 text-[14px] font-semibold text-ink-900">
              <ExternalLink :size="15" class="text-accent-600" />
              相关链接
            </h2>
            <ul class="mt-2.5 space-y-1.5">
              <li v-for="(link, index) in content.links" :key="index">
                <a
                  :href="link.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center gap-1.5 text-[13.5px] text-accent-600 underline-offset-2 transition hover:text-accent-700 hover:underline"
                >{{ link.label }}<ExternalLink :size="12" /></a>
              </li>
            </ul>
          </div>
        </section>

        <p v-if="content.updated_at" class="mt-6 text-center text-[11px] text-ink-300">
          内容更新于 {{ new Date(content.updated_at).toLocaleString("zh-CN", { hour12: false }) }}
        </p>
      </template>

      <div v-else class="mt-10 rounded-2xl border border-dashed border-slate-300 bg-white/60 px-4 py-10 text-center text-[13px] text-ink-400">
        关于页面还没有内容。<template v-if="auth.isSuper">点击右上角「编辑内容」开始填写。</template>
      </div>
    </div>

    <ModalShell
      :open="editOpen"
      title="编辑关于页面"
      subtitle="除链接外均可留空，留空的字段不会展示"
      max-width="max-w-2xl"
      @close="editOpen = false"
    >
      <div v-if="form" class="flex flex-col gap-3.5">
        <div class="grid gap-3.5 sm:grid-cols-2">
          <label class="flex flex-col gap-1.5">
            <span class="text-[12px] font-medium text-ink-600">站点名称</span>
            <input v-model="form.site_name" maxlength="100" class="input-base" placeholder="缺页中断" />
          </label>
          <label class="flex flex-col gap-1.5">
            <span class="text-[12px] font-medium text-ink-600">当前版本</span>
            <input v-model="form.app_version" maxlength="100" class="input-base" placeholder="例如 v2.0（2026-11）" />
          </label>
        </div>
        <label class="flex flex-col gap-1.5">
          <span class="text-[12px] font-medium text-ink-600">一句话标语</span>
          <input v-model="form.tagline" maxlength="200" class="input-base" placeholder="例如：个人工作台与多模态 AI 助手" />
        </label>
        <label class="flex flex-col gap-1.5">
          <span class="text-[12px] font-medium text-ink-600">站点介绍</span>
          <textarea v-model="form.intro" rows="4" maxlength="5000" class="input-base resize-y" placeholder="介绍这个站点是做什么的、面向谁使用" />
        </label>
        <label class="flex flex-col gap-1.5">
          <span class="text-[12px] font-medium text-ink-600">功能亮点（每行一条）</span>
          <textarea v-model="form.features" rows="4" maxlength="5000" class="input-base resize-y" placeholder="逐行填写，例如：&#10;日历排期与任务管理&#10;AI 对话与知识库" />
        </label>
        <label class="flex flex-col gap-1.5">
          <span class="text-[12px] font-medium text-ink-600">使用说明</span>
          <textarea v-model="form.guide" rows="4" maxlength="5000" class="input-base resize-y" placeholder="新用户上手指引、注意事项等" />
        </label>
        <div class="grid gap-3.5 sm:grid-cols-2">
          <label class="flex flex-col gap-1.5">
            <span class="text-[12px] font-medium text-ink-600">开发者 / 维护者</span>
            <input v-model="form.developer" maxlength="200" class="input-base" placeholder="例如：qzx" />
          </label>
          <label class="flex flex-col gap-1.5">
            <span class="text-[12px] font-medium text-ink-600">联系方式</span>
            <input v-model="form.contact" maxlength="500" class="input-base" placeholder="例如：邮箱 / 微信（可留空）" />
          </label>
        </div>

        <div class="flex flex-col gap-2">
          <div class="flex items-center justify-between">
            <span class="text-[12px] font-medium text-ink-600">相关链接（最多 10 条）</span>
            <button type="button" class="inline-flex items-center gap-1 text-[12px] font-medium text-accent-600 hover:text-accent-700" @click="addLink">
              <Plus :size="13" />
              添加链接
            </button>
          </div>
          <div v-if="!form.links.length" class="rounded-xl bg-slate-50 px-3 py-2 text-[12px] text-ink-400">
            还没有链接，可点击「添加链接」。
          </div>
          <div v-for="(link, index) in form.links" :key="index" class="flex items-center gap-2">
            <input v-model="link.label" maxlength="100" class="input-base w-36 shrink-0" placeholder="名称" />
            <input v-model="link.url" maxlength="500" class="input-base min-w-0 flex-1" placeholder="https://..." />
            <button type="button" class="icon-button h-8 w-8 !min-h-0 !min-w-0 shrink-0 text-ink-300 hover:text-red-600" aria-label="移除链接" @click="removeLink(index)">
              <Trash2 :size="14" />
            </button>
          </div>
        </div>
      </div>
      <template #footer>
        <button type="button" class="btn-secondary" :disabled="saving" @click="editOpen = false">
          <X :size="14" />
          取消
        </button>
        <button
          type="button"
          class="btn-primary inline-flex items-center gap-1.5"
          :disabled="saving"
          @click="save"
        >
          保存
        </button>
      </template>
    </ModalShell>
  </div>
</template>
