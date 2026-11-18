import { defineStore } from "pinia";
import { ref } from "vue";

const COLLAPSE_KEY = "nexus.sidebar.collapsed";

export const useUiStore = defineStore("ui", () => {
  const sidebarCollapsed = ref(localStorage.getItem(COLLAPSE_KEY) === "1");
  const sidebarOpen = ref(false);
  const copilotOpen = ref(window.innerWidth >= 1280);
  const commandPaletteOpen = ref(false);

  function toggleSidebar(): void {
    sidebarCollapsed.value = !sidebarCollapsed.value;
    localStorage.setItem(COLLAPSE_KEY, sidebarCollapsed.value ? "1" : "0");
  }

  function openMobileSidebar(): void {
    sidebarOpen.value = true;
  }

  function closeMobileSidebar(): void {
    sidebarOpen.value = false;
  }

  function toggleCopilot(): void {
    copilotOpen.value = !copilotOpen.value;
  }

  function openCommandPalette(): void {
    commandPaletteOpen.value = true;
  }

  function closeCommandPalette(): void {
    commandPaletteOpen.value = false;
  }

  return {
    sidebarCollapsed,
    sidebarOpen,
    copilotOpen,
    commandPaletteOpen,
    toggleSidebar,
    openMobileSidebar,
    closeMobileSidebar,
    toggleCopilot,
    openCommandPalette,
    closeCommandPalette,
  };
});