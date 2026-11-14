export type ProviderId = "openai" | "gemini" | "deepseek" | "claude" | "custom";

export interface ApiConfig {
  provider: ProviderId;
  base_url: string;
  model: string;
  system_prompt: string;
}

/** Server-side config state: the key itself never comes back, only a hint. */
export interface ApiConfigState extends ApiConfig {
  has_key: boolean;
  key_hint: string;
  updated_at: string | null;
}

export interface User {
  id: number;
  username: string;
  display_name: string;
  role: string;
  is_qzx: boolean;
  is_admin: boolean;
  is_super: boolean;
  is_chat_user: boolean;
}

export interface AccountInfo {
  username: string;
  role: string;
  is_admin: boolean;
  is_super: boolean;
  is_chat_user: boolean;
  last_login: string | null;
  date_joined: string;
  log_count: number;
}

export interface ActivityLogItem {
  id: number;
  username: string | null;
  actor_username: string | null;
  action: string;
  detail: string;
  ip: string | null;
  created_at: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface AgentAttachmentRef {
  id: string;
  name: string;
  mime: string;
  size: number;
  is_image: boolean;
}

export interface AgentAttachmentUpload {
  id: string;
  original_name: string;
  mime_type: string;
  file_size: number;
  is_image: boolean;
  extension: string;
}

export interface AgentMessageCitation {
  id: string;
  source_id: string;
  source_type: string;
  title: string;
  document_id: string | null;
  revision_no: number;
}

export interface AgentMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  attachments: AgentAttachmentRef[];
  knowledge_sources?: KnowledgeSourceRef[];
  citations?: AgentMessageCitation[];
  created_at: string;
  streaming?: boolean;
  error?: string;
}

export interface KnowledgeSourceRef {
  source_id: string;
  source_type: string;
  title: string;
  document_id: string;
  revision_no: number;
  chunk_id: string;
  heading_path: string;
  page_start: number | null;
  page_end: number | null;
  text: string;
  snapshot: boolean;
}

export interface KnowledgeScope {
  enabled: boolean;
  scope: "all" | "collections";
  collection_ids: string[];
  use_personal_memory: boolean;
  project_id: string | null;
  use_workspace: boolean;
  strict_sources: boolean;
}

export interface ConversationSummary {
  id: string;
  title: string;
  message_count: number;
  last_message: string;
  knowledge_enabled?: boolean;
  knowledge_scope?: "all" | "collections";
  knowledge_collection_ids?: string[];
  use_personal_memory?: boolean;
  use_workspace?: boolean;
  strict_sources?: boolean;
  knowledge_project?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: AgentMessage[];
}

export interface ChatMessage {
  id: string;
  sender_username: string;
  sender_name: string;
  message_type: "text" | "file";
  content: string;
  file_name: string;
  file_size: number;
  file_type: string;
  is_image: boolean;
  file_url: string;
  created_at: string;
}

export interface TransferFile {
  id: string;
  original_name: string;
  file_size: number;
  file_type: string;
  remark: string;
  is_public: boolean;
  uploader_name: string;
  is_image: boolean;
  extension: string;
  download_url: string;
  preview_url: string;
  created_at: string;
  updated_at: string;
}

export interface LocalUploadFile {
  file: File;
  previewUrl: string;
  id: string;
}

export interface AgentStreamMeta {
  type: "meta";
  conversation_id: string;
  title: string;
  user_message: AgentMessage;
  provider: string;
}

export interface AgentStreamDelta {
  type: "delta";
  content: string;
}

export interface AgentStreamDone {
  type: "done";
  message: AgentMessage;
  sources?: KnowledgeSourceRef[];
  context_epoch?: number;
}

export interface AgentStreamSources {
  type: "sources";
  retrieval: {
    knowledge: boolean;
    scope: "all" | "collections";
    collection_ids: string[];
    use_personal_memory: boolean;
    use_workspace: boolean;
    strict_sources: boolean;
  };
  sources: KnowledgeSourceRef[];
  warnings: string[];
  context_epoch: number;
}

export interface AgentStreamError {
  type: "error";
  message: string;
  partial_message: AgentMessage | null;
}

export type AgentStreamEvent =
  | AgentStreamMeta
  | AgentStreamDelta
  | AgentStreamDone
  | AgentStreamSources
  | AgentStreamError;

export type TaskStatus = "todo" | "doing" | "done" | "cancelled";
export type TaskPriority = "low" | "normal" | "high";

export interface WorkspaceTag {
  id: string;
  name: string;
  normalized_name: string;
  color: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceProject {
  id: string;
  name: string;
  description: string;
  status: "active" | "archived";
  color: string;
  position: number;
  version: number;
  task_count: number;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceTask {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  scheduled_date: string | null;
  due_at: string | null;
  completed_at: string | null;
  position: number;
  version: number;
  project: string | null;
  project_name: string;
  project_deleted: boolean;
  tags: WorkspaceTag[];
  created_at: string;
  updated_at: string;
}

export interface WorkspaceJournal {
  id?: string;
  date: string;
  content: string;
  version: number;
  exists: boolean;
}

export interface TodayPayload {
  date: string;
  weekday: string;
  timezone: string;
  tasks: WorkspaceTask[];
  overdue: WorkspaceTask[];
  overdue_count: number;
  needs_reschedule_count: number;
  unscheduled_count: number;
  completed_today: number;
  journal: {
    id: string;
    date: string;
    version: number;
    content: string;
    summary: string;
    updated_at: string;
  } | null;
}

export interface PagedResult<T> {
  results: T[];
  page: number;
  page_size: number;
  count: number;
  pages: number;
}
