# zixxx —— 个人工作台（任务 · 资料 · 知识库 · AI）

一个仿 **Gemini 极简交互风格** 的自托管全栈 Web 应用，采用 **Vue 3 + Django** 架构。**打开主页即登录页**，围绕个人日常使用构建：**今日待办与任务管理、私人资料库、手机扫码上传、个人知识库与 AI 记忆**，并保留原有的**多模态 AI 对话**、**`qzx` ↔ `sqx` 双人实时聊天**与**免密文件中转站**。

**部署目标（硬约束）**：单台 **4 核 4G 内存服务器**，所有组件（PostgreSQL、Redis、Nginx、Daphne、知识索引 worker、备份）同机运行。全部代码与默认参数必须在该容量下通过验收，资源预算见「部署」一节与 [TRAE_HANDOFF.md](TRAE_HANDOFF.md) 第 12.7 节。

---

## 一、功能矩阵

### 1. 今日工作台与任务（已完成）

- **今日页面**（`/today`）：当天安排、逾期事项、待重新安排、待安排任务与当日完成数，顶部快速新增待办。
- **任务管理**（`/tasks`）：标题、描述、优先级（low/normal/high）、计划日期、截止时间、项目、标签、附件、手动排序、完成/重开/取消/软删除与回收站恢复。
- **项目**（`/projects`）：轻量项目列表与归档；**每日记录**（`/journal`）：按日期保存 Markdown 正文，owner + date 唯一。
- **多端一致**：可变记录全部带 `version` 乐观锁（PATCH 提交旧版本返回 409），创建类操作支持 `client_request_id` 幂等；切换账号时前端整体清空缓存。

### 2. 私人资料库与手机扫码上传（已完成）

- **资料库**（`/library`）：资料夹、标签、备注、列表筛选、在线预览（复用全站预览器）、鉴权下载、重命名、移动、回收站与恢复；存储路径由服务端生成，`sha256` 校验完整性。
- **电脑扫码**：在资料库或任务详情生成限时上传二维码（UploadSession），手机无需登录，凭证只绑定指定目标投递文件；数据库只存 token 摘要，二维码地址用 URL fragment 传递。
- **手机落地页**（`/upload`）：独立简洁布局，逐文件进度、失败原因与单独重试；会话/收据两级幂等（重试不产生重复资料），配额预占、到期与撤销规则见交接文档第 6–7 节。
- 每文件 ≤ 100 MiB，单会话 ≤ 20 个文件 / 500 MiB，会话有效期 10 分钟。

### 3. 个人知识库与 AI 记忆（阶段 E 进行中）

- **知识集合与笔记**（`/knowledge`）：手写 Markdown 笔记；本人资料（TXT / Markdown / 文本 PDF / DOCX）、每日记录、AI 消息可一键「加入知识库」，保留来源与版本关系。
- **中文关键词检索**：首版为确定性关键词方案（CJK 单字 + 二元组、latin 小写化），按 owner、有效集合与当前 ready 修订在数据库内先过滤再排序；不依赖向量服务。
- **索引 worker**：解析作业持久化在数据库（租约 + claim token），`manage.py process_knowledge_jobs` 执行；扫描 PDF 标记 `needs_ocr`，首版不做 OCR。
- **AI 接入**：会话级「使用知识库 / 个人记忆 / 当前工作台」三个开关；资料片段以只读块注入并要求标注 `[S1]` 等来源编号，回答可点开来源定位（页码 / 标题路径）。
- **个人记忆**（`/knowledge/memories`）：候选（suggested）与已确认（active）分离；编辑、停用、恢复、忘记与导出；忘记会抬升上下文水位，旧历史不再注入模型（界面仍可见）。
- **状态说明**：后端已提交，前端页面与对话联调、20 题固定评估集验收仍在进行；口径与遗留问题以 [TRAE_HANDOFF.md](TRAE_HANDOFF.md) 第 18 节为准。

### 4. 多模态 AI 对话（已有）

- 左侧历史会话栏 + 居中悬浮多模态输入框，Markdown 流式渲染、代码高亮与 KaTeX 公式；可随时停止生成。
- 支持 PDF / DOCX / TXT / Markdown 与图片上传；图片缩放编码后随多模态请求发送。
- **内置默认模型**：未保存自己的 Key 时，服务端自动使用内置 DeepSeek 配置（多模态模型 `deepseek-flash`）开箱即用；保存的 API Key 服务端 Fernet 加密，只返回掩码。
- **测试连接**：模型设置中直接用当前表单发起一次短流式请求，显示首响耗时或失败原因。
- 仅 `qzx` / `sqx` 可用；游客 `yk` 与未登录访客被 401/403 拒绝。

### 5. 双人密聊（已有）

- `qzx` ↔ `sqx` 专属：WebSocket 实时文字与文件互传、正在输入提示、断线重连；WS 不可用自动回退 REST。握手经 `Sec-WebSocket-Protocol: zixxx.chat, token.<token>` 子协议，URL 不携带账号 Token。

### 6. 免密文件中转站（已有）

- **免密即传**：无需登录即可上传，选择「对所有人可见」或「仅 qzx 可见（私密投递）」；未登录访客进入独立裸布局，不暴露站内其他功能入口。
- **权限隔离**：访客/未登录仅见公开文件；`yk` 见公开 + 自己的投递；`qzx` 拥有全部管理权（重命名、备注、可见性切换、删除）。
- 文件只经鉴权下载接口流出，`/media` 不对外暴露。

### 7. 账号管理与操作日志（已有）

- 三级权限（rank 2 > rank 1 > rank 0）：分级改密（12 位以上 + 常见密码检查）、越级查询 403、全量操作日志（登录、改密、上传、删除、模型配置保存，含 IP 与时间戳）。

---

## 二、技术栈

| 层级 | 技术选型 | 说明 |
| :--- | :--- | :--- |
| 前端 | Vue 3 (Vite) + TypeScript + Pinia + Vue Router | 构建前执行 `vue-tsc` 类型检查 |
| UI | Tailwind CSS + Lucide Icons | Gemini 留白质感、移动端适配（最低 360px） |
| 渲染 | markdown-it + highlight.js + KaTeX | 禁止原始 HTML 进入 `v-html` |
| 后端 | Django 5 + DRF + Channels + Daphne | SQLite 开发 / PostgreSQL 生产（阶段 F） |
| 实时 | Channels + Daphne | 开发 InMemory 层；生产 Redis（多进程前置条件） |
| 文件 | PyMuPDF / python-docx / Pillow | 附件解析与知识库位置感知解析（保留页码、标题路径） |
| 加密 | cryptography (Fernet) | API Key 服务端加密存储 |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） | 生产方案见阶段 F |

---

## 三、项目结构

```text
├── backend/
│   ├── config/          # settings / asgi / urls / http 助手 / VersionedModel
│   ├── accounts/        # 认证、三级权限、操作日志、init_users 命令
│   ├── agent/           # AI 对话：llm.py 三协议流式适配器、parsing.py、SSE 会话
│   ├── chat/            # qzx ↔ sqx WebSocket 密聊
│   ├── transfer/        # 免密中转站（is_public 可见性、qzx 管理）
│   ├── workspace/       # 任务/项目/标签/每日记录/资料库/扫码上传
│   │   ├── library.py / library_views.py
│   │   └── upload_auth.py / upload_urls.py / upload_views.py
│   ├── knowledge/       # 知识库：模型、检索、上下文组装、记忆、索引作业、评估集
│   │   └── management/commands/   # process_knowledge_jobs / rebuild / seed / cleanup / evaluate
│   └── media/           # 本地文件存储（不对外暴露）
└── frontend/
    └── src/
        ├── views/       # Today / Tasks / Projects / Journal / Library / MobileUpload
        │               # Knowledge / KnowledgeMemories / AgentChat / DirectChat
        │               # TransferStation / Accounts / Login
        ├── components/  # Sidebar、KnowledgeScopeBar、ApiConfigModal、FilePreviewModal 等
        ├── stores/      # auth / agent / config / workspace / knowledge / ui / toast
        └── api/         # axios 封装（agent / workspace / library / upload / knowledge）
```

---

## 四、预置账号

```bash
python manage.py init_users
```

| 用户名 | 密码 | 角色 | 权限 |
| --- | --- | --- | --- |
| `qzx` | `NEXUS_PASSWORD_QZX` 或随机生成 | **最高管理员**（rank 2） | 全部功能：工作台、知识库、AI、密聊、中转站最高管理、账号管理 |
| `sqx` | `NEXUS_PASSWORD_SQX` 或随机生成 | **管理员**（rank 1） | 本人工作台与知识库、AI、密聊、重置普通账号 |
| `yk` | `NEXUS_PASSWORD_YK` 或随机生成 | 游客（rank 0） | **仅中转站**：上传、浏览公开与自己的文件；无工作台/知识库/AI/密聊入口 |

登录后默认跳转：`qzx` / `sqx` → 工作台首页 `/today`（可进入 AI 对话），`yk` → `/transfer`。

---

## 五、快速启动

### 1. 后端

```bash
cd backend
python -m venv venv
# Windows: .\venv\Scripts\activate   Linux/macOS: source venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py init_users

# 开发服务器（支持 WebSocket，默认 8000）
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

### 2. 前端

```bash
cd frontend
npm ci          # Windows 下若 esbuild 报 TEMP 拒绝访问，先设置 TEMP/TMP 到可写目录
npm run dev     # http://localhost:5173，/api 与 /ws 代理到 127.0.0.1:8000
```

### 3. 知识库 worker 与初始化（阶段 E）

```bash
cd backend
python manage.py process_knowledge_jobs --once          # 执行一批待处理索引作业
python manage.py process_knowledge_jobs --once --limit 10
python manage.py rebuild_knowledge_index --document <uuid> --dry-run
python manage.py seed_personal_knowledge --owner qzx --dry-run   # 幂等初始化个人条目
python manage.py cleanup_knowledge_data --dry-run
```

### 4. 测试与自检

```bash
cd backend
.\venv\Scripts\python.exe manage.py test agent config.test_security workspace knowledge --noinput

# 端到端自检脚本（勿对真实数据库运行，会创建/改密/删除测试数据）
python smoke_test.py http://127.0.0.1:8000
node ws_smoke.mjs
```

```bash
cd frontend
npm run build    # 先 vue-tsc 再 vite build，产物在 frontend/dist
npm audit        # 联网失败时记录原因，不得输出“无漏洞”
```

本地无 Key 体验流式对话：`node .tools/mock-llm.cjs`（监听 `127.0.0.1:9099`），API 配置选「自定义」，Base URL 填 `http://127.0.0.1:9099/v1`，并设置 `NEXUS_LLM_PRIVATE_ORIGINS=http://127.0.0.1:9099`。

---

## 六、部署（4 核 4G 硬约束）

| 组件 | 内存预算 | 关键约束 |
| --- | --- | --- |
| 系统 + Nginx | ≤ 500 MiB | SPA history fallback；`/api/` 关闭响应缓冲（SSE）；`/ws/` 转发 Upgrade |
| PostgreSQL | ≤ 900 MiB | shared_buffers=256MB、max_connections=30 |
| Redis | ≤ 256 MiB | maxmemory + 淘汰策略；channels / 限速 / 短 TTL 缓存共用，禁止存大对象 |
| Daphne (web) | ≤ 700 MiB | 单进程 async；多进程前必须先接入 Redis 层与 Redis 限速 |
| knowledge-worker | ≤ 450 MiB | 并发固定 1；解析子进程有内存上限与超时，被 OOM 后由租约重领 |
| 余量 | ≥ 500 MiB | 备份安排在低谷时段；建议 2G swap 兜底，正常运行不依赖 |

完整预算、9 条强制要求与验收清单见 [TRAE_HANDOFF.md](TRAE_HANDOFF.md) 第 12.7 节（含 4C4G 等价环境满负荷验收）。Docker Compose、Nginx 模板与备份恢复脚本由阶段 F 交付，环境变量清单见其第 12.3 节。

已生效的环境变量：`DJANGO_DEBUG`、`DJANGO_SECRET_KEY`、`DJANGO_ALLOWED_HOSTS`、`DJANGO_CORS_ORIGINS`、`DJANGO_CSRF_TRUSTED_ORIGINS`、`NEXUS_MASTER_KEY`、`NEXUS_BUILTIN_LLM_API_KEY`、`NEXUS_LLM_PRIVATE_ORIGINS`、`NEXUS_TRUSTED_PROXY_HOPS`、`NEXUS_PASSWORD_QZX/SQX/YK`。

---

## 七、安全要点

- **API Key 深度加密**：Fernet 密文入库，接口只返回 `has_key` 与掩码；主密钥取 `NEXUS_MASTER_KEY`，否则生成于 `backend/.master.key`（已 git-ignore，迁移时必须保留）。
- **内置默认 Key** 由部署环境 `NEXUS_BUILTIN_LLM_API_KEY` 提供，不出现在浏览器与网络响应中；曾写入源码的旧 Key 应在服务商后台吊销。
- **出站限制**：内网模型地址只允许 `NEXUS_LLM_PRIVATE_ORIGINS` 中列出的具体来源；已保存密钥按来源绑定，限制跨来源重定向与 DNS 解析结果。
- **文件安全**：所有下载经鉴权接口，带 `Content-Disposition` / `nosniff` / CSP sandbox；中转站拒绝可执行脚本后缀；聊天 80 MiB、中转站 500 MiB、AI 附件 25 MiB、扫码上传 100 MiB。
- **扫码凭证**：数据库只存 token 摘要；fragment 传递、日志脱敏、`Referrer-Policy: no-referrer`；Upload 凭证只能投递文件，不能换取账号 Token 或下载资料。
- **升级**：先备份再迁移；`accounts/0002` 会停用已公开默认密码的账号并撤销 Token，需执行 `init_users` 重新设密；更换 `NEXUS_MASTER_KEY` 会使原密文不可解密。
- Markdown 禁止原始 HTML；私人 API 响应 `no-store`；登录限速、改密强度检查；InMemory Channel Layer 仅适用单进程。

---

## 八、使用声明

- 站内内置《zixxx 使用声明》（[TERMS.md](TERMS.md)，前端 [terms.ts](frontend/src/lib/terms.ts)）：完整版适用于注册账号；游客在中转站仅展示《文件中转站使用声明》，不涉及 AI、密聊与模型密钥内容。
- 同意按版本号记录于浏览器，升级后需重新同意；管理员对违规内容可不经通知删除。
- 联系：zixuanqiu72@gmail.com

---

## 九、开发进度与协作

实施按 [TRAE_HANDOFF.md](TRAE_HANDOFF.md) 执行，其第 18 节为开发协作记录区（口径、进度表、审查反馈与复验记录）。

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| A–D | 基线 / 任务工作台 / 私人资料库 / 扫码上传 | 已完成 |
| E | 个人知识库与 AI 记忆 | **进行中**（后端已提交，前端联调与评估验收中） |
| F | 服务器就绪（PostgreSQL / Redis / Compose / Nginx / 备份） | 未开始 |
| G | 总体验收 | 未开始 |

新增模块的口径与已知问题以第 18 节为唯一权威来源；本 README 与实现不一致时，以交接文档为准。

---

## 十、站点信息

- **联系**：zixuanqiu72@gmail.com（页脚与《使用声明》可点击）
- **友链**：[qzx 的博客](https://blog.qzx1028.space) · [GitHub @qiuzxxxxx](https://github.com/qiuzxxxxx)
- **备案**：[豫ICP备2026020102号](https://beian.miit.gov.cn/)（展示于 [SiteFooter.vue](frontend/src/components/SiteFooter.vue)）
