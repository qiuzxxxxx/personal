# zixxx —— 个人工作台（任务 · 资料 · 知识库 · AI）

一个仿 **Gemini 极简交互风格** 的自托管全栈 Web 应用，采用 **Vue 3 + Django** 架构。**打开主页即登录页**，围绕个人日常使用构建：**今日待办与任务管理、私人资料库、手机扫码上传、个人知识库与 AI 记忆**，并提供**多模态 AI 对话**、**站内留言板**与**免密文件中转站**。

**运行形态**：本地开发环境为 **后端 Django 5 + Channels（Daphne）** 与 **前端 Vue 3 + Vite** 两个进程；数据落在本地 SQLite 与 `backend/media/`。生产环境变量清单见 [.env.example](.env.example)。

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
- **手机落地页**（`/upload`）：独立简洁布局，逐文件进度、失败原因与单独重试；会话/收据两级幂等（重试不产生重复资料），配额预占、到期与撤销规则由 `UploadSession` 模型与 `config/settings.py` 中的限额参数控制。
- 电脑上传与手机扫码上传每个文件 ≤ 1 GiB；单个扫码会话最多 20 个文件 / 1 GiB，会话有效期 10 分钟。

### 3. 个人知识库与 AI 记忆（阶段 E 进行中）

- **知识集合与笔记**（`/knowledge`）：手写 Markdown 笔记；本人资料（TXT / Markdown / 文本 PDF / DOCX）、每日记录、AI 消息可一键「加入知识库」，保留来源与版本关系。
- **中文关键词检索**：首版为确定性关键词方案（CJK 单字 + 二元组、latin 小写化），按 owner、有效集合与当前 ready 修订在数据库内先过滤再排序；不依赖向量服务。
- **索引 worker**：解析作业持久化在数据库（租约 + claim token），`manage.py process_knowledge_jobs` 执行；扫描 PDF 标记 `needs_ocr`，首版不做 OCR。
- **AI 接入**：会话级「使用知识库 / 个人记忆 / 当前工作台」三个开关；资料片段以只读块注入并要求标注 `[S1]` 等来源编号，回答可点开来源定位（页码 / 标题路径）。
- **个人记忆**（`/knowledge/memories`）：候选（suggested）与已确认（active）分离；编辑、停用、恢复、忘记与导出；忘记会抬升上下文水位，旧历史不再注入模型（界面仍可见）。
- **状态说明**：后端已提交，前端页面与对话联调、20 题固定评估集验收仍在进行；实现细节以 `backend/knowledge/` 与 `backend/workspace/` 源码为准。

### 4. 多模态 AI 对话（已有）

- 左侧历史会话栏 + 居中悬浮多模态输入框，Markdown 流式渲染、代码高亮与 KaTeX 公式；可随时停止生成。
- 支持 PDF / DOCX / TXT / Markdown 与图片上传；图片缩放编码后随多模态请求发送。
- **内置默认模型**：未保存自己的 Key 时，服务端自动使用内置 DeepSeek 配置（多模态模型 `deepseek-flash`）开箱即用；保存的 API Key 服务端 Fernet 加密，只返回掩码。
- **测试连接**：模型设置中直接用当前表单发起一次短流式请求，显示首响耗时或失败原因。
- 仅 `qzx` / `sqx` 可用；游客 `yk` 与未登录访客被 401/403 拒绝。
- **保留策略**：管理员账号的 AI 对话永久保存；成员和访客账号的 AI 消息与无引用附件仅保存 24 小时。接口访问时会惰性清理，生产环境还应定时执行 `cleanup_retention_data`。

### 5. 站内留言板（贴吧式，已有）

- 所有非访客成员可浏览、发帖、回复；帖子支持公开或指定可见范围。
- 帖子和回复均可附带文件附件（最大 1 GB），通过鉴权接口下载。
- 作者可删除自己的帖子/回复（物理删除），管理员可删除任意内容。
- 帖子列表按时间倒序展示，点击进详情看楼主帖 + 回复楼。
- 记录保留在服务器数据库，用于内容安全与审计。

### 6. 免密文件中转站（已有）

- **免密即传**：无需登录即可上传，选择「对所有人可见」或「仅 qzx 可见（私密投递）」；未登录访客进入独立裸布局，不暴露站内其他功能入口。
- **权限隔离**：访客/未登录仅见公开文件；`yk` 见公开 + 自己的投递；`qzx` 拥有全部管理权（重命名、备注、可见性切换、删除）。
- 文件只经鉴权下载接口流出，`/media` 不对外暴露。

### 7. 账号管理与操作日志（已有）

- 三级权限（rank 2 > rank 1 > rank 0）：分级改密（12 位以上 + 常见密码检查）、越级查询 403、全量操作日志（登录、改密、上传、删除、模型配置保存，含 IP 与时间戳）。
- **公告与历史**：最高管理员可在文件中转站的公告管理区发布或撤下登录页公告；登录页顶部、中转站顶部居中展示最新公告，登录后应用顶栏居中显示公告摘要，新公告带红点与“新”标记提醒（登录页、顶栏、侧边栏共用已读状态）。公告与中转站公告均保留发布历史（最近 50 条），可在登录页、顶栏、中转站与侧边栏查看。公告内容按纯文本渲染，不影响登录接口可用性。
- **系统维护**：最高管理员可在账号管理开启维护模式并填写说明；开启后仅 `qzx` 可登录，其他账号的登录会话立即失效，登录页展示维护提示。
- **账号锁定**：最高管理员可锁定或解锁非最高管理员账号；锁定后该账号无法登录，已有登录会话与扫码上传会话立即失效，并记录操作日志。

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
│   ├── chat/            # 站内留言板（贴吧式帖子+回复）
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
| `qzx` | `NEXUS_PASSWORD_QZX` 或随机生成 | **最高管理员**（rank 2） | 全部功能：工作台、知识库、AI、留言板、中转站最高管理、账号管理 |
| `sqx` | `NEXUS_PASSWORD_SQX` 或随机生成 | **管理员**（rank 1） | 本人工作台与知识库、AI、留言板、重置普通账号 |
| `yk` | `NEXUS_PASSWORD_YK` 或随机生成 | 游客（rank 0） | **仅中转站**：上传、浏览公开与自己的文件；无工作台/知识库/AI/留言板入口 |

登录后默认跳转：`qzx` / `sqx` → 工作台首页 `/today`（可进入 AI 对话），`yk` → `/transfer`。

---

## 五、快速启动

两个终端各跑一条命令即可，无需任何启动脚本。

### 1. 后端（终端 A）

```bash
cd backend
# 首次安装
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
python manage.py migrate
python manage.py init_users

# 日常启动（--noreload 避免多进程，热重载由前端 Vite 承担）
.\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

`--noreload` 是关键：默认的自动重载会额外 fork 一个监视进程，启动慢且吃内存。改完 Python 代码后按 `Ctrl+C` 重启即可。

### 2. 前端（终端 B）

```bash
cd frontend
npm ci            # 首次安装；Windows 下若 esbuild 报 TEMP 拒绝访问，先把 TEMP/TMP 指向可写目录
npm run dev       # http://127.0.0.1:5173，/api 与 /ws 代理到 127.0.0.1:8000
```

`backend/venv/` 和 `frontend/node_modules/` 是本机安装的依赖，不属于项目源码。需要缩小项目目录时，先停止后端、前端及占用其中二进制文件的进程，在项目根目录执行以下 PowerShell 命令；若 Windows 报“文件正在使用”，先关闭占用程序再重试。清理后按上面的首次安装命令重新创建依赖。Vite 的预构建缓存位于 `frontend/node_modules/.vite/`，删除后首次启动会重新生成。

```powershell
Remove-Item -LiteralPath .\backend\venv -Recurse -Force
Remove-Item -LiteralPath .\frontend\node_modules -Recurse -Force
```

### 3. 知识库 worker 与初始化

```bash
cd backend
python manage.py process_knowledge_jobs --once          # 执行一批待处理索引作业
python manage.py process_knowledge_jobs --once --limit 10
python manage.py rebuild_knowledge_index --document <uuid> --dry-run
python manage.py seed_personal_knowledge --owner qzx --dry-run   # 幂等初始化个人条目
python manage.py cleanup_knowledge_data --dry-run
python manage.py cleanup_retention_data                    # 清理 AI 历史
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

## 六、运行与配置

本项目当前以**本地直跑**方式运行：后端 Daphne/Django 进程 + 前端 Vite 开发服务器 + 本地 SQLite，没有容器化编排。

| 组件 | 说明 |
| --- | --- |
| 后端 | `manage.py runserver`（Daphne 提供 WebSocket），开发数据库为 SQLite（WAL 模式） |
| 前端 | Vite dev server，`/api` 与 `/ws` 反向代理到 `127.0.0.1:8000` |
| 知识索引 worker | `manage.py process_knowledge_jobs --interval 5`，与后端分离运行 |
| 保留策略清理 | `manage.py cleanup_retention_data`，生产环境建议每分钟定时执行 |
| 文件存储 | `backend/media/`，不对外暴露，下载一律走鉴权接口 |

如需上服务器，代码本身支持 PostgreSQL / Redis（通过 `DATABASE_ENGINE`、`REDIS_URL` 等环境变量切换），但部署编排（Nginx 模板、systemd 单元、备份脚本）不在本仓库内，需要自行按环境编写。

现有宝塔服务器从旧版升级到当前新版，请按 [UPGRADE_GUIDE_OLD_TO_CURRENT.md](UPGRADE_GUIDE_OLD_TO_CURRENT.md) 执行；留言板保留策略的专项说明见 [CHAT_RETENTION_UPDATE.md](CHAT_RETENTION_UPDATE.md)。

已生效的环境变量：`DJANGO_DEBUG`、`DJANGO_SECRET_KEY`、`DJANGO_ALLOWED_HOSTS`、`DJANGO_CORS_ORIGINS`、`DJANGO_CSRF_TRUSTED_ORIGINS`、`NEXUS_MASTER_KEY`、`NEXUS_BUILTIN_LLM_API_KEY`、`NEXUS_LLM_PRIVATE_ORIGINS`、`NEXUS_TRUSTED_PROXY_HOPS`、`NEXUS_PASSWORD_QZX/SQX/YK`。完整清单见 [.env.example](.env.example)。

---

## 七、安全要点

- **API Key 深度加密**：Fernet 密文入库，接口只返回 `has_key` 与掩码；主密钥取 `NEXUS_MASTER_KEY`，否则生成于 `backend/.master.key`（已 git-ignore，迁移时必须保留）。
- **内置默认 Key** 由部署环境 `NEXUS_BUILTIN_LLM_API_KEY` 提供，不出现在浏览器与网络响应中；曾写入源码的旧 Key 应在服务商后台吊销。
- **出站限制**：内网模型地址只允许 `NEXUS_LLM_PRIVATE_ORIGINS` 中列出的具体来源；已保存密钥按来源绑定，限制跨来源重定向与 DNS 解析结果。
- **文件安全**：所有下载经鉴权接口，带 `Content-Disposition` / `nosniff` / CSP sandbox；中转站拒绝常见可执行脚本后缀；留言板与中转站单文件上限 1 GiB、AI 附件 25 MiB、扫码上传每个文件上限 1 GiB。
- **模型传输**：公网模型接口必须使用 HTTPS；本机 HTTP 仅限 loopback，内网 HTTP 必须显式配置 `NEXUS_LLM_PRIVATE_ORIGINS`。
- **扫码凭证**：数据库只存 token 摘要；fragment 传递、日志脱敏、`Referrer-Policy: no-referrer`；Upload 凭证只能投递文件，不能换取账号 Token 或下载资料。
- **升级**：先备份再迁移；`accounts/0002` 会停用已公开默认密码的账号并撤销 Token，需执行 `init_users` 重新设密；更换 `NEXUS_MASTER_KEY` 会使原密文不可解密。
- Markdown 禁止原始 HTML；私人 API 响应 `no-store`；登录限速、改密强度检查；InMemory Channel Layer 仅适用单进程。

---

## 八、使用声明

- 站内内置《zixxx 使用声明》（[TERMS.md](TERMS.md)，前端 [terms.ts](frontend/src/lib/terms.ts)）：完整版适用于注册账号；游客在中转站仅展示《文件中转站使用声明》，不涉及 AI、留言板与模型密钥内容。
- 同意按版本号记录于浏览器，升级后需重新同意；管理员对违规内容可不经通知删除。
- 联系：zixuanqiu72@gmail.com

---

## 九、开发进度与协作

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| A–D | 基线 / 任务工作台 / 私人资料库 / 扫码上传 | 已完成 |
| E | 个人知识库与 AI 记忆 | **进行中**（后端已提交，前端联调与评估验收中） |

新增模块的口径与已知问题以对应模块的源码与测试为准；本 README 与实现不一致时，以源码为准。

---

## 十、站点信息

- **联系**：zixuanqiu72@gmail.com（页脚与《使用声明》可点击）
- **友链**：[qzx 的博客](https://blog.qzx1028.space) · [GitHub @qiuzxxxxx](https://github.com/qiuzxxxxx)
- **备案**：[豫ICP备2026020102号](https://beian.miit.gov.cn/)（展示于 [SiteFooter.vue](frontend/src/components/SiteFooter.vue)）
