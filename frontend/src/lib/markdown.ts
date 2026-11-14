import MarkdownIt from "markdown-it";
import hljs from "highlight.js";
import katex from "katex";

function renderKatex(source: string, displayMode: boolean): string {
  try {
    return katex.renderToString(source, {
      displayMode,
      throwOnError: false,
      strict: false,
      trust: false,
      output: "html",
    });
  } catch {
    return `<span class="math-error">${escapeHtml(source)}</span>`;
  }
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: false,
  highlight(code, language) {
    if (language && hljs.getLanguage(language)) {
      try {
        return hljs.highlight(code, { language, ignoreIllegals: true }).value;
      } catch {
        return "";
      }
    }
    return "";
  },
});

// Inline $...$ and $$...$$ math. Registered after backticks so code spans win.
md.inline.ruler.after("backticks", "math_inline", (state: any, silent: boolean) => {
  const start = state.pos;
  const src = state.src as string;
  if (src[start] !== "$") return false;
  const display = src[start + 1] === "$";
  const marker = display ? "$$" : "$";
  let cursor = start + marker.length;
  let close = -1;
  while (cursor < src.length) {
    if (src[cursor] === "\\") {
      cursor += 2;
      continue;
    }
    if (src.startsWith(marker, cursor)) {
      close = cursor;
      break;
    }
    cursor += 1;
  }
  if (close < 0) return false;
  if (!display && close === start + 1) return false;
  const content = src.slice(start + marker.length, close);
  if (!content.trim()) return false;
  if (!silent) {
    const token = state.push("math_inline", "math", 0);
    token.content = content;
    token.markup = marker;
    token.meta = { display };
  }
  state.pos = close + marker.length;
  return true;
});

// Multi-line $$ ... $$ blocks.
md.block.ruler.before(
  "fence",
  "math_block",
  (state: any, startLine: number, endLine: number, silent: boolean) => {
    const start = state.bMarks[startLine] + state.tShift[startLine];
    const max = state.eMarks[startLine];
    const src = state.src as string;
    if (start + 2 > max || src.slice(start, start + 2) !== "$$") return false;
    if (silent) return true;

    let line = startLine;
    let content = "";
    let found = false;
    while (line < endLine) {
      const lineStart = state.bMarks[line] + state.tShift[line];
      const lineEnd = state.eMarks[line];
      let segment = src.slice(lineStart, lineEnd);
      if (line === startLine) segment = segment.slice(2);
      const closeIndex = segment.indexOf("$$");
      if (closeIndex >= 0) {
        content += `${content ? "\n" : ""}${segment.slice(0, closeIndex)}`;
        found = true;
        break;
      }
      content += `${content ? "\n" : ""}${segment}`;
      line += 1;
    }
    if (!found || !content.trim()) return false;

    state.line = line + 1;
    const token = state.push("math_block", "math", 0);
    token.block = true;
    token.content = content.trim();
    token.markup = "$$";
    return true;
  },
  { alt: ["paragraph", "reference", "blockquote", "list"] },
);

md.renderer.rules.math_inline = (tokens, index) =>
  renderKatex(tokens[index].content, Boolean(tokens[index].meta?.display));
md.renderer.rules.math_block = (tokens, index) => {
  const rendered = renderKatex(tokens[index].content, true);
  return `<div class="math-block">${rendered}</div>`;
};

const defaultFence = md.renderer.rules.fence!;
md.renderer.rules.fence = (tokens, index, options, env, self) => {
  const token = tokens[index];
  const language = (token.info || "").trim().split(/\s+/)[0] || "text";
  const highlighted = defaultFence(tokens, index, options, env, self);
  return [
    '<div class="code-shell">',
    '<div class="code-bar">',
    `<span class="code-lang">${escapeHtml(language)}</span>`,
    '<button type="button" class="code-copy">复制</button>',
    "</div>",
    highlighted,
    "</div>",
  ].join("");
};

md.renderer.rules.link_open = (tokens, index, options, env, self) => {
  tokens[index].attrSet("target", "_blank");
  tokens[index].attrSet("rel", "noopener noreferrer");
  return self.renderToken(tokens, index, options);
};

md.renderer.rules.image = (tokens, index, options, env, self) => {
  tokens[index].attrSet("loading", "lazy");
  return self.renderToken(tokens, index, options);
};

export function renderMarkdown(source: string): string {
  if (!source) return "";
  try {
    return md.render(source);
  } catch {
    return `<p>${escapeHtml(source)}</p>`;
  }
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      const ok = document.execCommand("copy");
      area.remove();
      return ok;
    } catch {
      return false;
    }
  }
}