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
      path: "/agent",
      name: "agent",
      component: () => import("@/views/AgentChatView.vue"),
      meta: { title: "AI 对话", requiresAuth: true },
    },
    {
      path: "/chat",
      name: "chat",
      component: () => import("@/views/DirectChatView.vue"),
      meta: { title: "双人密聊", requiresAuth: true },
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
      path: "/:pathMatch(.*)*",
      redirect: "/",
    },
  ],
  scrollBehavior: () => ({ top: 0 }),
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!auth.initialized) {
    await auth.initialize();
  }
  document.title = `${String(to.meta.title || "zixxx")} · zixxx`;
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return {
      path: "/",
      query: { redirect: to.fullPath },
    };
  }
  if (
    auth.isAuthenticated &&
    auth.user?.username === "yk" &&
    (to.path === "/agent" || to.path === "/chat")
  ) {
    return { path: "/transfer" };
  }
  return true;
});

export default router;