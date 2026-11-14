<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  ArrowLeft,
  KeyRound,
  Loader2,
  RefreshCw,
  ScrollText,
  ShieldCheck,
  UserCog,
  LockKeyhole,
} from "lucide-vue-next";
import ModalShell from "@/components/ModalShell.vue";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toast";
import { changeAccountPassword, fetchLogs, listAccounts } from "@/api/accounts";
import { extractApiError } from "@/api/client";
import { formatDate, initials } from "@/lib/format";
import type { AccountInfo, ActivityLogItem } from "@/types";

const router = useRouter();
const auth = useAuthStore();
const toast = useToastStore();

const accounts = ref<AccountInfo[]>([]);
const loading = ref(true);
const loadError = ref("");

const logsOpen = ref(false);
const logsFor = ref<AccountInfo | null>(null);
const logs = ref<ActivityLogItem[]>([]);
const logsLoading = ref(false);

const pwdOpen = ref(false);
const pwdFor = ref<AccountInfo | null>(null);
const pwd1 = ref("");
const pwd2 = ref("");
const pwdSaving = ref(false);
const pwdError = ref("");

const ACTION_LABEL: Record<string, string> = {
  login: "登录成功",
  login_failed: "登录失败",
  logout: "退出登录",
  password_changed: "密码被重置",
  transfer_upload: "上传文件",
  transfer_update: "修改文件",
  transfer_delete: "删除文件",
  agent_config_saved: "保存模型配置",
};

const isAdmin = computed(() => auth.isAdmin);

const meRank = computed(() => (auth.isSuper ? 2 : auth.isAdmin ? 1 : 0));

function targetRank(account: AccountInfo): number {
  return account.is_super ? 2 : account.is_admin ? 1 : 0;
}

function canChangePwd(account: AccountInfo): boolean {
  return account.username !== auth.user?.username && meRank.value >= targetRank(account);
}

function canViewLogs(account: AccountInfo): boolean {
  if (account.username === auth.user?.username) return true;
  if (auth.isSuper) return true;
  return auth.isAdmin && targetRank(account) === 0;
}

function pwdTitle(account: AccountInfo): string {
  if (account.username === auth.user?.username) return "该接口用于修改其他账号的密码";
  if (!canChangePwd(account)) return "无权重置同级或更高级管理员的密码";
  return `重置 ${account.username} 的密码`;
}

function logsTitle(account: AccountInfo): string {
  if (!canViewLogs(account)) return "该账号日志仅最高管理员 qzx 可查看";
  return `查看 ${account.username} 的日志`;
}

function actionLabel(action: string): string {
  return ACTION_LABEL[action] || action;
}

function actionClass(action: string): string {
  if (action === "login_failed" || action === "transfer_delete" || action === "password_changed") {
    return "bg-rose-50 text-rose-600";
  }
  if (action === "login" || action === "transfer_upload") {
    return "bg-emerald-50 text-emerald-600";
  }
  return "bg-slate-100 text-ink-500";
}

async function load(): Promise<void> {
  loading.value = true;
  try {
    accounts.value = await listAccounts();
    loadError.value = "";
  } catch (error) {
    loadError.value = extractApiError(error);
  } finally {
    loading.value = false;
  }
}

async function openLogs(account: AccountInfo): Promise<void> {
  logsFor.value = account;
  logsOpen.value = true;
  logsLoading.value = true;
  logs.value = [];
  try {
    logs.value = await fetchLogs(account.username, 200);
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    logsLoading.value = false;
  }
}

function openPwd(account: AccountInfo): void {
  pwdFor.value = account;
  pwd1.value = "";
  pwd2.value = "";
  pwdError.value = "";
  pwdOpen.value = true;
}

async function submitPwd(): Promise<void> {
  pwdError.value = "";
  if (pwd1.value.length < 12 || pwd1.value.length > 128) {
    pwdError.value = "密码长度需为 12–128 个字符。";
    return;
  }
  if (pwd1.value !== pwd2.value) {
    pwdError.value = "两次输入的密码不一致。";
    return;
  }
  if (!pwdFor.value) return;
  pwdSaving.value = true;
  try {
    const result = await changeAccountPassword(pwdFor.value.username, pwd1.value);
    toast.success(result.detail || "密码已更新");
    pwdOpen.value = false;
    await load();
  } catch (error) {
    pwdError.value = extractApiError(error);
  } finally {
    pwdSaving.value = false;
  }
}

function goLogin(): void {
  router.push({ path: "/", query: { redirect: "/accounts" } });
}

onMounted(async () => {
  await auth.initialize();
  if (!isAdmin.value) {
    loading.value = false;
    return;
  }
  await load();
});
</script>

<template>
  <div class="accounts-page h-full overflow-y-auto">
    <div class="relative z-10 mx-auto w-full max-w-[980px] px-4 pb-14 pt-7 sm:px-7 sm:pt-10">
      <header class="flex items-start gap-3.5">
        <span class="hidden h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-ink-900 text-white shadow-[0_14px_30px_-18px_rgba(15,23,42,.7)] sm:flex">
          <UserCog :size="22" :stroke-width="1.7" />
        </span>
        <div>
          <span class="text-[10px] font-semibold uppercase tracking-[0.18em] text-accent-600">Account control</span>
          <h1 class="mt-2 text-[29px] font-medium tracking-[-0.04em] text-ink-900 sm:text-[34px]">账号管理</h1>
          <p class="mt-1.5 max-w-[560px] text-[12.5px] leading-6 text-ink-500">
            最高管理员 <span class="font-medium text-ink-700">qzx</span> 可管理全部账号与中转站；管理员
            <span class="font-medium text-ink-700">sqx</span> 可重置游客密码、查看游客日志；游客仅能查看自己的日志。
          </p>
        </div>
        <button
          v-if="isAdmin"
          type="button"
          class="ml-auto flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-ink-400 transition hover:text-ink-700"
          title="刷新"
          :disabled="loading"
          @click="load"
        >
          <RefreshCw :size="13" :class="{ 'animate-spin': loading }" />
        </button>
      </header>

      <div
        v-if="!isAdmin"
        class="mt-8 flex flex-col items-center rounded-[28px] border border-white/80 bg-white/90 p-9 text-center shadow-float backdrop-blur-xl"
      >
        <span class="flex h-14 w-14 items-center justify-center rounded-2xl bg-ink-900 text-white shadow-lg">
          <LockKeyhole :size="23" />
        </span>
        <h2 class="mt-4 text-[20px] font-medium tracking-tight text-ink-900">仅管理员可访问</h2>
        <p class="mt-2 max-w-[360px] text-[12px] leading-6 text-ink-500">
          当前账号 <span class="font-medium text-ink-700">{{ auth.user?.username || "访客" }}</span>
          不具备账号管理权限。请使用 qzx 或 sqx 登录。
        </p>
        <div class="mt-5 flex gap-2">
          <button type="button" class="btn-primary" @click="goLogin">
            <ShieldCheck :size="14" />
            切换账号
          </button>
          <button type="button" class="btn-secondary" @click="router.push({ name: 'agent' })">
            <ArrowLeft :size="14" />
            返回 AI 对话
          </button>
        </div>
      </div>

      <section
        v-else
        class="mt-7 overflow-hidden rounded-[26px] border border-white/90 bg-white/75 shadow-[0_20px_60px_-45px_rgba(15,23,42,0.35)] backdrop-blur-xl"
      >
        <div class="flex items-center gap-2.5 border-b border-slate-200/60 px-5 py-4">
          <h2 class="text-[14px] font-semibold tracking-tight text-ink-900">全部账号</h2>
          <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-medium tabular-nums text-ink-500">
            {{ accounts.length }}
          </span>
          <span class="ml-auto flex items-center gap-1 text-[9px] text-ink-400">
            <ShieldCheck :size="10" class="text-accent-500" />
            改密将使对方旧会话立即失效
          </span>
        </div>

        <div v-if="loading" class="space-y-2 p-4">
          <div v-for="index in 3" :key="index" class="h-14 animate-pulse rounded-2xl bg-slate-200/60" />
        </div>
        <div v-else-if="loadError" class="p-8 text-center text-[12px] text-rose-600">{{ loadError }}</div>
        <div v-else class="divide-y divide-slate-100">
          <div
            v-for="account in accounts"
            :key="account.username"
            class="flex flex-col gap-3 px-5 py-4 transition hover:bg-white/80 sm:flex-row sm:items-center"
          >
            <div class="flex min-w-0 flex-1 items-center gap-3">
              <span
                class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold text-white shadow-sm"
                :class="
                  account.is_admin
                    ? 'bg-gradient-to-br from-indigo-500 via-blue-500 to-cyan-400'
                    : 'bg-gradient-to-br from-slate-400 to-slate-500'
                "
              >
                {{ initials(account.username) }}
              </span>
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-1.5">
                  <p class="text-[12.5px] font-semibold text-ink-800">{{ account.username }}</p>
                  <span
                    v-if="account.username === auth.user?.username"
                    class="rounded-full bg-accent-50 px-1.5 py-0.5 text-[8px] font-medium text-accent-600"
                  >当前登录</span>
                  <span
                    v-if="account.is_super"
                    class="inline-flex items-center gap-1 rounded-full bg-amber-50 px-1.5 py-0.5 text-[8px] font-medium text-amber-700"
                  >
                    <ShieldCheck :size="8" />
                    最高管理员
                  </span>
                  <span
                    v-else-if="account.is_admin"
                    class="inline-flex items-center gap-1 rounded-full bg-blue-50 px-1.5 py-0.5 text-[8px] font-medium text-blue-600"
                  >
                    <ShieldCheck :size="8" />
                    管理员
                  </span>
                  <span
                    v-else-if="account.is_chat_user"
                    class="rounded-full bg-blue-50 px-1.5 py-0.5 text-[8px] font-medium text-blue-600"
                  >密聊用户</span>
                  <span v-else class="rounded-full bg-slate-100 px-1.5 py-0.5 text-[8px] font-medium text-ink-500">
                    {{ account.role }}
                  </span>
                </div>
                <p class="mt-0.5 text-[9.5px] text-ink-400">
                  最近登录 {{ account.last_login ? formatDate(account.last_login) : "从未" }}
                  · 日志 {{ account.log_count }} 条
                </p>
              </div>
            </div>

            <div class="flex shrink-0 items-center gap-2">
              <button
                type="button"
                class="btn-secondary h-9 px-3 text-[10.5px]"
                :disabled="!canViewLogs(account)"
                :title="logsTitle(account)"
                @click="openLogs(account)"
              >
                <ScrollText :size="12" />
                查看日志
              </button>
              <button
                type="button"
                class="btn-secondary h-9 px-3 text-[10.5px]"
                :disabled="!canChangePwd(account)"
                :title="pwdTitle(account)"
                @click="openPwd(account)"
              >
                <KeyRound :size="12" />
                更改密码
              </button>
            </div>
          </div>
        </div>
      </section>

      <p class="mt-5 text-[9.5px] leading-5 text-ink-400">
        日志记录登录、改密、中转站上传/修改/删除与模型配置保存等操作；依据《使用声明》，其他账号的日志仅管理员 qzx / sqx 可查看。
      </p>
    </div>

    <ModalShell
      :open="logsOpen"
      :title="`${logsFor?.username || ''} 的操作日志`"
      subtitle="按时间倒序，最多 200 条"
      max-width="max-w-2xl"
      @close="logsOpen = false"
    >
      <div v-if="logsLoading" class="space-y-2 py-4">
        <div v-for="index in 4" :key="index" class="h-9 animate-pulse rounded-xl bg-slate-200/60" />
      </div>
      <div v-else-if="!logs.length" class="py-10 text-center text-[11.5px] text-ink-400">暂无日志记录</div>
      <div v-else class="space-y-1.5">
        <div
          v-for="log in logs"
          :key="log.id"
          class="flex items-start gap-3 rounded-xl border border-slate-100 bg-white/80 px-3 py-2.5"
        >
          <span class="mt-0.5 rounded-md px-1.5 py-0.5 text-[9px] font-medium" :class="actionClass(log.action)">
            {{ actionLabel(log.action) }}
          </span>
          <div class="min-w-0 flex-1">
            <p class="truncate text-[11px] text-ink-700">
              {{ log.detail || "—" }}
              <span v-if="log.actor_username && log.actor_username !== log.username" class="text-ink-400">
                （操作人 {{ log.actor_username }}）
              </span>
            </p>
            <p class="mt-0.5 text-[9px] text-ink-400">
              {{ formatDate(log.created_at) }}
              <span v-if="log.ip"> · {{ log.ip }}</span>
            </p>
          </div>
        </div>
      </div>
    </ModalShell>

    <ModalShell
      :open="pwdOpen"
      :title="`重置 ${pwdFor?.username || ''} 的密码`"
      subtitle="重置后该账号的现有登录会话将立即失效。"
      max-width="max-w-md"
      @close="pwdOpen = false"
    >
      <div class="space-y-3">
        <div>
          <label class="field-label" for="pwd-new">新密码</label>
          <input
            id="pwd-new"
            v-model="pwd1"
            type="password"
            class="field-textarea mt-1.5 h-10 resize-none py-2.5"
            placeholder="12–128 个字符"
            autocomplete="new-password"
          />
        </div>
        <div>
          <label class="field-label" for="pwd-confirm">确认新密码</label>
          <input
            id="pwd-confirm"
            v-model="pwd2"
            type="password"
            class="field-textarea mt-1.5 h-10 resize-none py-2.5"
            placeholder="再次输入"
            autocomplete="new-password"
          />
        </div>
        <div
          v-if="pwdError"
          class="rounded-xl border border-rose-100 bg-rose-50 px-3 py-2 text-[11px] text-rose-600"
        >
          {{ pwdError }}
        </div>
      </div>
      <template #footer>
        <button type="button" class="btn-secondary" @click="pwdOpen = false">取消</button>
        <button type="button" class="btn-primary" :disabled="pwdSaving" @click="submitPwd">
          <Loader2 v-if="pwdSaving" :size="13" class="animate-spin" />
          <KeyRound v-else :size="13" />
          确认重置
        </button>
      </template>
    </ModalShell>
  </div>
</template>

<style scoped>
.accounts-page {
  background:
    radial-gradient(900px 500px at 85% -10%, rgba(100, 133, 255, 0.07), transparent 65%),
    #f8fafc;
}
</style>
