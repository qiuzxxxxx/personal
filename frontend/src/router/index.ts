import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("@/views/LoginView.vue"),
      meta: { title: "登录", bare: true },
    },
    {
      path: "/login",
      redirect: "/",
    },
    {
      path: "/today",
      name: "today",
      component: () => import("@/views/TodayView.vue"),
      meta: { title: "今日", requiresAuth: true },
    },
    {
      path: "/tasks",
      name: "tasks",
      component: () => import("@/views/TasksView.vue"),
      meta: { title: "任务", requiresAuth: true },
    },
    {
      path: "/projects",
      redirect: "/tasks",
    },
    {
      path: "/calendar",
      name: "calendar",
      component: () => import("@/views/CalendarPlanView.vue"),
      meta: { title: "日历与计划", requiresAuth: true },
    },
    {
      path: "/focus",
      name: "focus",
      component: () => import("@/views/FocusStatsView.vue"),
      meta: { title: "专注与统计", requiresAuth: true },
    },
    {
      path: "/reviews",
      name: "reviews",
      component: () => import("@/views/SpacedRepetitionView.vue"),
      meta: { title: "间隔复习", requiresAuth: true },
    },
    {
      path: "/settings",
      name: "settings",
      component: () => import("@/views/WorkspaceConfigView.vue"),
      meta: { title: "工作区配置", requiresAuth: true },
    },
    {
      path: "/journal",
      name: "journal",
      component: () => import("@/views/JournalView.vue"),
      meta: { title: "每日记录", requiresAuth: true },
    },
    {
      path: "/library",
      name: "library",
      component: () => import("@/views/LibraryView.vue"),
      meta: { title: "私人资料库", requiresAuth: true },
    },
    {
      path: "/knowledge",
      name: "knowledge",
      component: () => import("@/views/KnowledgeView.vue"),
      meta: { title: "个人知识库", requiresAuth: true },
    },
    {
      path: "/knowledge/memories",
      name: "knowledge-memories",
      component: () => import("@/views/KnowledgeMemoriesView.vue"),
      meta: { title: "个人记忆", requiresAuth: true },
    },
    {
      path: "/upload",
      name: "phone-upload",
      component: () => import("@/views/MobileUploadView.vue"),
      meta: { title: "手机上传", bare: true },
    },
    {
      path: "/agent",
      name: "agent",
      component: () => import("@/views/AgentChatView.vue"),
      meta: { title: "AI 对话", requiresAuth: true },
    },
    {
      path: "/chat",
      name: "chat",
      component: () => import("@/views/DirectChatView.vue"),
      meta: { title: "聊天", requiresAuth: true },
    },
    {
      path: "/transfer",
      name: "transfer",
      component: () => import("@/views/TransferStation.vue"),
      meta: { title: "文件中转站" },
    },
    {
      path: "/accounts",
      name: "accounts",
      component: () => import("@/views/AccountsView.vue"),
      meta: { title: "账号管理", requiresAuth: true },
    },
    {
      path: "/about",
      name: "about",
      component: () => import("@/views/AboutView.vue"),
      meta: { title: "关于" },
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/",
    },
  ],
  scrollBehavior: () => ({ top: 0 }),
});

// 访客角色只使用免密中转站，不能进入工作台或知识库。
const guestBlockedPaths = [
  "/agent",
  "/today",
  "/tasks",
  "/projects",
  "/journal",
  "/library",
  "/knowledge",
  "/knowledge/memories",
  "/chat",
  "/calendar",
  "/focus",
  "/reviews",
  "/settings",
  "/accounts",
];

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!auth.initialized) {
    await auth.initialize();
  }
  document.title = `${String(to.meta.title || "缺页中断")} · 缺页中断`;
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return {
      path: "/",
      query: { redirect: to.fullPath },
    };
  }
  // 已登录用户访问根路径时进入工作台，访客账号仍进入中转站。
  if (to.path === "/" && auth.isAuthenticated) {
    return { path: auth.isGuest ? "/transfer" : "/today" };
  }
  if (
    auth.isAuthenticated &&
    auth.isGuest &&
    guestBlockedPaths.some((path) => to.path === path || to.path.startsWith(`${path}/`))
  ) {
    return { path: "/transfer" };
  }
  return true;
});

export default router;
