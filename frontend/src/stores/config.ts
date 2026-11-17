import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { fetchAgentConfig, saveAgentConfig, type SaveAgentConfigPayload } from "@/api/agent";
import type { ApiConfig, ApiConfigState, ProviderId } from "@/types";
import { DEFAULT_API_CONFIG, providerById } from "@/lib/providers";

/** Old client-side storage key; migrated once to the encrypted server store. */
const LEGACY_STORAGE_KEY = "nexus.api.config.v1";

const EMPTY_STATE: ApiConfigState = {
  ...DEFAULT_API_CONFIG,
  has_key: false,
  key_hint: "",
  updated_at: null,
};

export const useConfigStore = defineStore("config", () => {
  const state = ref<ApiConfigState>({ ...EMPTY_STATE });
  const loaded = ref(false);
  let loading: Promise<void> | null = null;
  let sessionEpoch = 0;

  const config = computed<ApiConfig>(() => ({
    provider: state.value.provider,
    base_url: state.value.base_url,
    model: state.value.model,
    system_prompt: state.value.system_prompt,
  }));
  const isConfigured = computed(() =>
    Boolean(state.value.base_url.trim() && state.value.model.trim()),
  );
  const hasKey = computed(() => state.value.has_key);
  const keyHint = computed(() => state.value.key_hint);

  async function migrateLegacy(): Promise<void> {
    const raw = localStorage.getItem(LEGACY_STORAGE_KEY);
    if (!raw) return;
    localStorage.removeItem(LEGACY_STORAGE_KEY);
    try {
      const legacy = JSON.parse(raw) as Partial<ApiConfig> & { api_key?: string };
      const key = String(legacy.api_key || "").trim();
      if (!key || state.value.has_key) return;
      await save({
        provider: (legacy.provider as ProviderId) || DEFAULT_API_CONFIG.provider,
        base_url: String(legacy.base_url || "").trim(),
        model: String(legacy.model || "").trim(),
        system_prompt: String(legacy.system_prompt || ""),
        api_key: key,
      });
    } catch {
      // A corrupted legacy blob is simply dropped.
    }
  }

  async function load(force = false): Promise<void> {
    if (loading) return loading;
    if (loaded.value && !force) return;
    const epoch = sessionEpoch;
    loading = (async () => {
      try {
        const next = await fetchAgentConfig();
        if (epoch !== sessionEpoch) return;
        state.value = next;
        loaded.value = true;
        await migrateLegacy();
      } catch {
        if (epoch === sessionEpoch) loaded.value = false;
      } finally {
        if (epoch === sessionEpoch) loading = null;
      }
    })();
    return loading;
  }

  async function save(payload: SaveAgentConfigPayload): Promise<ApiConfigState> {
    const epoch = sessionEpoch;
    const next = await saveAgentConfig(payload);
    if (epoch !== sessionEpoch) return next;
    state.value = next;
    loaded.value = true;
    return next;
  }

  function applyPreset(id: ProviderId): void {
    const preset = providerById(id);
    state.value = {
      ...state.value,
      provider: id,
      base_url: preset.base_url,
      model: preset.model,
    };
  }

  function reset(): void {
    sessionEpoch += 1;
    loading = null;
    state.value = { ...EMPTY_STATE };
    loaded.value = false;
  }

  return {
    state,
    config,
    isConfigured,
    hasKey,
    keyHint,
    loaded,
    load,
    save,
    applyPreset,
    reset,
  };
});
