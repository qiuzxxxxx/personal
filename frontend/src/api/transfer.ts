import api from "./client";
import type { TransferFile } from "@/types";

export interface UploadTransferPayload {
  file: File;
  isPublic: boolean;
  remark?: string;
  uploaderName?: string;
}

export async function listTransferFiles(): Promise<TransferFile[]> {
  const { data } = await api.get<TransferFile[]>("/transfer/files/");
  return data;
}

export async function uploadTransferFile(
  payload: UploadTransferPayload,
  onProgress?: (percent: number) => void,
): Promise<TransferFile> {
  const form = new FormData();
  form.append("file", payload.file);
  form.append("is_public", payload.isPublic ? "true" : "false");
  if (payload.remark) form.append("remark", payload.remark);
  if (payload.uploaderName) form.append("uploader_name", payload.uploaderName);

  const { data } = await api.post<TransferFile>("/transfer/files/", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (event) => {
      if (!onProgress) return;
      const total = event.total || payload.file.size;
      if (total > 0) onProgress(Math.round((event.loaded / total) * 100));
    },
  });
  return data;
}

export async function patchTransferFile(
  id: string,
  patch: Partial<Pick<TransferFile, "original_name" | "remark" | "is_public">>,
): Promise<TransferFile> {
  const { data } = await api.patch<TransferFile>(`/transfer/files/${id}/`, patch);
  return data;
}

export async function deleteTransferFile(id: string): Promise<void> {
  await api.delete(`/transfer/files/${id}/`);
}