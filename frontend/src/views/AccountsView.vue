<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  ArrowLeft,
  KeyRound,
  Loader2,
  LogIn,
  Megaphone,
  RefreshCw,
  ScrollText,
  ShieldCheck,
  UserCog,
  LockKeyhole,
  Lock,
  Unlock,
  Wrench,
  Plus,
  Trash2,
} from "lucide-vue-next";
import ModalShell from "@/components/ModalShell.vue";
import { useAuthStore } from "@/stores/auth";
import { useAnnouncementStore } from "@/stores/announcements";
import { useToastStore } from "@/stores/toast";
import {
  changeAccountPassword,
  createAccount,
  deleteAccount,
  fetchLogs,
  listAccountLocks,
  listAccounts,
  setAccountLock,
  updateAccountAccess,
  updateMaintenance,
} from "@/api/accounts";
import type { AccountAccessLevel } from "@/api/accounts";
import { fetchMaintenanceStatus } from "@/api/auth";
import { extractApiError } from "@/api/client";
import {
  getTransferAnnouncement,
  getLoginAnnouncement,
  saveTransferAnnouncement,
  saveLoginAnnouncement,
} from "@/api/transfer";
import { formatDate, initials } from "@/lib/format";
import type {
  AccountInfo,
  AccountLockInfo,
  ActivityLogItem,
  MaintenanceStatus,
} from "@/types";

const router = useRouter();
const auth = useAuthStore();
const announcements = useAnnouncementStore();
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

const createOpen = ref(false);
const createUsername = ref("");
const createPassword = ref("");
const createAccess = ref<AccountAccessLevel>("member");
const createSaving = ref(false);
const createError = ref("");

const deleteOpen = ref(false);
const deleteFor = ref<AccountInfo | null>(null);
const deleteSaving = ref(false);
const deleteError = ref("");
const accessSaving = ref("");

// 维护模式（仅超级管理员）
const maintenance = ref<MaintenanceStatus>({ enabled: false, reason: "" });
const maintenanceDraftEnabled = ref(false);
const maintenanceDraftReason = ref("");
const maintenanceSaving = ref(false);

// 账号锁定（仅超级管理员）
const locks = ref<Record<string, AccountLockInfo>>({});
const lockOpen = ref(false);
const lockFor = ref<AccountInfo | null>(null);
const lockReason = ref("");
const lockSaving = ref(false);
const lockError = ref("");

// 公告管理（仅超级管理员）
const announcementDraft = ref("");
const editingAnnouncement = ref(false);
const savingAnnouncement = ref(false);
const loginAnnouncementDraft = ref("");
const editingLoginAnnouncement = ref(false);
const savingLoginAnnouncement = ref(false);

const ACCESS_OPTIONS: Array<{ value: AccountAccessLevel; label: string }> = [
  { value: "admin", label: "管理员" },
  { value: "member", label: "成员" },
  { value: "guest", label: "访客" },
];

const ACTION_LABEL: Record<string, string> = {
  login: "登录成功",
  login_failed: "登录失败",
  logout: "退出登录",
  password_changed: "密码被重置",
  transfer_upload: "上传文件",
  transfer_update: "修改文件",
  transfer_delete: "删除文件",
  agent_config_saved: "保存模型配置",
  account_created: "创建账号",
  account_deleted: "删除账号",
  account_permission_changed: "修改权限",
  login_maintenance_blocked: "维护拦截",
  login_account_locked: "锁定拦截",
  maintenance_toggled: "切换维护模式",
  account_lock_toggled: "账号锁定变更",
};

const isAdmin = computed(() => auth.isAdmin);

const maintenanceDirty = computed(
  () =>
    maintenanceDraftEnabled.value !== maintenance.value.enabled ||
    maintenanceDraftReason.value.trim() !== maintenance.value.reason,
);

const lockTargetLocked = computed(
  () => Boolean(lockFor.value && isLocked(lockFor.value.username)),
);

const meRank = computed(() => (auth.isSuper ? 2 : auth.isAdmin ? 1 : 0));

function isLocked(username: string): boolean {
  return Boolean(locks.value[username]);
}

function targetRank(account: AccountInfo): number {
  return account.is_super ? 2 : account.is_admin ? 1 : 0;
}

function canChangePwd(account: AccountInfo): boolean {
  return account.username !== auth.user?.username && meRank.value > targetRank(account);
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

async function loadAnnouncements(): Promise<void> {
  if (!auth.isSuper) return;
  try {
    const [transfer, login] = await Promise.all([
      getTransferAnnouncement(),
      getLoginAnnouncement(),
    ]);
    announcementDraft.value = transfer.content;
    loginAnnouncementDraft.value = login.content;
  } catch {
    // 静默失败，不影响主页面
  }
}

async function loadMaintenance(): Promise<void> {
  if (!auth.isSuper) return;
  try {
    const status = await fetchMaintenanceStatus();
    maintenance.value = status;
    maintenanceDraftEnabled.value = status.enabled;
    maintenanceDraftReason.value = status.reason;
  } catch {
    // 维护状态读取失败不阻断账号列表
  }
}

async function loadLocks(): Promise<void> {
  if (!auth.isSuper) return;
  try {
    const rows = await listAccountLocks();
    locks.value = Object.fromEntries(rows.map((row) => [row.username, row]));
  } catch {
    // 锁定列表读取失败不阻断账号列表
  }
}

async function refresh(): Promise<void> {
  await Promise.all([load(), loadAnnouncements(), loadMaintenance(), loadLocks()]);
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

function openCreate(): void {
  createUsername.value = "";
  createPassword.value = "";
  createAccess.value = "member";
  createError.value = "";
  createOpen.value = true;
}

async function submitCreate(): Promise<void> {
  createError.value = "";
  if (!createUsername.value.trim()) {
    createError.value = "请输入用户名。";
    return;
  }
  if (createPassword.value.length < 12 || createPassword.value.length > 128) {
    createError.value = "密码长度需为 12–128 个字符。";
    return;
  }
  createSaving.value = true;
  try {
    await createAccount({
      username: createUsername.value.trim(),
      password: createPassword.value,
      access_level: createAccess.value,
    });
    createOpen.value = false;
    toast.success(`账号 ${createUsername.value.trim().toLowerCase()} 已创建`);
    await load();
  } catch (error) {
    createError.value = extractApiError(error);
  } finally {
    createSaving.value = false;
  }
}

async function changeAccess(account: AccountInfo, event: Event): Promise<void> {
  const next = (event.target as HTMLSelectElement).value as AccountAccessLevel;
  if (next === account.access_level) return;
  accessSaving.value = account.username;
  try {
    await updateAccountAccess(account.username, next);
    toast.success(`${account.username} 已设为${ACCESS_OPTIONS.find((item) => item.value === next)?.label || next}`);
    await load();
  } catch (error) {
    toast.error(extractApiError(error));
    (event.target as HTMLSelectElement).value = account.access_level;
  } finally {
    accessSaving.value = "";
  }
}

function openDelete(account: AccountInfo): void {
  deleteFor.value = account;
  deleteError.value = "";
  deleteOpen.value = true;
}

async function submitDelete(): Promise<void> {
  if (!deleteFor.value) return;
  deleteSaving.value = true;
  deleteError.value = "";
  try {
    const username = deleteFor.value.username;
    await deleteAccount(username);
    deleteOpen.value = false;
    deleteFor.value = null;
    toast.success(`账号 ${username} 已删除`);
    await load();
  } catch (error) {
    deleteError.value = extractApiError(error);
  } finally {
    deleteSaving.value = false;
  }
}

async function publishAnnouncement(): Promise<void> {
  if (!auth.isSuper || savingAnnouncement.value) return;
  savingAnnouncement.value = true;
  try {
    const saved = await saveTransferAnnouncement(announcementDraft.value.trim());
    announcementDraft.value = saved.content;
    editingAnnouncement.value = false;
    void announcements.load(true);
    void announcements.loadHistory(true).then(() => announcements.markSeen());
    toast.success(saved.content ? "中转站公告已发布。" : "中转站公告已撤下。");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    savingAnnouncement.value = false;
  }
}

async function publishLoginAnnouncement(): Promise<void> {
  if (!auth.isSuper || savingLoginAnnouncement.value) return;
  savingLoginAnnouncement.value = true;
  try {
    const saved = await saveLoginAnnouncement(loginAnnouncementDraft.value.trim());
    loginAnnouncementDraft.value = saved.content;
    editingLoginAnnouncement.value = false;
    void announcements.load(true);
    void announcements.loadHistory(true).then(() => announcements.markSeen());
    toast.success(saved.content ? "登录页公告已发布。" : "登录页公告已撤下。");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    savingLoginAnnouncement.value = false;
  }
}

function goLogin(): void {
  router.push({ path: "/", query: { redirect: "/accounts" } });
}

async function saveMaintenance(): Promise<void> {
  if (!auth.isSuper || maintenanceSaving.value) return;
  maintenanceSaving.value = true;
  try {
    const status = await updateMaintenance({
      enabled: maintenanceDraftEnabled.value,
      reason: maintenanceDraftReason.value.trim(),
    });
    maintenance.value = status;
    maintenanceDraftEnabled.value = status.enabled;
    maintenanceDraftReason.value = status.reason;
    toast.success(
      status.enabled
        ? "维护模式已开启，其他账号的登录会话已全部失效。"
        : "维护模式已关闭，其他账号可以重新登录。",
    );
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    maintenanceSaving.value = false;
  }
}

function openLock(account: AccountInfo): void {
  lockFor.value = account;
  lockReason.value = locks.value[account.username]?.reason ?? "";
  lockError.value = "";
  lockOpen.value = true;
}

async function submitLock(): Promise<void> {
  if (!lockFor.value) return;
  const account = lockFor.value;
  const nextLocked = !isLocked(account.username);
  lockSaving.value = true;
  lockError.value = "";
  try {
    await setAccountLock({
      username: account.username,
      locked: nextLocked,
      reason: lockReason.value.trim(),
    });
    lockOpen.value = false;
    toast.success(
      nextLocked
        ? `${account.username} 已锁定，现有登录会话已失效。`
        : `${account.username} 已解锁，可以重新登录。`,
    );
    await Promise.all([load(), loadLocks()]);
  } catch (error) {
    lockError.value = extractApiError(error);
  } finally {
    lockSaving.value = false;
  }
}

onMounted(async () => {
  await auth.initialize();
  if (!isAdmin.value) {
    loading.value = false;
    return;
  }
  await refresh();
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
          <h1 class="text-[29px] font-medium tracking-[-0.04em] text-ink-900 sm:text-[34px]">账号管理</h1>
          <p class="mt-1.5 max-w-[560px] text-[12.5px] leading-6 text-ink-500">
            qzx 可新增、删除账号并设置权限；管理员可重置普通账号密码并查看其日志。
          </p>
        </div>
        <div v-if="isAdmin" class="ml-auto flex shrink-0 items-center gap-2">
          <button
            v-if="auth.isSuper"
            type="button"
            class="btn-primary min-h-11 px-3.5 text-[11px]"
            @click="openCreate"
          >
            <Plus :size="14" />
            新增用户
          </button>
          <button
            type="button"
            class="flex h-11 w-11 items-center justify-center rounded-full border border-slate-200 bg-white text-ink-500 transition hover:text-ink-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400"
            title="刷新"
            :disabled="loading"
            @click="refresh"
          >
            <RefreshCw :size="14" :class="{ 'animate-spin': loading }" />
          </button>
        </div>
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
          不具备账号管理权限。请使用管理员账号登录。
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

      <template v-else>
        <!-- 维护模式（仅超级管理员可见） -->
        <section
          v-if="auth.isSuper"
          class="mt-7 overflow-hidden rounded-[26px] border border-white/90 bg-white/75 shadow-[0_20px_60px_-45px_rgba(15,23,42,0.35)] backdrop-blur-xl"
        >
          <div class="flex items-center gap-3 border-b border-slate-200/60 px-5 py-4">
            <span
              class="flex h-7 w-7 items-center justify-center rounded-xl text-white shadow-sm"
              :class="maintenance.enabled ? 'bg-amber-500' : 'bg-slate-800'"
            >
              <Wrench :size="14" />
            </span>
            <div class="min-w-0 flex-1">
              <h2 class="text-[14px] font-semibold tracking-tight text-ink-900">系统维护</h2>
              <p class="mt-0.5 text-[10px] text-ink-400">开启后仅最高管理员可登录，其他账号会被立即登出</p>
            </div>
            <span
              class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[8.5px] font-medium"
              :class="maintenance.enabled ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-600'"
            >
              <span
                class="h-1.5 w-1.5 rounded-full"
                :class="maintenance.enabled ? 'bg-amber-400' : 'bg-emerald-400'"
              />
              {{ maintenance.enabled ? "维护中" : "正常运行" }}
            </span>
          </div>

          <div class="flex flex-col gap-4 p-5 sm:flex-row sm:items-start">
            <div class="min-w-0 flex-1">
              <label class="field-label" for="maintenance-reason">维护说明</label>
              <textarea
                id="maintenance-reason"
                v-model="maintenanceDraftReason"
                rows="3"
                maxlength="500"
                class="field-textarea mt-1.5 w-full"
                placeholder="例如：系统升级，预计 30 分钟后恢复。"
              />
              <p class="mt-1.5 text-[10px] leading-5 text-ink-400">
                说明会展示在登录页；留空时显示默认提示。
              </p>
            </div>
            <div class="flex shrink-0 flex-col items-start gap-3 sm:w-[190px]">
              <div class="flex items-center gap-2.5">
                <button
                  type="button"
                  role="switch"
                  :aria-checked="maintenanceDraftEnabled"
                  aria-label="切换维护模式"
                  class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-300 focus-visible:ring-offset-2"
                  :class="maintenanceDraftEnabled ? 'bg-amber-500' : 'bg-slate-300'"
                  @click="maintenanceDraftEnabled = !maintenanceDraftEnabled"
                >
                  <span
                    class="inline-block h-5 w-5 transform rounded-full bg-white shadow transition"
                    :class="maintenanceDraftEnabled ? 'translate-x-[22px]' : 'translate-x-0.5'"
                  />
                </button>
                <span class="text-[11.5px] font-medium text-ink-700">
                  {{ maintenanceDraftEnabled ? "开启维护" : "正常开放" }}
                </span>
              </div>
              <button
                type="button"
                class="btn-primary min-h-10 w-full text-[11px]"
                :disabled="maintenanceSaving || !maintenanceDirty"
                @click="saveMaintenance"
              >
                <Loader2 v-if="maintenanceSaving" :size="13" class="animate-spin" />
                <Wrench v-else :size="13" />
                {{ maintenanceDirty ? "保存维护设置" : "设置已保存" }}
              </button>
            </div>
          </div>
        </section>

        <!-- 公告管理区块（仅超级管理员可见） -->
        <section
          v-if="auth.isSuper"
          class="mt-7 overflow-hidden rounded-[26px] border border-white/90 bg-white/75 shadow-[0_20px_60px_-45px_rgba(15,23,42,0.35)] backdrop-blur-xl"
        >
          <div class="flex items-center gap-3 border-b border-slate-200/60 px-5 py-4">
            <span class="flex h-7 w-7 items-center justify-center rounded-xl bg-gradient-to-br from-accent-500 to-blue-500 text-white shadow-sm">
              <Megaphone :size="14" />
            </span>
            <div class="min-w-0 flex-1">
              <h2 class="text-[14px] font-semibold tracking-tight text-ink-900">公告管理</h2>
              <p class="mt-0.5 text-[10px] text-ink-400">管理站点各处公告内容，仅超级管理员可见此区块</p>
            </div>
            <span class="hidden items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-[8.5px] font-medium text-amber-700 sm:inline-flex">
              <ShieldCheck :size="9" />
              超级管理员专属
            </span>
          </div>

          <div class="grid gap-3 p-5 sm:grid-cols-2">
            <!-- 中转站公告 -->
            <button
              type="button"
              class="announcement-card group flex items-start gap-3.5 rounded-2xl border border-slate-200/80 bg-gradient-to-br from-white to-slate-50/50 p-4 text-left transition hover:border-accent-200/70 hover:shadow-md hover:shadow-accent-500/5"
              @click="editingAnnouncement = true"
            >
              <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-50 text-accent-600 transition group-hover:bg-accent-100">
                <Megaphone :size="18" :stroke-width="1.7" />
              </span>
              <div class="min-w-0 flex-1">
                <p class="text-[12.5px] font-semibold text-ink-800">中转站公告</p>
                <p class="mt-0.5 text-[10px] leading-5 text-ink-400">显示在文件中转站页面顶部，所有访客均可看到</p>
                <div class="mt-2.5 flex items-center gap-1.5">
                  <span
                    class="inline-flex h-1.5 w-1.5 rounded-full"
                    :class="announcementDraft.trim() ? 'bg-emerald-400' : 'bg-slate-300'"
                  />
                  <span class="text-[9px] text-ink-400">
                    {{ announcementDraft.trim() ? "当前有公告内容" : "暂无公告" }}
                  </span>
                </div>
              </div>
              <span class="mt-0.5 shrink-0 rounded-lg border border-accent-100 bg-accent-50/50 px-2 py-1 text-[9px] font-medium text-accent-600 transition group-hover:border-accent-200 group-hover:bg-accent-50">
                编辑
              </span>
            </button>

            <!-- 登录页公告 -->
            <button
              type="button"
              class="announcement-card group flex items-start gap-3.5 rounded-2xl border border-slate-200/80 bg-gradient-to-br from-white to-slate-50/50 p-4 text-left transition hover:border-blue-200/70 hover:shadow-md hover:shadow-blue-500/5"
              @click="editingLoginAnnouncement = true"
            >
              <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-500 transition group-hover:bg-blue-100">
                <LogIn :size="18" :stroke-width="1.7" />
              </span>
              <div class="min-w-0 flex-1">
                <p class="text-[12.5px] font-semibold text-ink-800">登录页公告</p>
                <p class="mt-0.5 text-[10px] leading-5 text-ink-400">显示在未登录用户的登录表单上方</p>
                <div class="mt-2.5 flex items-center gap-1.5">
                  <span
                    class="inline-flex h-1.5 w-1.5 rounded-full"
                    :class="loginAnnouncementDraft.trim() ? 'bg-emerald-400' : 'bg-slate-300'"
                  />
                  <span class="text-[9px] text-ink-400">
                    {{ loginAnnouncementDraft.trim() ? "当前有公告内容" : "暂无公告" }}
                  </span>
                </div>
              </div>
              <span class="mt-0.5 shrink-0 rounded-lg border border-blue-100 bg-blue-50/50 px-2 py-1 text-[9px] font-medium text-blue-500 transition group-hover:border-blue-200 group-hover:bg-blue-50">
                编辑
              </span>
            </button>
          </div>
        </section>

        <!-- 账号列表 -->
        <section
          class="mt-5 overflow-hidden rounded-[26px] border border-white/90 bg-white/75 shadow-[0_20px_60px_-45px_rgba(15,23,42,0.35)] backdrop-blur-xl"
        >
          <div class="flex items-center gap-2.5 border-b border-slate-200/60 px-5 py-4">
            <h2 class="text-[14px] font-semibold tracking-tight text-ink-900">全部账号</h2>
            <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-medium tabular-nums text-ink-500">
              {{ accounts.length }}
            </span>
            <span class="ml-auto flex items-center gap-1 text-[9px] text-ink-400">
              <ShieldCheck :size="10" class="text-accent-500" />
              每个账号仅保留最近一次登录
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
                      ? 'bg-accent-600'
                      : 'bg-slate-500'
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
                      v-if="isLocked(account.username)"
                      class="inline-flex items-center gap-1 rounded-full bg-rose-50 px-1.5 py-0.5 text-[8px] font-medium text-rose-600"
                    >
                      <Lock :size="8" />
                      已锁定
                    </span>
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
                    >聊天用户</span>
                    <span v-else class="rounded-full bg-slate-100 px-1.5 py-0.5 text-[8px] font-medium text-ink-500">
                      {{ account.role }}
                    </span>
                  </div>
                  <p class="mt-0.5 text-[9.5px] text-ink-400">
                    最近登录 {{ account.last_login ? formatDate(account.last_login) : "从未" }}
                    · 日志 {{ account.log_count }} 条
                  </p>
                  <p v-if="isLocked(account.username)" class="mt-0.5 text-[9.5px] text-rose-500">
                    锁定原因：{{ locks[account.username]?.reason || "未填写" }}
                    <span v-if="locks[account.username]?.locked_by">
                      · 操作人 {{ locks[account.username]?.locked_by }}
                    </span>
                  </p>
                </div>
              </div>

              <div class="flex shrink-0 flex-wrap items-center gap-2">
                <label v-if="auth.isSuper && !account.is_super" class="sr-only" :for="`access-${account.username}`">
                  {{ account.username }} 的权限
                </label>
                <select
                  v-if="auth.isSuper && !account.is_super"
                  :id="`access-${account.username}`"
                  class="h-9 rounded-xl border border-slate-200 bg-white px-2.5 text-[10.5px] text-ink-700 outline-none focus:border-accent-300 focus:ring-2 focus:ring-accent-100"
                  :value="account.access_level"
                  :disabled="accessSaving === account.username"
                  @change="changeAccess(account, $event)"
                >
                  <option v-for="option in ACCESS_OPTIONS" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </option>
                </select>
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
                <button
                  v-if="auth.isSuper && !account.is_super"
                  type="button"
                  class="flex h-9 w-9 items-center justify-center rounded-xl transition focus-visible:outline-none focus-visible:ring-2"
                  :class="
                    isLocked(account.username)
                      ? 'text-amber-500 hover:bg-amber-50 hover:text-amber-600 focus-visible:ring-amber-300'
                      : 'text-ink-400 hover:bg-amber-50 hover:text-amber-600 focus-visible:ring-amber-300'
                  "
                  :aria-label="`${isLocked(account.username) ? '解锁' : '锁定'}账号 ${account.username}`"
                  :title="`${isLocked(account.username) ? '解锁' : '锁定'} ${account.username}`"
                  @click="openLock(account)"
                >
                  <Unlock v-if="isLocked(account.username)" :size="14" />
                  <Lock v-else :size="14" />
                </button>
                <button
                  v-if="auth.isSuper && !account.is_super"
                  type="button"
                  class="flex h-9 w-9 items-center justify-center rounded-xl text-ink-400 transition hover:bg-rose-50 hover:text-rose-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300"
                  :aria-label="`删除账号 ${account.username}`"
                  :title="`删除 ${account.username}`"
                  @click="openDelete(account)"
                >
                  <Trash2 :size="14" />
                </button>
              </div>
            </div>
          </div>
        </section>

        <p class="mt-5 text-[9.5px] leading-5 text-ink-400">
          日志记录登录、改密、账号权限调整、中转站操作与模型配置保存；管理员只能查看权限低于自己的账号。
        </p>
      </template>
    </div>

    <!-- 日志弹窗 -->
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

    <!-- 改密弹窗 -->
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

    <!-- 新增用户弹窗 -->
    <ModalShell
      :open="createOpen"
      title="新增用户"
      subtitle="创建后可随时调整账号权限。"
      max-width="max-w-md"
      @close="createOpen = false"
    >
      <div class="space-y-4">
        <div>
          <label class="field-label" for="account-username">用户名</label>
          <input
            id="account-username"
            v-model="createUsername"
            type="text"
            class="field-textarea mt-1.5 h-11 resize-none py-2.5 text-base"
            autocomplete="off"
            autocapitalize="none"
            maxlength="150"
          />
        </div>
        <div>
          <label class="field-label" for="account-password">初始密码</label>
          <input
            id="account-password"
            v-model="createPassword"
            type="password"
            class="field-textarea mt-1.5 h-11 resize-none py-2.5 text-base"
            placeholder="12–128 个字符"
            autocomplete="new-password"
          />
        </div>
        <div>
          <label class="field-label" for="account-access">权限</label>
          <select
            id="account-access"
            v-model="createAccess"
            class="field-textarea mt-1.5 h-11 py-2.5 text-base"
          >
            <option v-for="option in ACCESS_OPTIONS" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          <p class="mt-1.5 text-[10.5px] leading-5 text-ink-500">
            管理员可管理普通账号；成员可使用工作台与 AI；访客仅使用文件中转站。
          </p>
        </div>
        <div
          v-if="createError"
          role="alert"
          class="rounded-xl border border-rose-100 bg-rose-50 px-3 py-2 text-[11px] text-rose-600"
        >
          {{ createError }}
        </div>
      </div>
      <template #footer>
        <button type="button" class="btn-secondary min-h-11" @click="createOpen = false">取消</button>
        <button type="button" class="btn-primary min-h-11" :disabled="createSaving" @click="submitCreate">
          <Loader2 v-if="createSaving" :size="14" class="animate-spin" />
          <Plus v-else :size="14" />
          创建用户
        </button>
      </template>
    </ModalShell>

    <!-- 删除账号弹窗 -->
    <ModalShell
      :open="deleteOpen"
      :title="`删除账号 ${deleteFor?.username || ''}`"
      subtitle="该操作会同时删除此账号的个人数据，无法撤销。"
      max-width="max-w-md"
      @close="deleteOpen = false"
    >
      <p class="text-sm leading-6 text-ink-600">
        确认删除 <span class="font-semibold text-ink-900">{{ deleteFor?.username }}</span>？
      </p>
      <div
        v-if="deleteError"
        role="alert"
        class="mt-3 rounded-xl border border-rose-100 bg-rose-50 px-3 py-2 text-[11px] text-rose-600"
      >
        {{ deleteError }}
      </div>
      <template #footer>
        <button type="button" class="btn-secondary min-h-11" @click="deleteOpen = false">取消</button>
        <button
          type="button"
          class="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-rose-600 px-4 text-sm font-semibold text-white transition hover:bg-rose-700 disabled:opacity-60"
          :disabled="deleteSaving"
          @click="submitDelete"
        >
          <Loader2 v-if="deleteSaving" :size="14" class="animate-spin" />
          <Trash2 v-else :size="14" />
          确认删除
        </button>
      </template>
    </ModalShell>

    <!-- 账号锁定弹窗 -->
    <ModalShell
      :open="lockOpen"
      :title="`${lockTargetLocked ? '解锁' : '锁定'}账号 ${lockFor?.username || ''}`"
      :subtitle="
        lockTargetLocked
          ? '解锁后该账号可以重新登录。'
          : '锁定后该账号无法登录，已有登录会话会立即失效。'
      "
      max-width="max-w-md"
      @close="lockOpen = false"
    >
      <p class="text-sm leading-6 text-ink-600">
        {{ lockTargetLocked ? "确认解除" : "确认锁定" }}
        <span class="font-semibold text-ink-900">{{ lockFor?.username }}</span>？
      </p>
      <div class="mt-3">
        <label class="field-label" for="lock-reason">
          {{ lockTargetLocked ? "解锁备注（可选）" : "锁定原因（可选）" }}
        </label>
        <textarea
          id="lock-reason"
          v-model="lockReason"
          rows="3"
          maxlength="255"
          class="field-textarea mt-1.5 w-full"
          :placeholder="lockTargetLocked ? '例如：问题已核实处理完毕。' : '例如：账号存在异常登录行为。'"
        />
      </div>
      <div
        v-if="lockError"
        role="alert"
        class="mt-3 rounded-xl border border-rose-100 bg-rose-50 px-3 py-2 text-[11px] text-rose-600"
      >
        {{ lockError }}
      </div>
      <template #footer>
        <button type="button" class="btn-secondary min-h-11" @click="lockOpen = false">取消</button>
        <button
          type="button"
          class="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold text-white transition disabled:opacity-60"
          :class="lockTargetLocked ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-rose-600 hover:bg-rose-700'"
          :disabled="lockSaving"
          @click="submitLock"
        >
          <Loader2 v-if="lockSaving" :size="14" class="animate-spin" />
          <Unlock v-else-if="lockTargetLocked" :size="14" />
          <Lock v-else :size="14" />
          {{ lockTargetLocked ? "确认解锁" : "确认锁定" }}
        </button>
      </template>
    </ModalShell>

    <!-- 中转站公告编辑弹窗 -->
    <ModalShell
      :open="editingAnnouncement"
      title="发布文件中转站公告"
      subtitle="公告会显示在访客与登录用户的文件中转站页面。"
      max-width="max-w-xl"
      @close="editingAnnouncement = false"
    >
      <textarea
        v-model="announcementDraft"
        rows="5"
        maxlength="5000"
        class="field-textarea w-full"
        placeholder="输入公告内容；留空后保存会撤下公告。"
      />
      <template #footer>
        <button type="button" class="btn-secondary" :disabled="savingAnnouncement" @click="editingAnnouncement = false">取消</button>
        <button type="button" class="btn-primary" :disabled="savingAnnouncement" @click="publishAnnouncement">
          <Loader2 v-if="savingAnnouncement" :size="13" class="animate-spin" />
          <Megaphone v-else :size="13" />
          {{ announcementDraft.trim() ? "发布公告" : "撤下公告" }}
        </button>
      </template>
    </ModalShell>

    <!-- 登录页公告编辑弹窗 -->
    <ModalShell
      :open="editingLoginAnnouncement"
      title="发布登录页公告"
      subtitle="公告会在未登录用户的登录表单上方展示。"
      max-width="max-w-xl"
      @close="editingLoginAnnouncement = false"
    >
      <textarea
        v-model="loginAnnouncementDraft"
        rows="5"
        maxlength="5000"
        class="field-textarea w-full"
        placeholder="输入登录页公告；留空后保存会撤下公告。"
      />
      <template #footer>
        <button type="button" class="btn-secondary" :disabled="savingLoginAnnouncement" @click="editingLoginAnnouncement = false">取消</button>
        <button type="button" class="btn-primary" :disabled="savingLoginAnnouncement" @click="publishLoginAnnouncement">
          <Loader2 v-if="savingLoginAnnouncement" :size="13" class="animate-spin" />
          <LogIn v-else :size="13" />
          {{ loginAnnouncementDraft.trim() ? "发布公告" : "撤下公告" }}
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

.announcement-card {
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.15s ease;
}

.announcement-card:hover {
  transform: translateY(-1px);
}

.announcement-card:active {
  transform: translateY(0);
}
</style>
