import api from "./client";
import type { PagedResult, ReviewCard, ReviewGrade } from "@/types";

export interface KnowledgeCollection {
  id: string;
  name: string;
  description: string;
  project: string | null;
  project_name: string;
  document_count: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export type KnowledgeIndexStatus =
  | "pending"
  | "processing"
  | "ready"
  | "failed"
  | "needs_ocr"
  | "stale";

export interface KnowledgeDocument {
  id: string;
  title: string;
  collection: string | null;
  collection_name: string;
  source_type: "manual" | "material" | "journal_entry" | "ai_message";
  source_label: string;
  content_origin: "user_authored" | "source_snapshot" | "ai_generated";
  ai_enabled: boolean;
  manual_body: string;
  source_title: string;
  source_date: string | null;
  index_status: KnowledgeIndexStatus;
  chunk_count: number;
  current_revision: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeMatch {
  source_id: string;
  document_id: string;
  title: string;
  collection_id: string;
  revision_no: number;
  heading_path: string;
  page_start: number | null;
  page_end: number | null;
  char_start: number | null;
  char_end: number | null;
  score: number;
  reason: string;
  matched_terms: string[];
  text: string;
}

export interface KnowledgeSearchResult {
  matches: KnowledgeMatch[];
  source_refs: string[];
  index_warnings: string[];
  scope: string | string[];
  count: number;
}

export type MemoryStatus = "suggested" | "active" | "disabled" | "superseded" | "forgotten";

export interface PersonalMemory {
  id: string;
  key: string;
  content: string;
  kind: "fact" | "preference" | "goal";
  scope_type: "global" | "project";
  project: string | null;
  project_name: string;
  status: MemoryStatus;
  evidence_type: "user_explicit" | "inferred";
  source_ref: string;
  confirmed_at: string | null;
  valid_from: string | null;
  valid_until: string | null;
  version: number;
  created_at: string;
  updated_at: string;
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

export async function fetchCollections(): Promise<KnowledgeCollection[]> {
  const { data } = await api.get<PagedResult<KnowledgeCollection>>(
    "/knowledge/collections/",
    { params: { page_size: 100 } },
  );
  return data.results;
}

export async function createCollection(payload: {
  name: string;
  description?: string;
  project?: string | null;
}): Promise<KnowledgeCollection> {
  const { data } = await api.post<KnowledgeCollection>("/knowledge/collections/", payload);
  return data;
}

export async function deleteCollection(id: string): Promise<KnowledgeCollection> {
  const { data } = await api.delete<KnowledgeCollection>(`/knowledge/collections/${id}/`);
  return data;
}

export async function fetchDocuments(query: {
  collection?: string;
  q?: string;
  source_type?: string;
  deleted?: boolean;
  page_size?: number;
  page?: number;
} = {}): Promise<PagedResult<KnowledgeDocument>> {
  const params: Record<string, unknown> = {};
  if (query.collection) params.collection = query.collection;
  if (query.q) params.q = query.q;
  if (query.source_type) params.source_type = query.source_type;
  if (query.deleted) params.deleted = "true";
  if (query.page) params.page = query.page;
  params.page_size = query.page_size ?? 100;
  if (query.page) params.page = query.page;
  const { data } = await api.get<PagedResult<KnowledgeDocument>>("/knowledge/documents/", {
    params,
  });
  return data;
}

export async function createDocument(payload: {
  title: string;
  collection?: string | null;
  manual_body?: string;
  ai_enabled?: boolean;
}): Promise<KnowledgeDocument> {
  const { data } = await api.post<KnowledgeDocument>("/knowledge/documents/", payload);
  return data;
}

export async function updateDocument(
  id: string,
  payload: {
    title?: string;
    collection?: string | null;
    manual_body?: string;
    ai_enabled?: boolean;
    version: number;
  },
): Promise<KnowledgeDocument> {
  const { data } = await api.patch<KnowledgeDocument>(`/knowledge/documents/${id}/`, payload);
  return data;
}

export async function deleteDocument(id: string): Promise<KnowledgeDocument> {
  const { data } = await api.delete<KnowledgeDocument>(`/knowledge/documents/${id}/`);
  return data;
}

export async function restoreDocument(id: string): Promise<KnowledgeDocument> {
  const { data } = await api.post<KnowledgeDocument>(`/knowledge/documents/${id}/restore/`);
  return data;
}

export async function purgeDocument(id: string): Promise<void> {
  await api.post(`/knowledge/documents/${id}/purge/`);
}

export async function reindexDocument(id: string): Promise<KnowledgeDocument> {
  const { data } = await api.post<{ document: KnowledgeDocument }>(
    `/knowledge/documents/${id}/reindex/`,
  );
  return data.document;
}

export async function importKnowledge(payload: {
  collection?: string | null;
  material?: string;
  entry?: string;
  message?: string;
  title?: string;
  ai_enabled?: boolean;
}): Promise<KnowledgeDocument> {
  const { data } = await api.post<KnowledgeDocument>(
    "/knowledge/documents/import/",
    payload,
  );
  return data;
}

export async function searchKnowledge(payload: {
  query: string;
  scope?: "all" | "collections";
  collection_ids?: string[];
  limit?: number;
}): Promise<KnowledgeSearchResult> {
  const { data } = await api.post<KnowledgeSearchResult>("/knowledge/search/", payload);
  return data;
}

export async function fetchMemories(query: {
  status?: MemoryStatus;
  page_size?: number;
  page?: number;
} = {}): Promise<PagedResult<PersonalMemory>> {
  const params: Record<string, unknown> = {};
  if (query.status) params.status = query.status;
  params.page_size = query.page_size ?? 100;
  if (query.page) params.page = query.page;
  const { data } = await api.get<PagedResult<PersonalMemory>>("/knowledge/memories/", {
    params,
  });
  return data;
}

export async function createMemory(payload: {
  key: string;
  content: string;
  kind?: "fact" | "preference" | "goal";
  scope_type?: "global" | "project";
  project?: string | null;
  evidence_type?: "user_explicit" | "inferred";
  source_ref?: string;
}): Promise<PersonalMemory> {
  const { data } = await api.post<PersonalMemory>("/knowledge/memories/", payload);
  return data;
}

export async function updateMemory(
  id: string,
  payload: {
    content?: string;
    kind?: "fact" | "preference" | "goal";
    scope_type?: "global" | "project";
    project?: string | null;
    version: number;
  },
): Promise<PersonalMemory> {
  const { data } = await api.patch<PersonalMemory>(`/knowledge/memories/${id}/`, payload);
  return data;
}

export async function acceptMemory(id: string, version: number): Promise<PersonalMemory> {
  const { data } = await api.post<PersonalMemory>(`/knowledge/memories/${id}/accept/`, {
    version,
  });
  return data;
}

export async function disableMemory(id: string, version: number): Promise<PersonalMemory> {
  const { data } = await api.post<PersonalMemory>(`/knowledge/memories/${id}/disable/`, {
    version,
  });
  return data;
}

export async function forgetMemory(id: string, version: number): Promise<PersonalMemory> {
  const { data } = await api.post<PersonalMemory>(`/knowledge/memories/${id}/forget/`, {
    version,
  });
  return data;
}

export async function deleteMemory(id: string, version: number): Promise<void> {
  await api.delete(`/knowledge/memories/${id}/`, { data: { version } });
}

export async function fetchCitation(id: string): Promise<{
  id: string;
  status: "available" | "source_updated" | "unavailable";
  source_id: string;
  source_type?: string;
  title?: string;
  document_id?: string;
  revision_no?: number;
  heading_path?: string;
  page_start?: number | null;
  page_end?: number | null;
  text?: string;
  detail?: string;
}> {
  const { data } = await api.get(`/knowledge/citations/${id}/`);
  return data;
}

export async function exportKnowledge(): Promise<{
  exported_at: string;
  context_epoch: number;
  collections: { id: string; name: string }[];
  documents: Record<string, unknown>[];
  memories: Record<string, unknown>[];
}> {
  const { data } = await api.get("/knowledge/export/");
  return data;
}

export async function fetchReviewCards(): Promise<ReviewCard[]> {
  const { data } = await api.get<ReviewCard[]>("/knowledge/reviews/");
  return data;
}

export async function createReviewCard(payload: {
  front: string;
  back: string;
  tag?: string;
  document?: string | null;
}): Promise<ReviewCard> {
  const { data } = await api.post<ReviewCard>("/knowledge/reviews/", payload);
  return data;
}

export async function gradeReviewCard(
  id: string,
  grade: ReviewGrade,
  version?: number,
): Promise<ReviewCard> {
  const { data } = await api.post<ReviewCard>(`/knowledge/reviews/${id}/grade/`, {
    grade,
    version,
  });
  return data;
}
