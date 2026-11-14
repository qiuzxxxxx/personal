import axios from "axios";
import api from "./client";
import type { LibraryMaterial } from "./workspace";

export interface UploadQuota {
  max_files: number;
  max_bytes: number;
  max_file_bytes: number;
  reserved_files: number;
  reserved_bytes: number;
  committed_files: number;
  committed_bytes: number;
}

export interface UploadSessionPayload {
  id: string;
  state: "active" | "revoked" | "closed";
  expires_at: string;
  created_at: string;
  revoked_at: string | null;
  quota: UploadQuota;
  destination: {
    folder_id: string | null;
    folder_name: string;
    task_id: string | null;
    task_title: string;
  };
  token?: string;
  qr_payload?: string;
  qr_warning?: string;
  receipts?: UploadReceiptPayload[];
  materials?: LibraryMaterial[];
}

export interface UploadReceiptPayload {
  id: string;
  client_upload_id: string;
  original_name: string;
  declared_size: number;
  actual_size: number;
  sha256: string;
  state: "reserved" | "receiving" | "committed" | "failed" | "expired";
  failure_code: string;
  material_id: string | null;
  created_at: string;
  updated_at: string;
  material?: LibraryMaterial;
}

/** Owner side: create, inspect and revoke a phone upload session. */
export async function createUploadSession(options: {
  folder?: string;
  task?: string;
} = {}): Promise<UploadSessionPayload> {
  const { data } = await api.post<UploadSessionPayload>("/upload/sessions/", options);
  return data;
}

export async function fetchUploadSession(id: string): Promise<UploadSessionPayload> {
  const { data } = await api.get<UploadSessionPayload>(`/upload/sessions/${id}/`);
  return data;
}

export async function revokeUploadSession(id: string): Promise<UploadSessionPayload> {
  const { data } = await api.post<UploadSessionPayload>(`/upload/sessions/${id}/revoke/`);
  return data;
}

/** Phone side: a dedicated client that never carries the account token. */
const uploadClient = axios.create({
  baseURL: "/api/upload",
  headers: { "Content-Type": "application/json" },
});

uploadClient.interceptors.request.use((config) => {
  const token = (config as { uploadToken?: string }).uploadToken;
  if (token) {
    config.headers.set?.("Authorization", `Upload ${token}`);
  }
  return config;
});

export async function fetchPhoneSession(token: string): Promise<UploadSessionPayload> {
  const response = await uploadClient.get<UploadSessionPayload>("/phone/session/", {
    uploadToken: token,
  } as never);
  return response.data;
}

export async function prepareReceipt(
  token: string,
  payload: { client_upload_id: string; original_name: string; declared_size: number },
): Promise<UploadReceiptPayload> {
  const response = await uploadClient.post<UploadReceiptPayload>("/phone/receipts/", payload, {
    uploadToken: token,
  } as never);
  return response.data;
}

export function uploadReceiptContent(
  token: string,
  receiptId: string,
  file: File,
  onProgress: (percent: number) => void,
): Promise<UploadReceiptPayload> {
  const form = new FormData();
  form.append("file", file);
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `/api/upload/phone/receipts/${receiptId}/content/`);
    request.setRequestHeader("Authorization", `Upload ${token}`);
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        try {
          resolve(JSON.parse(request.responseText) as UploadReceiptPayload);
        } catch (error) {
          reject(error);
        }
      } else {
        let detail = `上传失败（${request.status}）`;
        try {
          const parsed = JSON.parse(request.responseText);
          detail = parsed.detail || detail;
        } catch {
          // keep the generic message
        }
        reject(new Error(detail));
      }
    };
    request.onerror = () => reject(new Error("网络中断，上传失败。"));
    request.send(form);
  });
}
