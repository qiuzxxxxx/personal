import type { ApiConfig, ProviderId } from "@/types";

export interface ProviderPreset {
  id: ProviderId;
  name: string;
  eyebrow: string;
  description: string;
  base_url: string;
  model: string;
  protocol: "OpenAI 兼容" | "Gemini 原生" | "Claude 原生" | "自定义";
}

export const PROVIDERS: ProviderPreset[] = [
  {
    id: "openai",
    name: "OpenAI",
    eyebrow: "GPT",
    description: "GPT 系列与 OpenAI 兼容网关",
    base_url: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
    protocol: "OpenAI 兼容",
  },
  {
    id: "gemini",
    name: "Gemini",
    eyebrow: "Google",
    description: "原生 Google AI Studio 接口",
    base_url: "https://generativelanguage.googleapis.com/v1beta",
    model: "gemini-2.5-flash",
    protocol: "Gemini 原生",
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    eyebrow: "深度求索",
    description: "deepseek-flash 原生多模态（文本 + 图像）",
    base_url: "https://api.deepseek.com",
    model: "deepseek-flash",
    protocol: "OpenAI 兼容",
  },
  {
    id: "claude",
    name: "Claude",
    eyebrow: "Anthropic",
    description: "Claude 原生 Messages API",
    base_url: "https://api.anthropic.com/v1",
    model: "claude-sonnet-4-20250514",
    protocol: "Claude 原生",
  },
  {
    id: "custom",
    name: "自定义",
    eyebrow: "Gateway",
    description: "任意 OpenAI 兼容自建服务",
    base_url: "",
    model: "",
    protocol: "自定义",
  },
];

export const DEFAULT_API_CONFIG: ApiConfig = {
  provider: "deepseek",
  base_url: "https://api.deepseek.com",
  model: "deepseek-flash",
  system_prompt: "",
};

export function providerById(id: ProviderId): ProviderPreset {
  return PROVIDERS.find((item) => item.id === id) || PROVIDERS[0];
}

export function providerLabel(id: ProviderId): string {
  return providerById(id).name;
}