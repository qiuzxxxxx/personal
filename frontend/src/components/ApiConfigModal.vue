<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import {
  KeyRound,
  Link2,
  Cpu,
  Eye,
  EyeOff,
  RotateCcw,
  ShieldCheck,
  Check,
  Sparkles,
  Loader2,
  Plug,
} from "lucide-vue-next";
import ModalShell from "@/components/ModalShell.vue";
import { PROVIDERS, DEFAULT_API_CONFIG, providerById } from "@/lib/providers";
import { useConfigStore } from "@/stores/config";
import { useToastStore } from "@/stores/toast";
import { extractApiError } from "@/api/client";
import { testAgentConnection } from "@/api/agent";
import type { ApiConfig, ProviderId } from "@/types";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: [] }>();

const configStore = useConfigStore();
const toast = useToastStore();
const draft = ref<ApiConfig>({ ...DEFAULT_API_CONFIG });
const newKey = ref("");
const clearKey = ref(false);
const showKey = ref(false);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const testing = ref(false);
const testResult = ref<{ ok: boolean; message: string } | null>(null);
let activeTest: AbortController | null = null;

const selected = computed(() => providerById(draft.value.provider));

watch(
  () => props.open,
  async (open, _, onCleanup) => {
    resetTest();
    if (!open) return;
    loading.value = true;
    let current = true;
    onCleanup(() => { current = false; });
    await configStore.load();
    if (!current) return;
    loading.value = false;
    draft.value = { ...configStore.config };
    newKey.value = "";
    clearKey.value = false;
    showKey.value = false;
    error.value = "";
  },
  { immediate: true },
);

watch(
  () => [draft.value.provider, draft.value.base_url, draft.value.model, newKey.value, clearKey.value],
  resetTest,
);
onBeforeUnmount(resetTest);

function resetTest(): void {
  activeTest?.abort();
  activeTest = null;
  testing.value = false;
  testResult.value = null;
}

function selectProvider(id: ProviderId): void {
  if (id === draft.value.provider) return;
  const preset = providerById(id);
  draft.value = {
    provider: id,
    base_url: preset.base_url,
    model: preset.model,
    system_prompt: draft.value.system_prompt,
  };
}

function resetAll(): void {
  draft.value = { ...DEFAULT_API_CONFIG };
  newKey.value = "";
  clearKey.value = false;
  toast.info("已恢复默认配置，记得保存");
}

function connectionFields() {
  const base_url = draft.value.base_url.trim();
  const model = draft.value.model.trim();
  if (!base_url) throw new Error("请填写 Base URL。");
  if (!/^https?:\/\//i.test(base_url)) {
    throw new Error("Base URL 需要以 http:// 或 https:// 开头。");
  }
  if (!model) throw new Error("请填写模型名称。");
  const api_key = newKey.value.trim();
  return {
    provider: draft.value.provider,
    base_url,
    model,
    api_key,
    clear_key: clearKey.value && !api_key,
  };
}

async function testConnection(): Promise<void> {
  if (loading.value || testing.value || saving.value) return;
  const controller = new AbortController();
  activeTest = controller;
  testing.value = true;
  testResult.value = null;
  try {
    const { latency_ms } = await testAgentConnection(connectionFields(), controller.signal);
    if (activeTest === controller) {
      testResult.value = { ok: true, message: `连接成功 · 首次文本响应 ${latency_ms} 毫秒` };
    }
  } catch (err) {
    if (activeTest === controller) {
      testResult.value = { ok: false, message: extractApiError(err) };
    }
  } finally {
    if (activeTest === controller) {
      activeTest = null;
      testing.value = false;
    }
  }
}

async function save(): Promise<void> {
  if (loading.value || saving.value) return;
  resetTest();
  error.value = "";
  saving.value = true;
  try {
    const fields = connectionFields();
    await configStore.save({
      ...fields,
      system_prompt: draft.value.system_prompt,
    });
    toast.success(
      newKey.value.trim()
        ? "配置已保存，API Key 已在服务端加密"
        : clearKey.value
          ? "配置已保存，服务端 Key 已清除"
          : "配置已保存",
    );
    emit("close");
  } catch (err) {
    error.value = extractApiError(err);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <ModalShell
    :open="open"
    title="连接你的 AI 模型"
    subtitle="选择服务商，填写接口地址和模型名称。"
    max-width="max-w-2xl"
    @close="emit('close')"
  >
    <div class="space-y-5">
      <section>
        <div class="mb-2.5 flex items-center justify-between">
          <label class="field-label">选择服务商</label>
          <span class="text-[10px] font-medium text-ink-400">{{ selected.protocol }}</span>
        </div>
        <div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
          <button
            v-for="provider in PROVIDERS"
            :key="provider.id"
            type="button"
            class="relative rounded-2xl border p-3 text-left transition duration-200"
            :class="
              draft.provider === provider.id
                ? 'border-accent-400 bg-accent-50/60 shadow-[0_0_0_3px_rgba(68,115,246,0.08)]'
                : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/60'
            "
            @click="selectProvider(provider.id)"
          >
            <span class="flex items-center gap-1.5">
              <span class="text-[12px] font-semibold text-ink-800">{{ provider.name }}</span>
              <span class="rounded bg-slate-100 px-1 py-0.5 text-[8px] font-medium uppercase tracking-wide text-ink-400">
                {{ provider.eyebrow }}
              </span>
            </span>
            <span class="mt-1 block text-[10px] leading-4 text-ink-400">{{ provider.description }}</span>
            <span
              v-if="draft.provider === provider.id"
              class="absolute right-2 top-2 flex h-4 w-4 items-center justify-center rounded-full bg-accent-500 text-white"
            >
              <Check :size="10" :stroke-width="3" />
            </span>
          </button>
        </div>
      </section>

      <section class="space-y-3">
        <div>
          <label class="field-label" for="api-base-url">Base URL</label>
          <div class="field-wrap mt-1.5">
            <Link2 :size="16" class="field-icon" />
            <input
              id="api-base-url"
              v-model="draft.base_url"
              type="url"
              class="field-input"
              :placeholder="draft.provider === 'custom' ? 'http://127.0.0.1:8080/v1' : selected.base_url"
              autocomplete="off"
              spellcheck="false"
            />
          </div>
          <p class="mt-1.5 text-[10.5px] leading-4 text-ink-400">
            {{ selected.protocol }} 接口地址，无需填写末尾的 <code class="text-[10px]">/chat/completions</code>。
            免密网关可留空 API Key。
          </p>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <div>
            <label class="field-label" for="api-key">API Key</label>
            <div class="field-wrap mt-1.5">
              <KeyRound :size="16" class="field-icon" />
              <input
                id="api-key"
                v-model="newKey"
                :type="showKey ? 'text' : 'password'"
                class="field-input pr-10"
                :placeholder="
                  configStore.hasKey
                    ? `已加密保存 ${configStore.keyHint} · 留空保持不变`
                    : 'sk-...'
                "
                autocomplete="off"
                spellcheck="false"
              />
              <button
                type="button"
                class="absolute right-2 flex h-7 w-7 items-center justify-center rounded-lg text-ink-400 transition hover:bg-slate-100 hover:text-ink-700"
                :aria-label="showKey ? '隐藏密钥' : '显示密钥'"
                @click="showKey = !showKey"
              >
                <EyeOff v-if="showKey" :size="15" />
                <Eye v-else :size="15" />
              </button>
            </div>
            <label
              v-if="configStore.hasKey"
              class="mt-2 flex items-center gap-2 text-[10px] text-ink-400"
            >
              <input v-model="clearKey" type="checkbox" class="h-3 w-3 accent-rose-500" />
              清除服务端已保存的 Key（清除后需重新输入）
            </label>
            <p v-else-if="draft.provider === 'deepseek'" class="mt-1.5 text-[10.5px] leading-4 text-ink-400">
              如果站点已配置默认 DeepSeek Key，此处可以留空。
            </p>
          </div>

          <div>
            <label class="field-label" for="api-model">模型名称</label>
            <div class="field-wrap mt-1.5">
              <Cpu :size="16" class="field-icon" />
              <input
                id="api-model"
                v-model="draft.model"
                type="text"
                class="field-input"
                :placeholder="selected.model || 'deepseek-flash'"
                autocomplete="off"
                spellcheck="false"
              />
            </div>
          </div>
        </div>

        <div>
          <div class="flex items-center justify-between">
            <label class="field-label" for="api-system">System Prompt</label>
            <button
              type="button"
              class="flex items-center gap-1 text-[10px] font-medium text-ink-400 transition hover:text-ink-700"
              @click="draft.system_prompt = ''"
            >
              <RotateCcw :size="11" />
              恢复默认人格
            </button>
          </div>
          <textarea
            id="api-system"
            v-model="draft.system_prompt"
            rows="3"
            class="field-textarea mt-1.5"
            placeholder="留空则使用 zixxx 默认系统提示词。你也可以定义专属语气、身份或回答规范。"
          />
        </div>
      </section>

      <div class="flex items-start gap-2.5 rounded-2xl border border-emerald-100 bg-emerald-50/60 px-3.5 py-3">
        <ShieldCheck :size="16" class="mt-0.5 shrink-0 text-emerald-600" />
        <p class="text-[11px] leading-[1.65] text-emerald-800/90">
          配置与 Key 保存在<span class="font-medium">服务端加密存储</span>（Fernet / AES-128-CBC + HMAC-SHA256）。数据库只存密文，接口只返回掩码提示（如 <code class="text-[10px]">sk-…3456</code>），Key 不会回传浏览器，也不会出现在页面源码中。
        </p>
      </div>

      <div
        v-if="error"
        class="flex items-center gap-2 rounded-xl border border-rose-100 bg-rose-50 px-3 py-2 text-[11px] text-rose-600"
      >
        <Sparkles :size="13" />
        {{ error }}
      </div>

      <div class="flex items-center justify-between border-t border-slate-100 pt-1">
        <button
          type="button"
          class="text-[11px] font-medium text-ink-400 transition hover:text-ink-700"
          @click="resetAll"
        >
          恢复全部默认设置
        </button>
        <p class="flex items-center gap-1 text-[10px] text-ink-300">
          <Sparkles :size="10" />
          支持流式与多模态
        </p>
      </div>
    </div>

    <template #footer>
      <div class="w-full min-w-0">
        <p
          role="status"
          class="break-words text-xs leading-5"
          :class="testResult ? (testResult.ok ? 'mb-2 text-emerald-800' : 'mb-2 text-rose-700') : 'sr-only'"
        >
          {{ testResult?.message || (testing ? "正在测试模型连接" : "") }}
        </p>
        <div class="flex flex-wrap items-center justify-end gap-2">
          <button
            type="button"
            class="btn-secondary mr-auto whitespace-nowrap"
            :disabled="loading || testing || saving"
            @click="testConnection"
          >
            <Loader2 v-if="testing" :size="13" class="animate-spin motion-reduce:animate-none" aria-hidden="true" />
            <Plug v-else :size="13" aria-hidden="true" />
            {{ testing ? "测试中…" : "测试连接" }}
          </button>
          <button type="button" class="btn-secondary" @click="emit('close')">取消</button>
          <button type="button" class="btn-primary shrink-0 whitespace-nowrap" :disabled="loading || saving" @click="save">
            <Loader2 v-if="saving" :size="13" class="animate-spin" />
            保存配置
          </button>
        </div>
      </div>
    </template>
  </ModalShell>
</template>
