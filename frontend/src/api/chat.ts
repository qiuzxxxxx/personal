import api from "./client";
import type { ChatMessage } from "@/types";

/** @deprecated 旧聊天接口保留兼容，新留言板使用下方 BBS 函数 */
export interface ChatContact { username: string; name: string }

export async function getChatContacts(): Promise<ChatContact[]> {
  const { data } = await api.get<{ contacts: ChatContact[] }>("/chat/contacts/");
  return data.contacts;
}

export async function getChatMessages(withUser: string): Promise<ChatMessage[]> {
  const { data } = await api.get<ChatMessage[]>("/chat/messages/", { params: { with: withUser } });
  return data;
}

export async function getChatUnreadCount(): Promise<number> {
  const { data } = await api.get<{ count: number }>("/chat/unread/");
  return Math.max(0, Number(data.count) || 0);
}

export async function markChatRead(): Promise<void> {
  await api.post("/chat/read/");
}

export async function sendChatMessage(content: string, withUser: string): Promise<ChatMessage> {
  const { data } = await api.post<ChatMessage>(
    "/chat/messages/",
    { content },
    { params: { with: withUser } },
  );
  return data;
}

export async function deleteChatMessage(id: string): Promise<void> {
  await api.delete(`/chat/messages/${id}/`, { params: { scope: "self" } });
}

export async function clearChatMessages(withUser: string): Promise<void> {
  await api.delete("/chat/messages/clear/", { params: { with: withUser, scope: "self" } });
}

export async function uploadChatFile(
  file: File,
  content = "",
  onProgress?: (percent: number) => void,
  withUser = "qzx",
): Promise<ChatMessage> {
  const form = new FormData();
  form.append("file", file);
  form.append("content", content);
  const { data } = await api.post<ChatMessage>("/chat/files/", form, {
    params: { with: withUser },
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (event) => {
      if (!onProgress) return;
      const total = event.total || file.size;
      if (total > 0) onProgress(Math.round((event.loaded / total) * 100));
    },
  });
  return data;
}

// ---------------------------------------------------------------------------
// 留言板（贴吧式）—— BBSPost / BBSReply
// ---------------------------------------------------------------------------

export interface BBSPostListItem {
  id: string;
  author_username: string;
  author_name: string;
  title: string;
  content: string;
  visibility: "public" | "private";
  visible_to: string[];
  file_name: string;
  file_size: number;
  file_type: string;
  is_image: boolean;
  file_url: string;
  reply_count: number;
  last_reply_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface BBSReplyItem {
  id: string;
  author_username: string;
  author_name: string;
  content: string;
  file_name: string;
  file_size: number;
  file_type: string;
  is_image: boolean;
  file_url: string;
  created_at: string;
}

export interface BBSPostDetail extends BBSPostListItem {
  replies: BBSReplyItem[];
}

/** 获取帖子列表（公开 + 自己可见的） */
export async function getBbsPosts(): Promise<BBSPostListItem[]> {
  const { data } = await api.get<BBSPostListItem[]>("/chat/bbs/posts/");
  return data;
}

/** 获取帖子详情（含回复列表） */
export async function getBbsPost(postId: string): Promise<BBSPostDetail> {
  const { data } = await api.get<BBSPostDetail>(`/chat/bbs/posts/${postId}/`);
  return data;
}

/** 发帖（可带附件） */
export async function createBbsPost(
  payload: { title?: string; content: string; visibility?: "public" | "private"; visible_to?: string[] },
  file?: File,
): Promise<BBSPostDetail> {
  const form = new FormData();
  form.append("title", payload.title || "");
  form.append("content", payload.content);
  form.append("visibility", payload.visibility || "public");
  if (payload.visible_to?.length) {
    for (const u of payload.visible_to) {
      form.append("visible_to", u);
    }
  }
  if (file) {
    form.append("file", file);
  }
  const { data } = await api.post<BBSPostDetail>("/chat/bbs/posts/", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

/** 删除帖子（仅作者或管理员） */
export async function deleteBbsPost(postId: string): Promise<void> {
  await api.delete(`/chat/bbs/posts/${postId}/`);
}

/** 给帖子添加回复（可带附件） */
export async function addBbsReply(
  postId: string,
  content: string,
  file?: File,
): Promise<BBSReplyItem> {
  const form = new FormData();
  form.append("content", content);
  if (file) {
    form.append("file", file);
  }
  const { data } = await api.post<BBSReplyItem>(`/chat/bbs/posts/${postId}/replies/`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

/** 删除自己的回复 */
export async function deleteBbsReply(postId: string, replyId: string): Promise<void> {
  await api.delete(`/chat/bbs/posts/${postId}/replies/${replyId}/`);
}
