import api, { apiUrl, bearerHeaders } from "./client";
import type {
  AgentAttachmentUpload,
  AgentStreamEvent,
  AgentSuggestion,
  ApiConfig,
  ApiConfigState,
  ConversationDetail,
  ConversationSummary,
} from "@/types";

export interface SaveAgentConfigPayload extends ApiConfig {
  api_key?: string;
  clear_key?: boolean;
}

export async function fetchAgentConfig(): Promise<ApiConfigState> {
  const { data } = await api.get<ApiConfigState>("/agent/config/");
  return data;
}

export async function saveAgentConfig(
  payload: SaveAgentConfigPayload,
): Promise<ApiConfigState> {
  const { data } = await api.put<ApiConfigState>("/agent/config/", payload);
  return data;
}

export async function testAgentConnection(
  payload: Omit<SaveAgentConfigPayload, "system_prompt">,
  signal: AbortSignal,
): Promise<{ latency_ms: number }> {
  const { data } = await api.post<{ latency_ms: number }>("/agent/config/test/", payload, {
    signal,
    timeout: 30000,
  });
  return data;
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const { data } = await api.get<ConversationSummary[]>("/agent/conversations/");
  return data;
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const { data } = await api.get<ConversationDetail>(`/agent/conversations/${id}/`);
  return data;
}

export async function deleteConversation(id: string): Promise<void> {
  await api.delete(`/agent/conversations/${id}/`);
}

export async function fetchAgentSuggestions(): Promise<AgentSuggestion[]> {
  const { data } = await api.get<{ suggestions: AgentSuggestion[] }>("/agent/suggestions/");
  return data.suggestions;
}

export async function uploadAgentAttachment(file: File): Promise<AgentAttachmentUpload> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<AgentAttachmentUpload>("/agent/attachments/", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

interface StreamChatPayload {
  conversation_id?: string | null;
  message: string;
  attachment_ids: string[];
  api_config: Record<string, unknown>;
  knowledge?: Record<string, unknown>;
}

export interface StreamHandlers {
  onEvent: (event: AgentStreamEvent) => void;
  signal?: AbortSignal;
}

export async function streamAgentChat(
  payload: StreamChatPayload,
  { onEvent, signal }: StreamHandlers,
): Promise<void> {
  const response = await fetch(apiUrl("/agent/chat/"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...bearerHeaders(),
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    let message = "发送失败，请稍后再试。";
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
    } catch {
      // Keep the friendly fallback for non-JSON error bodies.
    }
    throw new Error(message);
  }

  if (!response.body) {
    throw new Error("当前浏览器不支持流式响应。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  const dispatch = (block: string) => {
    const data = block
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n")
      .trim();
    if (!data) return;
    try {
      onEvent(JSON.parse(data) as AgentStreamEvent);
    } catch {
      // Ignore malformed keep-alive frames.
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    for (const block of blocks) dispatch(block);
  }
  buffer += decoder.decode();
  if (buffer.trim()) dispatch(buffer);
}
