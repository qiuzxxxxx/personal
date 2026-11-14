import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";

import "highlight.js/styles/github-dark.css";
import "katex/dist/katex.min.css";
import "./style.css";

const app = createApp(App);
app.use(createPinia());
app.use(router);

router.isReady().then(() => {
  app.mount("#app");
  // Warm the lazy route chunks while idle so the first visit to any section
  // is instant (no dev-server compile wait, no white flash).
  const warm = () => {
    void import("@/views/AgentChatView.vue");
    void import("@/views/DirectChatView.vue");
    void import("@/views/TransferStation.vue");
    void import("@/views/AccountsView.vue");
    void import("@/views/LoginView.vue");
  };
  const idle = (
    window as Window & {
      requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number;
    }
  ).requestIdleCallback;
  if (typeof idle === "function") {
    idle(warm, { timeout: 2500 });
  } else {
    window.setTimeout(warm, 800);
  }
});