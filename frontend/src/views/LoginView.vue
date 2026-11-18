<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ArrowLeft,
  ArrowRight,
  Eye,
  EyeOff,
  Loader2,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
  UserRound,
  LogOut,
  Wrench,
} from "lucide-vue-next";
import BrandMark from "@/components/BrandMark.vue";
import brandLogo from "@/assets/brand/zixxx-logo.png";
import UsageTermsModal from "@/components/UsageTermsModal.vue";
import AnnouncementBody from "@/components/AnnouncementBody.vue";
import ModalShell from "@/components/ModalShell.vue";
import SiteFooter from "@/components/SiteFooter.vue";
import { useAnnouncementStore } from "@/stores/announcements";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toast";
import { fetchMaintenanceStatus } from "@/api/auth";
import { extractApiError } from "@/api/client";
import { initials } from "@/lib/format";
import type { MaintenanceStatus, User } from "@/types";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const toast = useToastStore();
const announcements = useAnnouncementStore();

const username = ref("");
const password = ref("");
const particleCanvas = ref<HTMLCanvasElement | null>(null);
const showPassword = ref(false);
const submitting = ref(false);
const error = ref("");
const termsOpen = ref(false);
const announcementOpen = ref(false);
const maintenance = ref<MaintenanceStatus | null>(null);
let disposeParticleField: (() => void) | null = null;

const redirectTarget = computed(() => {
  const value = route.query.redirect;
  if (typeof value !== "string") return "";
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/login")) return "";
  return value;
});

function homeFor(user: User): string {
  if (redirectTarget.value) {
    if (user.is_guest && redirectTarget.value !== "/transfer" && redirectTarget.value !== "/accounts") {
      return "/transfer";
    }
    return redirectTarget.value;
  }
  if (user.is_guest) return "/transfer";
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
    void loadMaintenance();
  } finally {
    submitting.value = false;
  }
}

async function loadMaintenance(): Promise<void> {
  try {
    maintenance.value = await fetchMaintenanceStatus();
  } catch {
    // 维护状态读取失败不能阻断正常登录。
  }
}

function continueAsCurrent(): void {
  if (!auth.user) return;
  router.push(homeFor(auth.user));
}

function switchAccount(): void {
  void auth.logout();
  username.value = "";
  password.value = "";
  toast.info("已退出当前账号，请重新登录");
}

onMounted(() => {
  disposeParticleField = mountParticleField(particleCanvas.value);
  if (!auth.initialized) void auth.initialize();
  // 公告改为弹窗：读取完成后若存在登录页公告则自动弹出，页面不再内嵌公告区域。
  void announcements.load(true).then(() => {
    if (announcements.hasLogin) openAnnouncement();
  });
  void announcements.loadHistory(true);
  void loadMaintenance();
});

function openAnnouncement(): void {
  announcementOpen.value = true;
  announcements.markSeen();
  void announcements.loadHistory(true).then(() => announcements.markSeen());
}

onUnmounted(() => disposeParticleField?.());

type Particle = {
  angle: number;
  orbit: number;
  speed: number;
  phase: number;
  size: number;
  hue: number;
};

function mountParticleField(canvas: HTMLCanvasElement | null): (() => void) | null {
  if (!canvas) return null;
  const canvasElement: HTMLCanvasElement = canvas;
  const contextResult = canvasElement.getContext("2d", { alpha: true, desynchronized: true });
  if (!contextResult) return null;
  const context: CanvasRenderingContext2D = contextResult;

  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
  let width = 0;
  let height = 0;
  let frame = 0;
  let previousTime = 0;
  const particles: Particle[] = Array.from({ length: 142 }, () => ({
    angle: Math.random() * Math.PI * 2,
    orbit: 0.06 + Math.sqrt(Math.random()) * 0.91,
    speed: (0.00009 + Math.random() * 0.00025) * (Math.random() > 0.5 ? 1 : -1),
    phase: Math.random() * Math.PI * 2,
    size: 0.45 + Math.random() * 1.3,
    hue: [184, 197, 215, 232, 250][Math.floor(Math.random() * 5)],
  }));

  function stop(): void {
    if (!frame) return;
    cancelAnimationFrame(frame);
    frame = 0;
  }

  function draw(time: number): void {
    frame = 0;
    if (!width || !height || document.hidden) return;

    const delta = previousTime ? Math.min(time - previousTime, 40) : 16;
    previousTime = time;
    const cx = width * 0.5;
    const cy = height * 0.51;
    const radius = Math.min(width, height) * 0.47;
    context.clearRect(0, 0, width, height);
    context.globalCompositeOperation = "screen";

    // Fine elliptical filaments give the particles a visible orbital field.
    for (let index = 0; index < 4; index += 1) {
      const drift = time * (index % 2 ? -0.000035 : 0.000028);
      context.beginPath();
      context.ellipse(
        cx,
        cy,
        radius * (0.44 + index * 0.135),
        radius * (0.18 + index * 0.06),
        drift + index * 0.53,
        0,
        Math.PI * 2,
      );
      context.strokeStyle = `rgba(${index % 2 ? "133, 174, 255" : "80, 235, 255"}, ${0.08 + index * 0.02})`;
      context.lineWidth = 0.85;
      context.stroke();
    }

    for (const particle of particles) {
      particle.angle += particle.speed * delta;
      const wave = Math.sin(time * 0.00042 + particle.phase) * 0.014;
      const r = radius * (particle.orbit + wave);
      const angle = particle.angle + particle.orbit * 1.65;
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r * 0.72;
      const tailLength = 4 + particle.size * 4;
      const tangent = angle + Math.PI * 0.5;
      const alpha = 0.32 + (Math.sin(time * 0.0011 + particle.phase) + 1) * 0.28;

      context.beginPath();
      context.moveTo(x - Math.cos(tangent) * tailLength, y - Math.sin(tangent) * tailLength * 0.72);
      context.lineTo(x, y);
      context.strokeStyle = `hsla(${particle.hue}, 100%, 78%, ${alpha * 0.82})`;
      context.lineWidth = Math.max(0.65, particle.size * 0.82);
      context.stroke();

      context.beginPath();
      context.arc(x, y, particle.size * (0.72 + alpha * 0.52), 0, Math.PI * 2);
      context.fillStyle = `hsla(${particle.hue}, 100%, 88%, ${alpha})`;
      context.fill();
    }

    context.globalCompositeOperation = "source-over";
    if (!motionPreference.matches) frame = requestAnimationFrame(draw);
  }

  function resize(): void {
    const bounds = canvasElement.getBoundingClientRect();
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
    width = bounds.width;
    height = bounds.height;
    canvasElement.width = Math.round(width * pixelRatio);
    canvasElement.height = Math.round(height * pixelRatio);
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    previousTime = 0;
    stop();
    if (width && height) draw(performance.now());
  }

  function onVisibilityChange(): void {
    if (document.hidden) {
      stop();
      return;
    }
    if (!motionPreference.matches && !frame) frame = requestAnimationFrame(draw);
  }

  function onMotionPreferenceChange(): void {
    previousTime = 0;
    stop();
    draw(performance.now());
  }

  const observer = new ResizeObserver(resize);
  observer.observe(canvasElement);
  motionPreference.addEventListener("change", onMotionPreferenceChange);
  document.addEventListener("visibilitychange", onVisibilityChange);
  resize();

  return () => {
    stop();
    observer.disconnect();
    motionPreference.removeEventListener("change", onMotionPreferenceChange);
    document.removeEventListener("visibilitychange", onVisibilityChange);
  };
}
</script>

<template>
  <div class="login-page h-full overflow-y-auto">
    <div class="grid min-h-[100dvh] md:grid-cols-[0.82fr_1.18fr] lg:grid-cols-[1.06fr_0.94fr]">
      <section class="visual-panel relative hidden overflow-hidden p-12 md:flex md:flex-col xl:p-16">
        <div class="visual-grid" aria-hidden="true" />
        <div class="visual-glow visual-glow-a" aria-hidden="true" />
        <div class="visual-glow visual-glow-b" aria-hidden="true" />
        <div class="visual-ring visual-ring-a" aria-hidden="true" />
        <div class="visual-ring visual-ring-b" aria-hidden="true" />

        <div class="login-art-wrap relative z-10 flex flex-1 items-center justify-center" aria-hidden="true">
          <canvas ref="particleCanvas" class="particle-canvas" />
        </div>
      </section>

      <section class="relative flex min-h-[100dvh] flex-col bg-[#fbfcfd]">
        <div class="flex items-center justify-between px-6 pt-6 sm:px-10">
          <RouterLink to="/agent" class="flex items-center gap-2.5 md:hidden">
            <BrandMark :size="29" />
            <span class="text-[14px] font-semibold tracking-tight text-ink-900">缺页中断</span>
          </RouterLink>
        </div>

        <div class="flex flex-1 items-center justify-center px-6 pb-10 pt-8 sm:px-10 sm:pt-4">
          <div class="w-full max-w-[420px] animate-fade-up">
            <img
              :src="brandLogo"
              alt="缺页中断 标志"
              class="mx-auto mb-3 h-auto w-[210px] object-contain sm:w-[250px]"
            />
            <span class="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-accent-600">
              <Sparkles :size="12" />
              Secure entry
            </span>
            <h1 class="mt-3 text-[30px] font-medium tracking-[-0.04em] text-ink-900 sm:text-[34px]">
              进入你的专属空间
            </h1>
            <p class="mt-2.5 text-[12.5px] leading-6 text-ink-500">
              登录后即可使用个人工作台与 AI 对话；公开文件中转站无需账号，打开即传。
            </p>

            <div
              v-if="maintenance?.enabled"
              role="status"
              class="mt-6 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50/90 px-4 py-3.5"
            >
              <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-amber-100 text-amber-600">
                <Wrench :size="15" />
              </span>
              <div class="min-w-0">
                <p class="text-[12px] font-semibold text-amber-800">系统维护中</p>
                <p class="mt-0.5 text-[10.5px] leading-5 text-amber-700">
                  {{ maintenance?.reason || "站点暂时关闭登录，仅最高管理员可进入。" }}
                  其他账号请稍后再试。
                </p>
              </div>
            </div>

            <div
              v-if="auth.isAuthenticated && auth.user"
              class="mt-6 rounded-2xl border border-slate-200/80 bg-white p-3.5 shadow-sm"
            >
              <div class="flex items-center gap-3">
                <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent-600 text-[13px] font-semibold text-white">
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

              <RouterLink
                to="/transfer"
                class="flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white text-[12px] font-semibold text-ink-700 shadow-sm transition duration-200 hover:border-accent-300 hover:bg-accent-50"
              >
                <ArrowLeft :size="14" />
                免密中转站
              </RouterLink>

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

            <div class="mt-6 flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-[10px] text-ink-400">
              <button type="button" class="underline underline-offset-2 transition hover:text-ink-700" @click="termsOpen = true">
                使用声明
              </button>
              <button
                v-if="announcements.hasAny || announcements.hasHistory"
                type="button"
                class="underline underline-offset-2 transition hover:text-ink-700"
                @click="openAnnouncement"
              >
                公告与历史
              </button>
            </div>
          </div>
        </div>

        <SiteFooter />
      </section>
    </div>

    <UsageTermsModal :open="termsOpen" @close="termsOpen = false" />

    <ModalShell
      :open="announcementOpen"
      title="公告"
      subtitle="当前公告与历史记录"
      max-width="max-w-lg"
      @close="announcementOpen = false"
    >
      <AnnouncementBody />
      <template #footer>
        <button type="button" class="btn-primary" @click="announcementOpen = false">
          我知道了
        </button>
      </template>
    </ModalShell>
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

.login-art-wrap {
  min-height: 360px;
  isolation: isolate;
}

.login-art-wrap::before,
.login-art-wrap::after {
  position: absolute;
  left: 50%;
  top: 50%;
  content: "";
  pointer-events: none;
  transform: translate(-50%, -50%);
}

.login-art-wrap::before {
  width: min(68%, 520px);
  aspect-ratio: 1;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(34, 211, 238, 0.24), rgba(59, 130, 246, 0.14) 34%, rgba(99, 102, 241, 0.07) 53%, transparent 72%);
  filter: blur(18px);
  animation: particle-bloom 8s ease-in-out infinite alternate;
}

.login-art-wrap::after {
  width: min(76%, 590px);
  aspect-ratio: 1.72;
  border: 1px solid rgba(119, 194, 255, 0.17);
  border-radius: 50%;
  box-shadow: 0 0 65px rgba(34, 211, 238, 0.08), inset 0 0 65px rgba(99, 102, 241, 0.06);
  transform: translate(-50%, -50%) rotate(-23deg);
}

.particle-canvas {
  position: absolute;
  inset: 0;
  z-index: 1;
  width: 100%;
  height: 100%;
  overflow: visible;
}

@keyframes particle-bloom {
  from { opacity: 0.65; scale: 0.9; }
  to { opacity: 1; scale: 1.08; }
}

@media (prefers-reduced-motion: reduce) {
  .login-art-wrap::before {
    animation: none;
  }
}
</style>
