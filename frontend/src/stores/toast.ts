import { defineStore } from "pinia";
import { ref } from "vue";

export type ToastKind = "success" | "error" | "info";

export interface ToastItem {
  id: number;
  message: string;
  kind: ToastKind;
}

let sequence = 0;

export const useToastStore = defineStore("toast", () => {
  const items = ref<ToastItem[]>([]);

  function dismiss(id: number): void {
    items.value = items.value.filter((item) => item.id !== id);
  }

  function show(message: string, kind: ToastKind = "info", duration = 3600): number {
    const id = ++sequence;
    items.value.push({ id, message, kind });
    if (duration > 0) {
      window.setTimeout(() => dismiss(id), duration);
    }
    return id;
  }

  function success(message: string): number {
    return show(message, "success");
  }

  function error(message: string): number {
    return show(message, "error", 5000);
  }

  function info(message: string): number {
    return show(message, "info");
  }

  return { items, show, success, error, info, dismiss };
});