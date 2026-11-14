import { fileExtension } from "./format";

export type PreviewKind =
  | "image"
  | "pdf"
  | "markdown"
  | "text"
  | "audio"
  | "video"
  | "none";

const IMAGE_EXT = new Set(["png", "jpg", "jpeg", "webp", "gif"]);
const PDF_EXT = new Set(["pdf"]);
const MARKDOWN_EXT = new Set(["md", "markdown"]);
const TEXT_EXT = new Set(["txt", "csv", "json", "log", "yml", "yaml", "ini", "conf"]);
const AUDIO_EXT = new Set(["mp3", "wav", "ogg", "m4a", "flac"]);
const VIDEO_EXT = new Set(["mp4", "webm", "ogv", "mov", "m4v"]);

/** Text previews are capped to keep the browser responsive. */
export const MAX_TEXT_PREVIEW_BYTES = 2 * 1024 * 1024;

export const PREVIEW_LABEL: Record<PreviewKind, string> = {
  image: "图片预览",
  pdf: "PDF 预览",
  markdown: "Markdown 预览",
  text: "文本预览",
  audio: "音频播放",
  video: "视频播放",
  none: "不支持预览",
};

/**
 * Decide how a file can be previewed in-browser. SVG is deliberately excluded:
 * it can carry scripts and is only offered as a download.
 */
export function previewKind(name: string, mime = "", size = 0): PreviewKind {
  const ext = fileExtension(name);
  if (ext === "svg" || ext === "svgz" || mime === "image/svg+xml") return "none";
  if (IMAGE_EXT.has(ext)) return "image";
  if (PDF_EXT.has(ext)) return "pdf";
  if (MARKDOWN_EXT.has(ext)) return size > MAX_TEXT_PREVIEW_BYTES ? "none" : "markdown";
  if (TEXT_EXT.has(ext) || mime.startsWith("text/")) {
    return size && size > MAX_TEXT_PREVIEW_BYTES ? "none" : "text";
  }
  if (AUDIO_EXT.has(ext) || mime.startsWith("audio/")) return "audio";
  if (VIDEO_EXT.has(ext) || mime.startsWith("video/")) return "video";
  return "none";
}
