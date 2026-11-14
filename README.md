# zixxx —— 个人多模态 AI 助手、双人即时通讯与公开文件中转站

一个仿 **Gemini 极简交互风格** 的自托管全栈 Web 应用，采用 **Vue 3 + Django** 架构。**打开主页即登录页**，登录后进入完整空间；集成了**自定义多模态 AI 对话**、**`qzx` 与 `sqx` 专属实时聊天与文件互传**，以及**支持免密上传与可见性控制的 `qzx` 最高管理员管理中转站**。

---

## 一、核心功能矩阵

### 1. Gemini 风格多模态 AI Agent

- **极简对话界面**：左侧可折叠历史会话栏 + 居中悬浮多模态输入框，支持 Markdown 实时流式渲染、代码高亮（highlight.js）与 LaTeX 数学公式（KaTeX，行内 `$...$` 与独立 `$$...$$`）。
- **多模态文件理解**：支持上传 PDF、Word（.docx）、TXT、Markdown 文档及图片（PNG/JPG/WebP）。文档在服务端用 PyMuPDF / python-docx 提取文本注入上下文；图片经服务端缩放编码后以 data-URL 形式随多模态请求发送。
- **自定义 API 配置**：支持 OpenAI、Gemini、DeepSeek、Claude 和 OpenAI 兼容网关。已保存的 API Key 在服务端加密存储，只随请求发送至对应的模型来源。
- **测试连接**：模型设置中的「测试连接」会用当前表单发起一次简短的流式请求，显示首次文本响应耗时或失败原因，无需先保存配置。
- **流式体验**：SSE 流式输出、可随时「停止生成」、失败时保留已生成的部分内容并给出可读错误。
- **登录准入**：AI 对话仅对 `qzx` / `sqx` 开放；游客账号 `yk` 与未登录访客均无法使用，接口直接返回 401/403。

### 2. 双人专属即时通讯（`qzx` ↔ `sqx`）

- **预置专属账号**：`python manage.py init_users` 为新账号和待重新设密的账号生成初始密码，也可从环境变量读取。
- **实时文字与文件互传**：基于 WebSocket（Django Channels，InMemory 层）低延迟推送，支持「正在输入」提示、断线自动重连；聊天窗口中可直接发送文档/图片，图片在线预览、任意文件可下载。WebSocket 不可用时自动回退 REST 发送。

### 3. 免密文件中转站（最高管理员 `qzx` 完全控制权）

- **免密即传（访客模式）**：无需登录，打开中转站页面即可拖拽上传；上传时选择 **「对所有人可见」** 或 **「仅最高管理员 qzx 可见（私密投递）」**，可附备注与署名。
- **可见性权限隔离**：
  - 普通访客 / 未登录用户：仅可上传、查看并下载 `is_public=True` 的文件；无法修改、重命名、切换权限或删除任何文件（私密投递后访客端立即隐藏）。
  - 游客账号 `yk`：登录后可上传，并可浏览「公开文件 + 自己投递的文件」（含自己的私密投递），可下载这些文件；**没有**删除、重命名、修改备注、切换可见性的权限；侧边栏不出现 AI 对话与双人密聊入口。
  - 最高管理员 `qzx`：登录后可查看和下载全部文件、重命名、修改备注、切换可见性和删除文件。
- 文件只通过鉴权下载接口流出，`/media` 目录不对外暴露。

---

## 二、技术栈

| 层级 | 技术选型 | 说明 |
| :--- | :--- | :--- |
| 前端框架 | Vue 3 (Vite) + TypeScript | Composition API，构建快速 |
| UI 与样式 | Tailwind CSS + Lucide Icons | 还原 Gemini 留白质感与响应式侧边栏 |
| 状态与路由 | Pinia + Vue Router | 管理登录态、API 配置及多视图切换 |
| 渲染引擎 | `markdown-it` + `highlight.js` + `KaTeX` | 代码高亮与数学公式渲染 |
| 后端框架 | Django 5 + Django REST Framework | 标准化 RESTful API 与权限控制 |
| 实时通讯 | Django Channels + Daphne (InMemory) | 无需 Redis 即可支持双人实时聊天 |
| 文件解析 | `PyMuPDF` / `python-docx` / `Pillow` | 提取上传文档内容供 AI 阅读 |
| 数据库 | SQLite3 | 单文件零配置，备份迁移极简 |

---

## 三、项目目录结构

```text
zixxx-agent/
├── backend/                        # Django 后端工程
│   ├── config/                     # 全局配置 (settings.py, asgi.py, urls.py)
│   ├── accounts/                   # 用户认证与预置账号初始化
│   │   └── management/commands/init_users.py
│   ├── agent/                      # AI 对话、多模态解析与自定义 API 代理
│   │   ├── llm.py                  # OpenAI / Gemini / Claude 流式适配器
│   │   ├── parsing.py              # PDF / DOCX / TXT / 图片解析与校验
│   │   └── views.py                # 会话、附件上传、SSE 流式对话
│   ├── chat/                       # qzx & sqx 实时通讯与文件互传
│   │   ├── consumers.py            # WebSocket Consumer（鉴权 + 群发）
│   │   └── views.py                # 历史消息、文件上传与下载
│   ├── transfer/                   # 免密文件中转站 (is_public 可见性控制)
│   │   ├── models.py               # TransferFile 模型
│   │   ├── permissions.py          # qzx 专属增删改查权限校验
│   │   └── views.py                # 上传、列表过滤、可见性切换、下载与删除
│   ├── media/                      # 本地文件存储 (chat_files/ & transfer_station/ & agent_uploads/)
│   ├── manage.py
│   ├── requirements.txt
│   ├── smoke_test.py               # 后端接口端到端自检脚本
│   ├── ws_smoke.mjs                # WebSocket 自检脚本 (node)
│   └── seed_demo.py                # 可选：生成演示数据（仅本地视觉验收用）
└── frontend/                       # Vue 3 前端工程
    ├── src/
    │   ├── api/                    # Axios 封装 (自动携带 Token / 会话标识)
    │   ├── components/
    │   │   ├── Sidebar.vue         # Gemini 风格侧边栏 (AI对话 / 双人密聊 / 文件中转站)
    │   │   ├── ApiConfigModal.vue  # 自定义 API Key / BaseURL / 模型配置弹窗
    │   │   ├── MultimodalInput.vue # 支持拖拽上传图片与文档的底部悬浮输入框
    │   │   ├── MarkdownRenderer.vue# Markdown + 代码高亮 + KaTeX + 复制按钮
    │   │   └── ChatFileCard.vue    # 聊天文件卡片（图片预览 / 下载）
    │   ├── views/
    │   │   ├── AgentChatView.vue   # AI Agent 主对话页
    │   │   ├── DirectChatView.vue  # qzx & sqx 互发消息与文档页
    │   │   ├── TransferStation.vue # 免密文件中转站 (qzx 管理栏与可见性开关)
    │   │   └── LoginView.vue       # 登录页 (仅密聊及 qzx 管理中转站时需登录)
    │   ├── stores/                 # Pinia: auth / agent / config / ui / toast
    │   └── router/index.ts
    └── package.json
```

---

## 四、核心数据库与权限设计

### 1. 预置账号

```bash
python manage.py init_users
```

| 用户名 | 密码 | 角色定位 | 权限说明 |
| --- | --- | --- | --- |
| `qzx` | `NEXUS_PASSWORD_QZX` 或随机生成 | **最高管理员**（rank 2） | 与 `sqx` 密聊、使用 AI Agent、管理中转站、重置下级账号密码、查看全部账号日志 |
| `sqx` | `NEXUS_PASSWORD_SQX` 或随机生成 | **管理员**（rank 1） | 与 `qzx` 密聊、使用 AI Agent、重置普通账号密码、查看权限内日志 |
| `yk` | `NEXUS_PASSWORD_YK` 或随机生成 | 游客（rank 0） | 上传文件、浏览公开与自己的文件 |

### 2. 文件中转站模型（`transfer/models.py`）

```python
class TransferFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to='transfer_station/%Y/%m/')
    original_name = models.CharField(max_length=255, verbose_name="文件名")
    file_size = models.BigIntegerField(default=0, verbose_name="文件大小(字节)")
    file_type = models.CharField(max_length=100, blank=True, verbose_name="MIME类型")
    remark = models.CharField(max_length=255, blank=True, default='', verbose_name="备注说明")
    is_public = models.BooleanField(default=True, verbose_name="是否对所有人可见")
    uploader_name = models.CharField(max_length=64, default='免密访客', verbose_name="上传者标识")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
```

### 3. 中转站接口与权限规则

| HTTP 方法 | 接口路径 | 访问权限 | 功能描述 |
| --- | --- | --- | --- |
| `GET` | `/api/transfer/files/` | 免密公开 | 未登录仅返回 `is_public=True`；登录非最高管理员（如 `yk` / `sqx`）返回公开 + 自己投递的文件；`qzx` 返回全部 |
| `POST` | `/api/transfer/files/` | 免密公开 | 无需密码上传，表单字段 `is_public`（公开 / 仅最高管理员可见） |
| `GET` | `/api/transfer/files/<id>/download/` | 条件公开 | 公开文件人人可下载；私密文件仅上传者与 `qzx` |
| `PATCH` | `/api/transfer/files/<id>/` | 仅 `qzx` | 修改文件名、备注或切换可见性 |
| `DELETE` | `/api/transfer/files/<id>/` | 仅 `qzx` | 删除记录并同步清理磁盘物理文件 |

聊天客户端在 `/ws/chat/` 握手时通过 `Sec-WebSocket-Protocol` 提交 `zixxx.chat, token.<token>`，服务端只回显 `zixxx.chat`。反向代理应避免记录认证相关请求头。

---

## 五、快速启动指南

### 1. 启动后端 (Django)

```bash
cd backend
python -m venv venv
# Windows 激活: venv\Scripts\activate  |  Linux/macOS 激活: source venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py init_users

# 启动支持 WebSocket 的 ASGI 服务（默认 8000 端口）
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

### 2. 启动前端 (Vue 3)

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173`：

- **主页即登录页**：打开 `/` 直接进入登录页；登录成功后按角色进入空间（`qzx` / `sqx` → AI 对话，`yk` → 中转站）；
- 左侧 **「文件中转站」** 可**免密直接上传/下载公开文件**；
- 登录 `qzx` 后，中转站解锁「公开/私密切换」「重命名 / 备注」「删除」；
- 登录 `qzx` 或 `sqx` 进入双人实时聊天，并解锁 AI 对话与「账号管理」（按层级重置下级账号密码、查看下级账号操作日志）；
- 游客账号 `yk` 可上传与浏览中转站（含自己的私密投递）；
- 未登录访问 `/agent`、`/chat`、`/accounts` 会自动跳回主页登录页。

> 前端开发服务器默认把 `/api` 与 `/ws` 代理到 `http://127.0.0.1:8000`。若后端跑在其他端口，用环境变量覆盖：
> `VITE_PROXY_TARGET=http://127.0.0.1:8001 npm run dev`

### 3. 可选：本地演示与自检

```bash
# 生成演示数据（中转站文件 / 聊天记录 / 一条含公式与代码的 AI 会话）
cd backend && python seed_demo.py

# 后端接口端到端自检（用测试账号，设置对应的 NEXUS_PASSWORD_* 环境变量）
python smoke_test.py http://127.0.0.1:8000

# WebSocket 自检（需要 Node.js 24）
node ws_smoke.mjs
```

仓库内 `.tools/mock-llm.cjs` 是一个本地 OpenAI 兼容流式 mock（`node .tools/mock-llm.cjs`，监听 `127.0.0.1:9099`）。启动后端前设置 `NEXUS_LLM_PRIVATE_ORIGINS=http://127.0.0.1:9099`，然后在 API 配置中选择「自定义」，Base URL 填 `http://127.0.0.1:9099/v1`，即可在无真实 Key 的情况下体验流式渲染。

### 4. 生产构建

```bash
cd frontend && npm run build     # 产物在 frontend/dist
```

将 `dist` 交给 Nginx 等静态服务器，并把 `/api`、`/ws` 反代到 Daphne。前端和后端需一同更新。启用 HTTPS，并配置 `DJANGO_ALLOWED_HOSTS`、稳定的 `DJANGO_SECRET_KEY` 和现有的 `NEXUS_MASTER_KEY`（若一直使用 `backend/.master.key`，应保留该文件）。跨域部署时配置 `DJANGO_CORS_ORIGINS`。若在防止客户端伪造转发地址的可信反代之后运行，可设置 `NEXUS_TRUSTED_PROXY_HOPS`。

---

## 六、文件在线预览

中转站与密聊中的常见文件支持**浏览器内在线预览**（[FilePreviewModal.vue](frontend/src/components/FilePreviewModal.vue)）：

| 类型 | 扩展名 | 预览方式 |
| :--- | :--- | :--- |
| 图片 | png / jpg / jpeg / webp / gif | 大图查看（SVG 因可携带脚本被排除，仅可下载） |
| 文档 | pdf | 内嵌浏览器 PDF 阅读器 |
| 文本 | txt / csv / json / log / yml / ini（≤2 MB） | 等宽字体原文 |
| Markdown | md / markdown | 复用 AI 回答的渲染器 |
| 音视频 | mp3 / wav / mp4 / webm 等 | 原生播放器 |
| 其他 | 压缩包 / 办公文档 / 可执行文件 | 不提供预览，仅下载 |

预览通过鉴权下载接口取回 blob 后在本地渲染，不会二次上传；压缩包与可执行文件出于安全考虑一律不预览。

---

## 七、使用声明与合规

- 站内内置《zixxx 使用声明》（[TERMS.md](TERMS.md)，前端 [terms.ts](frontend/src/lib/terms.ts)），引用《网络安全法》《民法典》《个人信息保护法》《数据安全法》《著作权法》《未成年人保护法》《生成式人工智能服务管理暂行办法》《网络信息内容生态治理规定》等法条，列明**禁止信息十项、禁止行为七项**与注意事项。
- **同意机制**：中转站首次上传前必须勾选同意（按版本号记录于浏览器），未同意时上传入口被禁用；登录页与中转站页脚可随时查看全文。
- 管理员对违规内容可不经通知直接删除；声明版本升级后需重新同意。

---

## 八、账号管理与操作日志（三级权限）

权限层级：**最高管理员 `qzx`（rank 2）＞ 管理员 `sqx`（rank 1）＞ 普通账号（rank 0，如 `yk`）**。

- **改密**（`POST /api/auth/<username>/password/`）：操作者级别须高于目标账号，且目标须为应用账号。新密码至少 12 个字符并经过常见密码检查。重置后目标账号旧 Token 立即失效。
- **日志**（`GET /api/auth/logs/?username=X`）：本人日志始终可查；最高管理员可查任何账号；`sqx` 仅可查普通账号（rank 0）；越级查询返回 403。
- **账号清单**（`GET /api/auth/users/`）：仅管理员（含 `sqx`）。
- **中转站管理**：仅最高管理员 `qzx`（私密文件对「上传者 + 最高管理员」可见）。
- **操作日志**（[accounts/models.py](backend/accounts/models.py) 的 `ActivityLog`）记录：登录成功/失败、退出、密码被重置（含操作人）、中转站上传/修改/删除、模型配置保存，附 IP 与时间戳；记录失败永不影响业务请求。
- 前端入口：侧边栏「账号管理」（仅管理员可见）→ 每行「查看日志 / 更改密码」，按钮按层级自动禁用；非管理员访问 `/accounts` 看到准入页。

---

## 九、安全说明

- 升级已有安装时，先备份数据库，再执行 `python manage.py migrate` 和 `python manage.py init_users`。迁移会停用仍使用已公开默认密码的预置账号口令并撤销对应 Token。初始化命令为当前的三个预置账号重新设密，已自定义的密码继续有效。
- 默认模型的服务端密钥由 `NEXUS_BUILTIN_LLM_API_KEY` 提供。升级前应在服务商后台吊销旧密钥并生成新密钥。自定义公网模型地址可以直接配置，内网模型只允许使用部署方在 `NEXUS_LLM_PRIVATE_ORIGINS` 中列出的具体来源（协议、主机、端口）。
- 私密文件按账号 ID 鉴权。旧版预置账号文件可由保留署名迁移归属，其他旧记录保留原文件和署名，归属未能确认的私密记录由最高管理员访问。
- **模型 API Key 服务端深度加密**：保存时经 HTTPS 上传一次，之后以 Fernet（AES-128-CBC + HMAC-SHA256）密文存入数据库（[agent/crypto.py](backend/agent/crypto.py)）；`GET /api/agent/config/` 只返回 `has_key` 与掩码提示（如 `sk-…3456`），明文永不回传浏览器、不出现在页面源码与爬虫可见内容中。主密钥优先取环境变量 `NEXUS_MASTER_KEY`，否则自动生成于 `backend/.master.key`（chmod 600，已 git-ignore）。对话请求只带 `use_saved: true`，由后端内存解密后直连模型。
- 聊天/中转站文件下载均带 `Content-Disposition`、`X-Content-Type-Options: nosniff` 与 `Content-Security-Policy: sandbox`，图片以外的内容强制下载，避免浏览器直接执行上传内容。
- 中转站拒绝可执行文件/脚本后缀上传；聊天文件限 80 MB、中转站限 500 MB、AI 附件限 25 MB。
- InMemory Channel Layer 仅适合单进程部署；多进程/多机部署请替换为 Redis Channel Layer。

---

## 十、站点信息

- **联系**：zixuanqiu72@gmail.com（页脚与《使用声明》中均可点击）
- **友链**：[qzx 的博客](https://blog.qzx1028.space) · [GitHub @qiuzxxxxx](https://github.com/qiuzxxxxx)
- **备案**：[豫ICP备2026020102号](https://beian.miit.gov.cn/)
- 友链与备案号展示于全站页脚（[SiteFooter.vue](frontend/src/components/SiteFooter.vue)，含登录页），备案号的修改请直接编辑该组件。
