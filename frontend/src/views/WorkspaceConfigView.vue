<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Cpu, Globe2, Loader2, Settings2, ShieldCheck, UserCog } from "lucide-vue-next";
import ApiConfigModal from "@/components/ApiConfigModal.vue";
import { testAgentConnection } from "@/api/agent";
import { extractApiError } from "@/api/client";
import { fetchMaintenance, updateMaintenance } from "@/api/accounts";
import { fetchPreferences, savePreferences } from "@/api/workspace";
import { useAuthStore } from "@/stores/auth";
import { useConfigStore } from "@/stores/config";
import { useToastStore } from "@/stores/toast";
import type { TaskPriority } from "@/types";

const router = useRouter();
const auth = useAuthStore();
const configStore = useConfigStore();
const toast = useToastStore();

const apiOpen = ref(false);
const testing = ref(false);
const testResult = ref("");
const preferenceLoading = ref(false);
const savingPreference = ref(false);
const timezone = ref("Asia/Shanghai");
const weekStartsOn = ref(1);
const defaultPriority = ref<TaskPriority>("normal");
const maintenanceEnabled = ref(false);
const maintenanceReason = ref("");
const maintenanceLoading = ref(false);

async function testConnection(): Promise<void> {
  testing.value = true;
  testResult.value = "";
  const controller = new AbortController();
  try {
    const result = await testAgentConnection(
      {
        provider: configStore.config.provider,
        base_url: configStore.config.base_url,
        model: configStore.config.model,
      },
      controller.signal,
    );
    testResult.value = `连接成功，首响 ${result.latency_ms} ms`;
  } catch (error) {
    testResult.value = extractApiError(error);
  } finally {
    testing.value = false;
  }
}

async function loadPreference(): Promise<void> {
  preferenceLoading.value = true;
  try {
    const preference = await fetchPreferences();
    timezone.value = preference.timezone;
    weekStartsOn.value = preference.week_starts_on;
    defaultPriority.value = preference.default_task_priority;
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    preferenceLoading.value = false;
  }
}

async function submitPreference(): Promise<void> {
  savingPreference.value = true;
  try {
    const preference = await savePreferences({
      timezone: timezone.value.trim() || "Asia/Shanghai",
      week_starts_on: weekStartsOn.value,
      default_task_priority: defaultPriority.value,
    });
    weekStartsOn.value = preference.week_starts_on;
    toast.success("工作区偏好已保存");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    savingPreference.value = false;
  }
}

async function loadMaintenance(): Promise<void> {
  if (!auth.isQzx) return;
  maintenanceLoading.value = true;
  try {
    const status = await fetchMaintenance();
    maintenanceEnabled.value = status.enabled;
    maintenanceReason.value = status.reason;
  } catch {
    // 维护状态读取失败不影响其他配置项。
  } finally {
    maintenanceLoading.value = false;
  }
}

async function toggleMaintenance(): Promise<void> {
  const next = !maintenanceEnabled.value;
  maintenanceLoading.value = true;
  try {
    const status = await updateMaintenance({
      enabled: next,
      reason: maintenanceReason.value.trim(),
    });
    maintenanceEnabled.value = status.enabled;
    maintenanceReason.value = status.reason;
    toast.success(status.enabled ? "已开启维护模式" : "已关闭维护模式");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    maintenanceLoading.value = false;
  }
}

onMounted(() => {
  void configStore.load();
  void loadPreference();
  void loadMaintenance();
});
</script>

<template>
  <div class="space-y-4 p-3 sm:p-5">
    <div>
      <h1 class="text-lg font-semibold text-slate-900">工作区配置</h1>
      <p class="text-xs text-slate-400">默认模型、周起始日、时区与系统维护</p>
    </div>

    <section class="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
      <div class="flex items-center gap-2">
        <Cpu :size="15" class="text-blue-600" />
        <h2 class="text-sm font-semibold text-slate-800">默认模型配置</h2>
      </div>
      <p class="mt-2 text-xs text-slate-500">
        当前模型：<span class="font-medium text-slate-800">{{ configStore.config.model || "未配置" }}</span>
        · {{ configStore.config.provider }}
        <span v-if="configStore.hasKey" class="text-emerald-600">（已保存密钥）</span>
        <span v-else class="text-slate-400">（使用内置 Key）</span>
      </p>
      <p class="mt-1 break-all text-[11px] text-slate-400">{{ configStore.config.base_url }}</p>
      <div class="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-[#4285f4] via-[#9b72cb] to-[#d96570] shadow-sm px-3 py-1.5 text-xs font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
          :disabled="testing"
          @click="testConnection"
        >
          <Loader2 v-if="testing" :size="13" class="animate-spin" />
          {{ testing ? "测试中..." : "测试连接" }}
        </button>
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 transition hover:bg-slate-50"
          @click="apiOpen = true"
        >
          <Settings2 :size="13" />
          模型设置
        </button>
        <span v-if="testResult" class="text-[11px] text-slate-500">{{ testResult }}</span>
      </div>
    </section>

    <section class="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
      <div class="flex items-center gap-2">
        <Globe2 :size="15" class="text-blue-600" />
        <h2 class="text-sm font-semibold text-slate-800">每周起始日与时区</h2>
      </div>
      <div class="mt-3 grid gap-3 sm:grid-cols-3">
        <label class="block space-y-1 text-xs text-slate-500">
          时区
          <input
            v-model="timezone"
            class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
            placeholder="Asia/Shanghai"
          />
        </label>
        <label class="block space-y-1 text-xs text-slate-500">
          每周起始日
          <select
            v-model.number="weekStartsOn"
            class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
          >
            <option :value="0">周日</option>
            <option :value="1">周一</option>
            <option :value="6">周六</option>
          </select>
        </label>
        <label class="block space-y-1 text-xs text-slate-500">
          默认任务优先级
          <select
            v-model="defaultPriority"
            class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
          >
            <option value="low">低</option>
            <option value="normal">普通</option>
            <option value="high">高</option>
          </select>
        </label>
      </div>
      <button
        type="button"
        class="mt-3 rounded-lg bg-gradient-to-r from-[#4285f4] via-[#9b72cb] to-[#d96570] shadow-sm px-3 py-1.5 text-xs font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
        :disabled="preferenceLoading || savingPreference"
        @click="submitPreference"
      >
        {{ savingPreference ? "保存中..." : "保存偏好" }}
      </button>
    </section>

    <section v-if="auth.isQzx" class="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
      <div class="flex items-center gap-2">
        <ShieldCheck :size="15" class="text-rose-600" />
        <h2 class="text-sm font-semibold text-slate-800">系统维护模式</h2>
      </div>
      <p class="mt-1 text-[11px] text-slate-400">开启后仅最高管理员 qzx 可登录，其他会话立即失效。</p>
      <div class="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          class="rounded-lg px-3 py-1.5 text-xs font-medium text-white transition disabled:opacity-50"
          :class="maintenanceEnabled ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-rose-600 hover:bg-rose-700'"
          :disabled="maintenanceLoading"
          @click="toggleMaintenance"
        >
          {{ maintenanceEnabled ? "关闭维护模式" : "开启维护模式" }}
        </button>
        <input
          v-model="maintenanceReason"
          class="w-full min-w-0 rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400 sm:w-auto sm:min-w-[220px] sm:flex-1"
          placeholder="维护说明（可选）"
        />
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 transition hover:bg-slate-50"
          @click="router.push('/accounts')"
        >
          <UserCog :size="13" />
          账号与日志
        </button>
      </div>
    </section>

    <ApiConfigModal :open="apiOpen" @close="apiOpen = false" />
  </div>
</template>
