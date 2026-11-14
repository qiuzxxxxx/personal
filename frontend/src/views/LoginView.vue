<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ArrowLeft,
  ArrowRight,
  Eye,
  EyeOff,
  HardDriveUpload,
  Loader2,
  LockKeyhole,
  MessagesSquare,
  ShieldCheck,
  Sparkles,
  UserRound,
  LogOut,
  Check,
} from "lucide-vue-next";
import BrandMark from "@/components/BrandMark.vue";
import UsageTermsModal from "@/components/UsageTermsModal.vue";
import SiteFooter from "@/components/SiteFooter.vue";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toast";
import { extractApiError } from "@/api/client";
import { initials } from "@/lib/format";
import type { User } from "@/types";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const toast = useToastStore();

const username = ref("");
const password = ref("");
const showPassword = ref(false);
const submitting = ref(false);
const error = ref("");
const filledAccount = ref("");
const termsOpen = ref(false);

const quickAccounts = [
  {
    username: "qzx",
    role: "最高管理员",
    hint: "密聊 + AI 对话 + 中转站完全控制",
    icon: ShieldCheck,
    accent: "text-amber-600 bg-amber-50 border-amber-100",
  },
  {
    username: "sqx",
    role: "管理员",
    hint: "密聊 + AI 对话 + 普通账号管理",
    icon: MessagesSquare,
    accent: "text-cyan-600 bg-cyan-50 border-cyan-100",
  },
  {
    username: "yk",
    role: "游客",
    hint: "仅文件中转站",
    icon: Eye,
    accent: "text-slate-600 bg-slate-100 border-slate-200",
  },
];

const redirectTarget = computed(() => {
  const value = route.query.redirect;
  if (typeof value !== "string") return "";
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/login")) return "";
  return value;
});

function accountCardClass(account: string): string {
  return filledAccount.value === account
    ? "border-accent-300 bg-accent-50/40 shadow-sm"
    : "border-slate-200/80 bg-white/70 hover:border-slate-300 hover:bg-white";
}

function fillAccount(name: string): void {
  username.value = name;
  password.value = "";
  filledAccount.value = name;
  error.value = "";
  const input = document.getElementById("login-password") as HTMLInputElement | null;
  input?.focus();
}

function homeFor(user: User): string {
  if (redirectTarget.value) {
    if (user.username === "yk" && redirectTarget.value !== "/transfer" && redirectTarget.value !== "/accounts") {
      return "/transfer";
    }
    return redirectTarget.value;
  }
  if (user.username === "yk") return "/transfer";
  return "/today";
}

async function submit(): Promise<void> {
  error.value = "";
  if (!username.value.trim() || !password.value) {
    error.value = "请输入用户名和密码。";
    return;
  }
  submitting.value = true;
  try {
    const user = await auth.login(username.value.trim(), password.value);
    password.value = "";
    toast.success(`欢迎回来，${user.username}`);
    await router.replace(homeFor(user));
  } catch (err) {
    error.value = extractApiError(err);
  } finally {
    submitting.value = false;
  }
}

function continueAsCurrent(): void {
  if (!auth.user) return;
  router.push(homeFor(auth.user));
}

async function switchAccount(): Promise<void> {
  await auth.logout();
  filledAccount.value = "";
  username.value = "";
  password.value = "";
  toast.info("已退出当前账号，请重新登录");
}

onMounted(async () => {
  if (!auth.initialized) await auth.initialize();
});
</script>

<template>
  <div class="login-page h-full overflow-y-auto">
    <div class="grid min-h-[100dvh] lg:grid-cols-[1.06fr_0.94fr]">
      <section class="visual-panel relative hidden overflow-hidden p-12 lg:flex lg:flex-col xl:p-16">
        <div class="visual-grid" aria-hidden="true" />
        <div class="visual-glow visual-glow-a" aria-hidden="true" />
        <div class="visual-glow visual-glow-b" aria-hidden="true" />
        <div class="visual-ring visual-ring-a" aria-hidden="true" />
        <div class="visual-ring visual-ring-b" aria-hidden="true" />

        <RouterLink to="/agent" class="relative z-10 flex w-fit items-center gap-3">
          <BrandMark :size="34" />
          <span class="text-[16px] font-semibold tracking-tight text-white">zixxx</span>
        </RouterLink>

        <div class="relative z-10 mt-auto max-w-[510px] pb-5">
          <span class="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/8 px-3 py-1.5 text-[9.5px] font-semibold uppercase tracking-[0.18em] text-white/65 backdrop-blur">
            <span class="h-1.5 w-1.5 rounded-full bg-cyan-300 shadow-[0_0_10px_rgba(103,232,249,.9)]" />
            Private space for two
          </span>
          <h2 class="mt-7 text-[39px] font-medium leading-[1.17] tracking-[-0.045em] text-white xl:text-[46px]">
            把重要的对话，<br />留在自己的服务器里。
          </h2>
          <p class="mt-5 max-w-[430px] text-[13.5px] leading-7 text-white/50">
            一个安静、克制、完全自托管的工作空间。AI、密聊与文件，在这里各自拥有清晰的边界。
          </p>

          <div class="mt-9 grid max-w-[460px] gap-3">
            <div class="feature-row">
              <span class="feature-icon"><MessagesSquare :size="16" /></span>
              <div>
                <p class="text-[12px] font-medium text-white/85">双人实时密聊</p>
                <p class="mt-0.5 text-[10.5px] text-white/40">WebSocket 低延迟通道，仅 qzx 与 sqx 可见</p>
              </div>
            </div>
            <div class="feature-row">
              <span class="feature-icon"><HardDriveUpload :size="16" /></span>
              <div>
                <p class="text-[12px] font-medium text-white/85">免密文件中转</p>
                <p class="mt-0.5 text-[10.5px] text-white/40">访客即传即取，私密文件只有 qzx 能看到</p>
              </div>
            </div>
            <div class="feature-row">
              <span class="feature-icon"><Sparkles :size="16" /></span>
              <div>
                <p class="text-[12px] font-medium text-white/85">你自己的 AI</p>
                <p class="mt-0.5 text-[10.5px] text-white/40">连接任意 OpenAI / Gemini / Claude 兼容接口</p>
              </div>
            </div>
          </div>
        </div>

        <div class="relative z-10 mt-7 flex items-end justify-between">
          <p class="text-[9px] uppercase tracking-[0.18em] text-white/25">Self-hosted · SQLite · Django</p>
          <div class="sample-chat">
            <div class="flex items-center gap-2">
              <span class="flex h-5 w-5 items-center justify-center rounded-full bg-gradient-to-br from-indigo-400 to-cyan-400 text-[8px] font-bold text-white">Q</span>
              <span class="text-[9px] font-medium text-white/65">qzx</span>
              <span class="ml-auto text-[8px] text-white/25">now</span>
            </div>
            <p class="mt-2 text-[10px] leading-4 text-white/55">文件已经放上中转站了，只有你能看到。</p>
            <div class="mt-2 flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-2 py-1.5">
              <LockKeyhole :size="9" class="text-cyan-300/80" />
              <span class="text-[8.5px] text-white/45">仅 qzx 可见 · 私密投递</span>
            </div>
          </div>
        </div>
      </section>

      <section class="relative flex min-h-[100dvh] flex-col bg-[#fbfcfd]">
        <div class="flex items-center justify-between px-6 pt-6 sm:px-10">
          <RouterLink to="/agent" class="flex items-center gap-2.5 lg:hidden">
            <BrandMark :size="29" />
            <span class="text-[14px] font-semibold tracking-tight text-ink-900">zixxx</span>
          </RouterLink>
          <RouterLink
            to="/transfer"
            class="ml-auto inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3.5 py-2 text-[11px] font-medium text-ink-500 shadow-sm transition hover:border-slate-300 hover:text-ink-800"
          >
            <ArrowLeft :size="13" />
            免密中转站
          </RouterLink>
        </div>

        <div class="flex flex-1 items-center justify-center px-6 pb-10 pt-8 sm:px-10 sm:pt-4">
          <div class="w-full max-w-[420px] animate-fade-up">
            <span class="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-accent-600">
              <Sparkles :size="12" />
              Secure entry
            </span>
            <h1 class="mt-3 text-[30px] font-medium tracking-[-0.04em] text-ink-900 sm:text-[34px]">
              进入你的专属空间
            </h1>
            <p class="mt-2.5 text-[12.5px] leading-6 text-ink-500">
              登录后即可使用 AI 对话与双人密聊；公开文件中转站无需账号，打开即传。
            </p>

            <div
              v-if="auth.isAuthenticated && auth.user"
              class="mt-6 rounded-2xl border border-slate-200/80 bg-white p-3.5 shadow-sm"
            >
              <div class="flex items-center gap-3">
                <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 via-blue-500 to-cyan-400 text-[13px] font-semibold text-white">
                  {{ initials(auth.user.username) }}
                </span>
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-1.5">
                    <span class="text-[12.5px] font-semibold text-ink-800">{{ auth.user.username }}</span>
                    <ShieldCheck v-if="auth.isQzx" :size="12" class="text-accent-500" />
                  </div>
                  <p class="text-[10.5px] text-ink-400">{{ auth.user.role }}</p>
                </div>
                <span class="flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-1 text-[9px] font-medium text-emerald-600">
                  <span class="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  已登录
                </span>
              </div>
              <div class="mt-3 flex gap-2">
                <button type="button" class="btn-primary h-9 flex-1 text-[11px]" @click="continueAsCurrent">
                  继续进入
                  <ArrowRight :size="13" />
                </button>
                <button type="button" class="btn-secondary h-9 px-3 text-[11px]" @click="switchAccount">
                  <LogOut :size="12" />
                  退出
                </button>
              </div>
            </div>

            <div v-if="auth.isAuthenticated" class="my-6 flex items-center gap-3">
              <span class="h-px flex-1 bg-slate-200" />
              <span class="text-[9.5px] uppercase tracking-[0.14em] text-ink-300">或切换账号</span>
              <span class="h-px flex-1 bg-slate-200" />
            </div>

            <form class="mt-7 space-y-3.5" @submit.prevent="submit">
              <div>
                <label for="login-username" class="field-label">用户名</label>
                <div class="field-wrap mt-1.5">
                  <UserRound :size="16" class="field-icon" />
                  <input
                    id="login-username"
                    v-model="username"
                    type="text"
                    class="field-input"
                    placeholder="qzx / sqx / yk"
                    autocomplete="username"
                    autocapitalize="none"
                    spellcheck="false"
                    autofocus
                  />
                </div>
              </div>

              <div>
                <label for="login-password" class="field-label">密码</label>
                <div class="field-wrap mt-1.5">
                  <LockKeyhole :size="16" class="field-icon" />
                  <input
                    id="login-password"
                    v-model="password"
                    :type="showPassword ? 'text' : 'password'"
                    class="field-input pr-10"
                    placeholder="请输入密码"
                    autocomplete="current-password"
                  />
                  <button
                    type="button"
                    class="absolute right-2 flex h-7 w-7 items-center justify-center rounded-lg text-ink-400 transition hover:bg-slate-100 hover:text-ink-700"
                    :aria-label="showPassword ? '隐藏密码' : '显示密码'"
                    @click="showPassword = !showPassword"
                  >
                    <EyeOff v-if="showPassword" :size="15" />
                    <Eye v-else :size="15" />
                  </button>
                </div>
              </div>

              <div
                v-if="error"
                class="flex items-center gap-2 rounded-xl border border-rose-100 bg-rose-50 px-3 py-2.5 text-[11px] text-rose-600"
              >
                <span class="h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400" />
                {{ error }}
              </div>

              <button
                type="submit"
                class="group flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-ink-900 text-[12px] font-semibold text-white shadow-[0_14px_30px_-18px_rgba(15,23,42,0.75)] transition duration-200 hover:bg-accent-600 disabled:cursor-not-allowed disabled:opacity-60"
                :disabled="submitting || auth.loading"
              >
                <Loader2 v-if="submitting || auth.loading" :size="16" class="animate-spin" />
                <template v-else>
                  登录
                  <ArrowRight :size="14" class="transition group-hover:translate-x-0.5" />
                </template>
              </button>
            </form>

            <div class="mt-7">
              <div class="mb-2.5 flex items-center justify-between">
                <p class="text-[9.5px] font-semibold uppercase tracking-[0.14em] text-ink-400">账号</p>
                <span class="text-[9.5px] text-ink-300">点击填入用户名</span>
              </div>
              <div class="grid gap-2">
                <button
                  v-for="account in quickAccounts"
                  :key="account.username"
                  type="button"
                  class="flex items-center gap-2.5 rounded-xl border p-2.5 text-left transition duration-200"
                  :class="accountCardClass(account.username)"
                  @click="fillAccount(account.username)"
                >
                  <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border" :class="account.accent">
                    <component :is="account.icon" :size="13" />
                  </span>
                  <span class="min-w-0 flex-1">
                    <span class="flex items-center gap-1.5">
                      <span class="text-[11px] font-semibold text-ink-800">{{ account.username }}</span>
                      <span class="text-[9px] text-ink-400">{{ account.role }}</span>
                    </span>
                    <span class="mt-0.5 block truncate text-[9px] text-ink-300">{{ account.hint }}</span>
                  </span>
                  <Check v-if="filledAccount === account.username" :size="13" class="text-accent-500" />
                  <ArrowRight v-else :size="12" class="text-ink-300" />
                </button>
              </div>
            </div>

            <div class="mt-7 flex items-center gap-2 rounded-xl bg-slate-100/70 px-3 py-2.5">
              <LockKeyhole :size="12" class="shrink-0 text-ink-400" />
              <p class="text-[9.5px] leading-4 text-ink-400">
                登录凭证以 Token 保存于浏览器。正式部署时请修改默认密码，并在反向代理层启用 HTTPS。
              </p>
            </div>

            <div class="mt-6 flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-[10px] text-ink-400">
              <RouterLink to="/transfer" class="transition hover:text-ink-700">免密文件中转站</RouterLink>
              <span class="h-2.5 w-px bg-slate-200" />
              <button type="button" class="underline underline-offset-2 transition hover:text-ink-700" @click="termsOpen = true">
                使用声明
              </button>
            </div>
          </div>
        </div>

        <SiteFooter />
      </section>
    </div>

    <UsageTermsModal :open="termsOpen" @close="termsOpen = false" />
  </div>
</template>

<style scoped>
.visual-panel {
  background:
    radial-gradient(1200px 620px at 75% 5%, rgba(61, 100, 255, 0.24), transparent 62%),
    radial-gradient(900px 700px at 15% 95%, rgba(13, 148, 136, 0.18), transparent 62%),
    linear-gradient(145deg, #08101f 0%, #0b1426 48%, #0d1a2f 100%);
}

.visual-grid {
  position: absolute;
  inset: 0;
  opacity: 0.32;
  background-image: radial-gradient(rgba(255, 255, 255, 0.13) 0.7px, transparent 0.7px);
  background-size: 24px 24px;
  mask-image: linear-gradient(to bottom, black, transparent 80%);
}

.visual-glow {
  position: absolute;
  border-radius: 999px;
  filter: blur(60px);
  pointer-events: none;
}

.visual-glow-a {
  top: -120px;
  right: -120px;
  width: 450px;
  height: 450px;
  background: rgba(83, 116, 255, 0.26);
}

.visual-glow-b {
  bottom: -180px;
  left: -100px;
  width: 480px;
  height: 480px;
  background: rgba(20, 184, 166, 0.14);
}

.visual-ring {
  position: absolute;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 999px;
  pointer-events: none;
}

.visual-ring-a {
  width: 620px;
  height: 620px;
  right: -260px;
  bottom: -220px;
}

.visual-ring-b {
  width: 380px;
  height: 380px;
  right: -130px;
  bottom: -100px;
  border-color: rgba(125, 211, 252, 0.08);
}

.feature-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.035);
  padding: 11px 13px;
  backdrop-filter: blur(10px);
}

.feature-icon {
  display: inline-flex;
  height: 30px;
  width: 30px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.07);
  color: rgba(165, 201, 255, 0.92);
}

.sample-chat {
  width: 218px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.055);
  padding: 11px 12px;
  box-shadow: 0 24px 50px -30px rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(16px);
  transform: rotate(-2deg);
}
</style>