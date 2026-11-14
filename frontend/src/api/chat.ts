import api from "./client";
import type { ChatMessage } from "@/types";

export async function getChatMessages(): Promise<ChatMessage[]> {
  const { data } = await api.get<ChatMessage[]>("/chat/messages/");
  return data;
}

export async function sendChatMessage(content: string): Promise<ChatMessage> {
  const { data } = await api.post<ChatMessage>("/chat/messages/", { content });
  return data;
}

export async function uploadChatFile(
  file: File,
  content = "",
  onProgress?: (percent: number) => void,
): Promise<ChatMessage> {
  const form = new FormData();
  form.append("file", file);
  form.append("content", content);
  const { data } = await api.post<ChatMessage>("/chat/files/", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (event) => {
      if (!onProgress) return;
      const total = event.total || file.size;
      if (total > 0) onProgress(Math.round((event.loaded / total) * 100));
    },
  });
  return data;
}