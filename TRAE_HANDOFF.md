# zixxx 个人工作台实施交接文档

交接日期为 2026-11-14，时区为 Asia/Shanghai。项目工作目录为 D:\ai。接手开发者为 Trae。

本文是基于现有源码编写的实施方案。任务管理、每日记录、私人资料库、扫码上传、个人知识库和 AI 记忆属于待开发功能。文中引用的模块、接口和代码路径已经检查，具体部署环境还需在上线时核实。个人知识库的完整实施要求见第 16 节，已纳入首版执行顺序与验收。

## 1. 用户目标与执行范围

用户希望将目前的 zixxx 扩展为长期使用的个人工作台，用来记录每天要做的事、管理个人资料，并支持电脑展示二维码、手机扫码上传资料。项目后续将部署到服务器。

用户追加要求：结合可核实的个人需求，为 AI 增加知识库，并写入 Trae 交接文档。实现后，AI 应能在用户选择的范围内检索私人资料、引用出处、使用有效的个人偏好，并将用户要求保存的内容写成可编辑、可撤回的知识或记忆。

用户此前已授权在保留原有业务功能的前提下直接审查和修改安全问题。此次要求是制定详细交接方案，交由 Trae 实施。

Trae 接手后应按本文顺序完成开发、测试、迁移脚本和部署材料。遇到可逆的实现选择，使用本文默认方案继续推进，并在交付说明中记录选择。真实服务器、域名、账号和外部服务密钥缺失时，先完成本地可验证的交付物，精确说明上线仍缺什么。

### 1.1 第一版要完成的使用闭环

1. 早上打开工作台，看到今天安排、逾期事项和待安排任务，能快速新增一条待办。
2. 白天调整任务、标记完成、补充记录，把文件或手机照片关联到任务。
3. 电脑点“手机上传”，手机扫码选择文件，电脑收到上传结果，资料进入私人资料库。
4. 晚上能查看今天完成了什么、写下每日记录，并安排剩余任务。
5. 换设备、退出再登录、服务重启后，任务、记录和文件都能恢复。
6. 上线后通过同一 HTTPS 域名访问，完成备份恢复演练。
7. 将笔记、文档或选中的对话内容加入知识库，在 AI 对话中提问并打开回答的资料出处。
8. 查看 AI 记住了什么，修改或停用过期偏好；询问今天安排时使用任务模块的当前数据。

### 1.2 本文采用的默认方案

以下均为可调整的产品默认值，应在最终交付说明中列出，不应描述为用户已经逐项确认。

- 以 qzx 的个人使用体验为首要目标。qzx、sqx 各有独立工作台，新模块数据按 owner 隔离。
- yk 和历史 guest 账号沿用游客定位。游客继续使用已有中转站。
- 语言采用简体中文，日期分组默认使用 Asia/Shanghai。
- 新增资料默认为私人资料。公开分享仍通过已有中转站显式操作。
- 手机扫码上传使用限时上传凭证，扫码者无需登录。该凭证仅能向指定位置投递文件。
- 前端沿用 Vue 3、TypeScript、Pinia、Tailwind 和现有 Lucide 图标。
- 后端沿用 Django、DRF、Channels、Daphne。
- 开发环境支持 SQLite。正式部署方案默认采用 PostgreSQL、Redis、Nginx 和 Daphne，提供 Docker Compose 交付。
- 首版文件存储采用服务器持久化目录，预留 Django Storage 接口以便以后接入对象存储。
- 首版知识库采用可验证的中文关键词检索、分段引用和个人记忆管理；向量检索作为后续增强，不依赖新增付费服务才能交付。
- 本轮核心范围为第 14 节的阶段 A 至 G，包含第 16 节知识库。第 15 节属于后续扩展，核心功能完成后再选择实施。

## 2. 已核实的项目现状

### 2.1 现有业务

- AI 对话支持会话历史、图片与文档附件、Markdown、公式和流式输出。
- 模型服务支持 OpenAI 兼容协议、Gemini 原生协议、Claude 原生协议。
- 模型设置已增加“测试连接”，调用 POST /api/agent/config/test/，返回首次文本响应耗时或可读错误。
- qzx 与 sqx 可通过 WebSocket 聊天、发送文件，WebSocket 不可用时可通过 REST 发送。
- 文件中转站支持匿名上传公开或私密文件。qzx 可管理中转站全部文件，其他登录用户可见公开文件和本人文件。
- 账号管理包含分级改密与操作日志。
- 当前主页是登录页，qzx、sqx 登录后的默认目标是 /agent，yk 默认进入 /transfer。
- 当前代码使用 SQLite 和 InMemoryChannelLayer。
- 当前 AI 附件解析会将文本带入会话上下文；尚无独立知识库、分段索引、来源引用记录或个人记忆模型，不能把已有附件聊天当作知识库已经完成。

### 2.2 接手时重点阅读的源码

前端入口与整体布局在 frontend/src/App.vue、frontend/src/router/index.ts 和 frontend/src/components/Sidebar.vue。登录后的跳转逻辑还在 frontend/src/views/LoginView.vue，修改首页时要同时检查这些入口。

账号状态与请求封装在 frontend/src/stores/auth.ts 和 frontend/src/api/client.ts。认证 Token 当前保存在 localStorage，下载依靠带认证头的请求获取 Blob。

现有业务页面分别为 frontend/src/views/AgentChatView.vue、DirectChatView.vue、TransferStation.vue 和 AccountsView.vue。模型设置组件为 frontend/src/components/ApiConfigModal.vue。

可复用的界面能力包括 frontend/src/components/ModalShell.vue、FilePreviewModal.vue、FileIcon.vue、ToastHost.vue，以及 frontend/src/lib/preview.ts、markdown.ts、format.ts。复用时仍要检查新场景的权限、文件大小和 MIME 边界。

后端全局配置、路由和 ASGI 入口分别位于 backend/config/settings.py、urls.py 和 asgi.py。backend/config/streaming.py 用于在 ASGI 下逐块发送同步生成器和文件内容。

认证、角色及日志在 backend/accounts/。AI 配置与聊天在 backend/agent/。模型出站地址检查在 backend/agent/endpoints.py，密钥存储在 crypto.py，模型适配器在 llm.py。

双人聊天代码在 backend/chat/。中转站代码在 backend/transfer/，TransferFile 已增加 uploader 外键。

### 2.3 当前版本与检查记录

- frontend/package.json 的生产构建会先执行 vue-tsc，再执行 Vite 构建。
- 后端依赖要求 Django >=5.2.19,<5.3，已经显式列入 cryptography。
- 当前前端依赖已升级 Axios、KaTeX、markdown-it、PostCSS 和 vue-tsc。
- 上一轮开发记录中，agent 与 config.test_security 共 13 项测试通过，前端构建通过。
- 上一轮安全修改还执行过 93 项 HTTP 检查、实际 WebSocket 收发和模拟模型流式检查。
- 上述属于历史验证记录。Trae 应在自己的代码版本和依赖环境中重新运行相关检查。
- AUDIT.md 是早期审查记录，不能据此推断当前环境已经完成上线配置。
- 本次检查发现 D:\ai 尚未初始化 Git 仓库。建立本地版本管理时先检查 .gitignore，排除数据库、媒体、密钥、环境文件和依赖目录。
- 根目录 package.json 没有有效的项目测试命令。前端命令在 frontend/ 执行，Django 命令在 backend/ 执行。

### 2.4 已有安全行为

接手修改时，应将以下行为纳入兼容性验收。

- 模型 API Key 加密保存，读取接口只返回是否存在及掩码。
- 默认 DeepSeek Key 由 NEXUS_BUILTIN_LLM_API_KEY 提供，源码中原先写死的密钥已经移除。
- 已保存模型密钥按来源绑定，出站代理限制内网地址、DNS 解析结果与跨来源重定向。
- WebSocket 使用 zixxx.chat 和 token.<token> 子协议握手，URL 中没有账号 Token。
- WebSocket 在收发事件前检查 Token 是否仍有效。
- 私密中转站文件通过 uploader_id 判断归属。
- Markdown 禁止原始 HTML，文件下载经过鉴权，私人响应使用 no-store。
- 登录有限速，改密有长度和常见密码检查。

这些措施需要伴随新增功能持续验证。它们不等于已经完成全面上线审计。

### 2.5 上线前必须处理的现存差距

1. 核实 accounts/0002_revoke_preset_passwords 与 transfer/0002_transferfile_uploader 是否已应用。此前修改源码时没有对用户现有数据库执行这两项迁移。
2. 前一项迁移会停用仍使用已公开默认密码的账号口令并撤销对应 Token。升级流程中要执行 init_users 为当前预置账号初始化可用密码，向所有者安全交付新凭据。
3. transfer 的迁移只为能够确认的预置账号署名恢复归属。其他历史记录需要保留，无法确认归属的私密记录继续由中转站最高管理员处理。
4. settings.py 在缺少 DJANGO_SECRET_KEY 时每次启动随机生成值。生产配置应要求稳定的显式值，缺失时给出明确启动错误。
5. agent/crypto.py 在密钥文件无效、写入失败或初始化竞争时存在恢复与一致性风险。生产环境应验证主密钥有效，禁止静默生成临时主密钥后继续保存业务密文。并发初始化需要原子处理。
6. 已有加密数据对应的主密钥必须随迁移保留。设置一个新的随机 NEXUS_MASTER_KEY 会使原密文无法解密。
7. 默认 DeepSeek Key 是否已在服务器配置尚未验证。曾写入源码的旧 Key 需要在服务商后台吊销，新 Key 由部署环境提供。
8. 当前限速使用默认进程内缓存，Channels 也使用进程内层。生产配置应接入 Redis，覆盖多进程限速与聊天广播。
9. 现有公开中转站有单文件上限，但还需要总量配额、临时盘预算和网关限速，以应对匿名上传持续占满磁盘。
10. 真实服务器、域名、HTTPS、备份位置和生产网络连通性尚未配置或验证。

### 2.6 接手时的基线检查命令

在 Windows PowerShell 中，从项目目录进入 backend，使用项目虚拟环境运行以下检查。showmigrations 用于检查现有数据库状态，实际升级在完成备份和迁移演练后执行。

```powershell
Set-Location D:\ai\backend
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py showmigrations --plan
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe manage.py test agent config.test_security --noinput
```

前端安装和检查使用 frontend/package-lock.json。

```powershell
Set-Location D:\ai\frontend
npm ci
npm run build
npm audit
```

上述为接手基线，新增模块后需要补充其测试。npm audit 联网失败时应记录失败原因，不能输出“无漏洞”。开发环境如果限制本地套接字，Daphne 初始化与 WebSocket 测试可能受影响，应在具备本地网络权限的测试环境中完成验证。

新增依赖安装到项目环境，并更新对应锁文件或依赖清单。当前 backend/venv 曾缺少 pip 模块，可以通过外部 pip 的 --python 选项指定该虚拟环境，避免把后端依赖误装到全局环境。

## 3. 产品结构与页面行为

### 3.1 导航与路由

- /today 为登录后的工作台首页。
- /tasks 为全部任务，包含待安排、进行中、已完成和筛选。
- /projects 为轻量项目列表，项目详情可使用 /projects/:id。
- /journal 为每日记录，支持选择日期。
- /library 为私人资料库。
- /knowledge 为个人知识库，提供知识集合、笔记、资料索引状态和搜索。
- /knowledge/memories 为个人记忆管理，提供来源、适用范围、编辑、停用与忘记。
- /upload 为手机扫码落地页，使用独立的简洁布局。
- /agent、/chat、/transfer、/accounts 继续提供现有入口。
- /settings 汇总个人偏好与模型设置，可逐步从现有弹窗复用组件。
- /login 作为明确的登录路由。原 / 地址按登录态跳转至登录页或工作台，保留旧链接兼容。

常用导航优先放“今日、任务、资料、记录”。知识库与已有 AI 入口相邻，项目、聊天、中转站保持可发现。手机保留四个常用底部入口，通过更多菜单进入知识库等模块。

路由权限和 API 权限必须同时存在。手机上传页即使浏览器已登录其他账号，也只能按上传凭证对应的目标接收资料。

### 3.2 今日页面

页面按完成任务的顺序组织。

1. 顶部显示当前日期、星期和“添加任务”输入框。
2. 主区域显示今天安排的未完成任务，支持完成、编辑、调整计划日期。
3. 逾期事项和过去计划但未完成的任务分别展示，用户可以移到今天或重新安排。
4. 待安排任务作为可展开的入口，避免自动挤入今日清单。
5. 下方显示今天已完成的任务与简短每日记录。
6. 资料入口包含“上传文件”和“手机扫码上传”，上传完成后可立即关联任务。

首页使用真实任务与资料数据。新账号显示“添加第一条任务”和“上传第一份资料”等直接操作。开发演示数据只能写入专门的测试环境。

### 3.3 任务操作

支持标题快速添加、详细描述、优先级、计划日期、截止时间、项目、标签、附件、手动排序、完成、重新打开、取消和删除。

首次提交成功后才清空输入框。请求失败时保留用户输入，并显示可重试反馈。完成操作可以乐观更新，但失败后必须恢复原状态。

任务详情用侧滑面板或独立详情页。手机端详情占满主要可视区域。键盘用户可以添加和编辑任务，排序同时提供“上移、下移”操作。

### 3.4 项目、每日记录与资料

项目包含名称、说明、颜色标识、进行或归档状态，以及所属任务。首版采用任务列表，后续可以增加看板。

每日记录按日期保存正文，适合记录当天安排、进展与想法。首版采用 Markdown 输入与预览，复用现有安全渲染器。正文自动保存显示“保存中、已保存、保存失败”。

资料库支持按文件名、备注、标签和资料夹查找，支持列表、预览、下载、重命名、移动、关联任务和移入回收站。

个人资料库与公开中转站分别保存各自的访问权限。用户将私人资料发布到中转站时，应明确选择公开或私密投递，并创建独立中转站记录。后续修改源文件的可见性不能意外改变已经发布的副本。

资料、每日记录和 AI 消息提供“加入知识库”，由登录用户选择目标集合。导入记录保留来源和版本，展示排队、解析中、可检索或失败。手机上传成功只代表资料入库，扫码者无权决定资料是否用于 AI。任务的当前状态通过实时查询取得，历史复盘可由用户另存为有日期的知识笔记。

## 4. 任务与日期的业务规则

### 4.1 日期含义

- scheduled_date 为计划在哪一天做，使用用户时区的日历日期。
- due_at 为明确的截止时刻，数据库存储带时区时间，统一转换为 UTC。
- completed_at 为实际完成时刻。
- 今日列表使用 scheduled_date 等于当前本地日期。
- 待安排列表使用 scheduled_date 为空且状态未结束。
- 逾期使用 due_at 小于当前时刻且状态为 todo 或 doing。
- 过去计划未完成使用 scheduled_date 早于今天且状态未结束，文案显示“待重新安排”。
- 截止时间为空时，不因计划日期过去就伪造一个截止时刻。

过了午夜，任务原计划日期继续保留。页面恢复到前台、跨午夜以及用户调整时区后，应重新获取当天视图。

### 4.2 状态转换

状态采用 todo、doing、done、cancelled。

- 标记 done 时设置 completed_at。
- 重复设置 done 时返回已有状态，避免重写完成时间。
- 从 done 重新打开时清空 completed_at。
- cancelled 不计入完成统计。
- 删除使用 deleted_at 软删除，回收站支持恢复。
- 首版统计以当前数据计算。“当日完成数”指 completed_at 落入当天且当前状态仍为 done 的任务数量。
- 同一天创建、完成后又重新打开的任务，从当天完成数中移除。

首版不宣称提供不可变的历史绩效报表。若以后需要精确重建任意时刻的状态，增加 TaskEvent 事件记录后再提供该类统计。

### 4.3 多端更新与重复请求

Task、Project、DailyEntry 和 Material 的可变记录增加 version 整数字段。

- PATCH 要求客户端提交读取时的 version。
- 后端在事务中用 id、owner、version 做条件更新，成功后 version 加一。
- 更新行数为零时，先确认对象存在且属于本人，再返回 409 与当前可编辑版本。
- 前端保留本地草稿并提示刷新或对照重试。
- 上传、快速添加任务等可能重试的创建操作传 client_request_id。
- 同一 owner、同一 client_request_id 的重复请求返回原结果。相同 ID 携带不同内容时返回 409。
- 排序使用事务内批量更新，核对所有任务的 owner 和预期版本，冲突时整体失败。

### 4.4 首版范围内的每日记录

owner 与 date 建唯一约束，防止同一天生成两份记录。

前端输入停顿后保存，并保留当前草稿与服务端版本。关闭页面前存在未保存文本时提示用户。请求失败时正文留在页面内，允许显式复制或重试。

切换账号时清空内存中的任务、每日记录、资料列表与上传状态。使用 KeepAlive 的页面需要按 user.id 隔离实例或在账号变化时销毁缓存，不能只监听是否登录的布尔值。

## 5. 数据模型建议

本节是建议字段合同，Trae 可以根据现有代码习惯调整命名。任何调整必须同时更新接口、迁移和验收说明。

所有新业务表使用 UUID 主键，owner 使用 settings.AUTH_USER_MODEL 外键。客户端不应有修改 owner 的字段权限。

### 5.1 WorkspacePreference

- user，一对一。
- timezone，默认 Asia/Shanghai，使用有效 IANA 时区。
- week_starts_on，默认周一。
- default_task_priority，默认 normal。

### 5.2 Project

- id、owner、name、description。
- status 为 active 或 archived。
- color 为有限的主题色标识。
- position、version、created_at、updated_at、deleted_at。
- name 长度建议 120，description 长度建议 10000。

项目归档后仍可查询原任务。删除项目先软删除，任务保留项目关联用于恢复。任务列表能展示“项目已删除”，并允许移到其他项目。

### 5.3 Task

- id、owner、project，可选 project。
- title，长度 200。
- description，长度上限建议 20000。
- status、priority，priority 使用 low、normal、high。
- scheduled_date、due_at、completed_at，允许为空。
- position、version、client_request_id。
- created_at、updated_at、deleted_at。
- tags，通过中间表关联。
- materials，通过 TaskMaterial 关联。

建议索引包括 owner、deleted_at、scheduled_date、status 的列表访问组合，以及 owner、due_at 和 owner、completed_at。具体索引应以查询计划和实际过滤条件为依据。

### 5.4 DailyEntry 与 Tag

DailyEntry 包含 owner、date、content、version、created_at、updated_at。正文建议限制 50000 字符，owner 与 date 唯一。

Tag 包含 owner、name、color。规范化名称后，对 owner 与规范化名称建唯一约束。首版只支持单层标签。

### 5.5 Folder 与 Material

Folder 包含 id、owner、name、position、version、deleted_at。首版采用单层资料夹，提供“全部资料”和“未分类”视图。

Material 包含以下字段。

- id、owner、folder。
- original_name、storage_key、detected_mime、size_bytes、sha256。
- remark、tags。
- source 为 desktop、qr 或 transfer_copy。
- state 为 pending、ready、failed 或 deleting。
- version、created_at、updated_at、deleted_at。
- upload_receipt，可空且唯一，用于与一次上传关联。

storage_key 必须由服务端生成。original_name 只用于展示与下载命名。客户端提供的 MIME 与 size 只能用于预检查，最终值由实际文件决定。

sha256 用于完整性核验和提示可能重复的文件。首版允许用户重复上传，不做跨账号文件去重，也不返回其他账号是否拥有相同文件。

### 5.6 TaskMaterial

- task、material、created_at。
- task 与 material 建唯一约束。
- 两侧对象必须属于同一 owner。
- 删除关联只移除关联关系。
- Material 在回收站时，任务详情显示“附件已移入回收站”，恢复后重新可用。

### 5.7 UploadSession

- id、owner、token_digest。
- destination_folder、destination_task，均可空。
- state 为 active、revoked 或 closed。
- expires_at、created_at、revoked_at。
- max_files、max_bytes、max_file_bytes。
- reserved_files、reserved_bytes、committed_files、committed_bytes。
- auth_version，用于账号安全状态变化后的统一撤销。

UploadSession 的目标在创建时由服务端验证并固定。后续上传请求不能更换 owner、任务或资料夹。

### 5.8 UploadReceipt

- id、session、client_upload_id，session 与 client_upload_id 唯一。
- original_name、declared_size、actual_size、sha256。
- state 为 reserved、receiving、committed、failed 或 expired。
- lease_expires_at、created_at、updated_at、failure_code。
- material，可空且唯一。
- attempt_id 或等价的条件更新标识，用于阻止同一收据被并行写入。

这个模型承担上传重试、配额预占、结果查询和异常清理。文件系统写入不能放进长时间数据库事务中。

## 6. 扫码上传的完整交互

### 6.1 电脑端

1. 在资料库、资料夹或任务详情点击“手机上传”。
2. 登录态接口创建 UploadSession，返回二维码地址、过期时间和配额。
3. 弹窗显示目标位置、二维码、剩余时间、上传结果和“停止接收”按钮。
4. 用户可以重新生成二维码。重新生成应先撤销旧会话。
5. 电脑每 3 秒查询会话状态，页面隐藏时降低频率或暂停。关闭弹窗后停止轮询。
6. 上传完成后在列表中增量显示新资料，按 material.id 去重。
7. WebSocket 推送可作为增强，刷新或重新连接后仍以状态接口为准。

关闭弹窗默认执行撤销。若撤销请求网络失败，应明确显示“停止接收未确认”，服务器仍以 expires_at 为最后约束。不能仅凭前端关闭就宣称二维码已经失效。

### 6.2 手机端

手机相机、系统扫码或微信扫一扫打开标准 HTTPS 页面。

页面展示“向工作台上传资料”、安全的目标提示、文件限制、剩余时间、选择文件和拍照按钮。手机界面不展示拥有者的任务描述、全部资料、聊天记录或账号日志。

文件选择支持多选。手机拍照可使用单独的 capture 输入，普通文件输入继续提供系统文件选择器。针对 iOS Safari、Android Chrome 和微信内置浏览器进行真机或明确记录的兼容性测试。

一次选择多个文件后，每个文件各自发送一个上传请求。当前 Django 配置 DATA_UPLOAD_MAX_NUMBER_FILES=1，需沿用每请求一个文件的行为。

展示每个文件的进度、成功、失败原因和单独重试按钮。列表整体显示已完成数量。用户再次打开页面时可以通过重新扫描有效二维码恢复会话查询。

### 6.3 二维码中的凭证

建议链接形态为 https://工作台域名/upload#session=<uuid>&token=<random_token>。

- token 使用安全随机数生成，建议至少 32 随机字节。
- 数据库保存 token 的摘要。原始 token 仅在会话创建响应中返回。
- fragment 由前端读取后立即使用 history.replaceState 清除地址栏中的敏感内容。
- 浏览器将 token 留在当前页内存，用专门的上传请求封装发送 Authorization: Upload <token>。
- 手机页面刷新后若内存凭证丢失，提示重新扫码。
- token 不写入 localStorage，不放进二维码图片生成服务，不加载外部统计脚本。
- 二维码由前端本地编码库生成。库需固定版本，文本内容、二维码和图片调试日志都不能包含真实账号 Token。
- 请求与错误日志对 Authorization、上传凭证和二维码链接做脱敏。
- 手机路由设置 Referrer-Policy: no-referrer 和适合该页面的 CSP。
- 上传权限限制在专用路由。账号 Token 与 Upload Token 采用分开的认证类与请求封装。

持有二维码即可在有效期内投递文件，所以二维码页面要显示“持有码者可向此处上传”。首版支持同一会话多次投递，不把它误写成一次性扫码。

### 6.4 默认限制与撤销规则

以下数值为首版建议，使用配置项实现。

- 会话有效期 10 分钟。
- 每个账号最多同时存在 3 个有效会话。
- 每会话最多 20 个成功文件，成功与在途文件合计最多 500 MiB。
- 每个文件最多 100 MiB，手机端默认串行上传。
- 在有效期内拿到收据后，该次上传最多再持续 20 分钟，同时受单请求超时约束。
- 到期后拒绝新的预占，已经合法预占的上传可以在收据截止时间前完成。
- 手动撤销、账号被停用、退出该账号全部会话或重置密码，应使相应上传会话失效。
- 手动撤销优先于收据宽限期。接收文件结束时必须再次检查撤销状态。
- 上传已提交成功之后的撤销只阻止后续写入，成功文件继续保存在资料库。

auth_version 可采用独立的一对一安全状态记录，由密码重置、全局登出和停用操作递增。创建上传会话时记录其值，预占和最终提交都比对该值。

### 6.5 本地扫码与服务器扫码

手机扫描 localhost 或 127.0.0.1 会访问手机自身。开发二维码应使用手机能访问的电脑局域网地址，服务器二维码使用显式配置的 PUBLIC_BASE_URL。

PUBLIC_BASE_URL 必须由部署方提供。生成二维码时不要信任客户端 Host 或任意 forwarded header 拼接域名。

开发时允许同一局域网的明确地址与端口，配置 Vite、Django hosts、Origin 和防火墙。生产落地页使用 HTTPS。域名或手机网络不通时，页面和文档要指出可验证的原因。

## 7. 上传一致性与文件保护

### 7.1 上传流程

1. 手机向准备接口提交文件名、声明大小与 client_upload_id。
2. 服务端验证 token、目标、有效期和配额，短事务内建立 UploadReceipt 并预占文件数与字节数。
3. 同一请求 ID 已成功时直接返回原收据。已在接收时返回当前状态。元信息不一致时返回 409。
4. 手机向收据内容接口提交单文件 multipart。后端先鉴权，再使用受控流式写入保存到临时目录。
5. 写入过程中统计实际字节并计算摘要。实际大小超过预占大小或单文件上限时中止。
6. 核验文件类型和内容特征，将文件放到服务端生成的最终路径。
7. 再次检查会话撤销、目标状态和配额，事务内创建或转为 ready 的 Material，建立 TaskMaterial 并提交收据。
8. 失败后释放预占、删除临时内容，保留可读 failure_code。允许重试时重新预占和重新获取写入权。
9. 进程在文件写完、数据库提交前崩溃时，由定时清理命令识别孤儿文件或 pending 记录，进行补偿。

首版整文件失败重传。为以后增加分片保留收据标识，首版界面只显示已实现的恢复能力。

### 7.2 并发和重试规则

- 配额检查与预占要原子执行。PostgreSQL 可使用行锁与事务。
- SQLite 的 select_for_update 不能提供同等锁语义。开发模式需要条件更新或明确的写入串行化，不能仅靠 Python 内存锁应付多进程。
- 同一收据在同一时刻只允许一个上传请求进入 receiving。
- 失败补偿也要比较状态或 attempt_id，避免重复释放配额。
- 预占字节与实际字节分开统计。成功后释放多余预占，以实际大小计入账号存储。
- 仅重试同一收据不能制造第二个 Material。
- 每个文件以真实数据落库成功为完成依据。浏览器上传进度到 100% 时先显示“服务端处理中”。

扫码目标若在上传期间被删除或归档为不可写，应在最终提交时返回明确错误，释放预占并清理暂存文件。即使页面上还保留旧任务名称，服务端也必须重新验证目标状态。

### 7.3 文件限制与下载

首版私人资料库以常见图片、PDF、TXT、Markdown、Office 文档、音视频和压缩包为可选类型，具体允许列表集中配置。对于需要浏览器预览的类型核验内容特征，压缩包和 Office 文档按下载处理，避免上传后自动解压或执行。

服务端校验扩展名、实际内容特征、大小、文件名长度，存储使用随机路径，上传目录放在静态站点目录之外。客户端 MIME 仅作提示。上传校验原则参考 OWASP 的文件上传指南。[OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)

下载接口先验证 owner，再读取文件。默认 Content-Disposition 为 attachment。预览采用已校验的类型与现有安全渲染器，SVG 和 HTML 按下载处理。PDF 预览需要核对签名和浏览器沙箱行为。

较大的音视频不能全部读入 Blob 后才播放。首版可以设定预览大小阈值，超限提供下载。后续流媒体预览需增加鉴权 Range 支持。

文件永久删除采用可重试流程。记录先标记 deleting，文件删除成功后再完成数据库清理。出现磁盘权限或对象存储错误时保留失败状态，避免记录消失但物理文件长期残留。

### 7.4 磁盘与匿名上传

增加账号存储配额和全站存储预算，使用实际文件字节数核算。软删除文件仍计入配额，永久删除成功后才释放。

公开中转站沿用已有公开上传能力，同时增加按真实来源地址限速、总文件数及总容量预算。个人工作台的扫码配额与公开中转站分开统计，但共享服务器总存储预算。

反向代理临时文件、Django 临时文件、应用接收文件都消耗磁盘，部署说明要考虑同时存在的副本。低磁盘水位时拒绝新上传，已成功文件继续可读。

清理命令支持 dry-run，限定在配置的临时与媒体根目录内。路径必须经过规范化校验，禁止根据用户文件名直接删除路径。

## 8. API 合同

所有下列新接口均返回 JSON，二进制下载与文件内容上传除外。新接口单独定义 Serializer，不将任意 request.data 直接写入模型。

分页默认每页 50，最大 100。列表使用稳定排序，包含 id 作为最终排序键。过滤参数需要类型、日期范围和长度校验。

### 8.1 工作台与任务

- GET /api/workspace/today/?date=YYYY-MM-DD，返回指定本地日期的今日任务、待重新安排数量、逾期数量、当日完成数和每日记录摘要。
- GET /api/tasks/，支持 scheduled_date、status、project、tag、q、page 和 page_size。
- POST /api/tasks/，创建任务。
- GET、PATCH、DELETE /api/tasks/<uuid>/，读取、更新、软删除。
- POST /api/tasks/<uuid>/restore/，恢复。
- POST /api/tasks/reorder/，提交当前列表顺序与对象版本。
- POST /api/tasks/<uuid>/materials/，关联本人资料。
- DELETE /api/tasks/<uuid>/materials/<material_uuid>/，解除关联。

示意创建请求如下，日期仅作合同示例。

```json
{
  "client_request_id": "a443fefa-a95b-491b-9d06-de23084b117b",
  "title": "整理今天收到的资料",
  "description": "",
  "status": "todo",
  "priority": "normal",
  "scheduled_date": "2026-11-15",
  "due_at": null,
  "project": null,
  "tags": []
}
```

完成任务使用 PATCH 提交 status=done 与 version。owner、completed_at、created_at 由服务端决定。

### 8.2 项目、记录与资料

- GET、POST /api/projects/。
- GET、PATCH、DELETE /api/projects/<uuid>/。
- POST /api/projects/<uuid>/restore/。
- GET /api/journal/<YYYY-MM-DD>/，返回当天正文和版本。不存在时返回明确的未创建状态。
- PUT /api/journal/<YYYY-MM-DD>/，按 owner、date 创建或更新，携带 version。首次创建的并发冲突返回 409。
- GET、POST /api/tags/，以及 PATCH、DELETE /api/tags/<uuid>/。
- GET、POST /api/library/folders/，以及 PATCH、DELETE /api/library/folders/<uuid>/。
- GET /api/library/materials/，按资料夹、标签、文件类型、日期和关键词筛选。
- POST /api/library/materials/，登录用户的桌面上传入口，复用文件接收服务。
- GET、PATCH、DELETE /api/library/materials/<uuid>/。
- POST /api/library/materials/<uuid>/restore/。
- GET /api/library/materials/<uuid>/download/。

回收站列表可通过 deleted=true 过滤获取，仅返回本人记录。永久删除动作使用独立的 purge 接口，前端明确提示并要求确认。

### 8.3 电脑管理上传会话

- POST /api/upload-sessions/，使用账号认证，提交目标任务或资料夹。
- GET /api/upload-sessions/<uuid>/，使用账号认证，返回本人会话状态与收据摘要。
- POST /api/upload-sessions/<uuid>/revoke/，由会话拥有者撤销，重复调用仍成功。

创建会话响应包含 id、upload_url、expires_at、limits。upload_url 仅本次返回，响应必须 no-store。

### 8.4 手机上传接口

专用认证类识别 Upload 凭证，以下接口不接受该凭证执行其他业务。

- GET /api/mobile-upload/<session_uuid>/，返回是否可上传、限制及该会话的安全收据摘要。
- POST /api/mobile-upload/<session_uuid>/prepare/，创建或获取文件收据。
- POST /api/mobile-upload/<session_uuid>/receipts/<receipt_uuid>/content/，发送文件内容。
- GET /api/mobile-upload/<session_uuid>/receipts/<receipt_uuid>/，查询本次结果。

手机返回内容只包含会话内文件名、进度状态、大小和错误。手机接口不返回私人文件下载 URL、磁盘路径、账号信息或任务正文。

建议错误合同包含 code、detail 和可选 request_id。

- 400 用于输入或文件格式错误。
- 401 用于缺少或无效凭证。
- 403 用于当前账号无功能权限。
- 404 用于目标不存在或不属于当前访问范围。
- 409 用于版本、幂等内容或并发状态冲突。
- 410 用于已验证凭证对应的会话过期或撤销。
- 413 用于文件大小超限。
- 429 用于频率或同时上传数限制，提供 Retry-After。
- 503 用于暂时无法接收或存储预算不足，返回 storage_unavailable 等稳定 code。

## 9. 权限与信息边界

### 9.1 新工作台的权限

qzx 与 sqx 都可操作自己的任务、项目、记录、标签和资料。工作台默认不开放跨账号查看。

知识集合、个人记忆、引用和导出沿用同一隔离边界；具体规则与接口见第 16 节。

中转站最高管理员权限仍由原模块管理。不能直接把 IsTransferAdmin 用于私人资料库并因此授予所有私人资料访问权。

对象读取、编辑、删除、下载、恢复、任务资料关联和统计查询全部在服务端按 owner 过滤。上传目标、标签 ID、项目 ID 和资料 ID 都要做归属校验。

新 workspace 权限使用显式 allowlist 或清晰的角色能力配置。现有 agent 的“排除游客”规则不能直接等同于新工作台准入规则。

### 9.2 扫码权限

扫码 token 仅绑定会话和目标，不能换取账号登录 Token、改变会话目标、下载资料、修改任务、查询全部资料或获得其他会话状态。

解析 multipart 之前应尽早校验会话凭证和大小预算。反向代理允许匿名请求进入扫码专用接口，不代表 Django 可以省略鉴权。

### 9.3 前端与服务端安全

- 私人 API 响应禁止公共缓存。
- 新页面的富文本使用安全 Markdown，危险 HTML 与脚本不能进入 v-html。
- 上传文件名、备注与服务端错误均以文本输出。
- 新增 WebSocket 推送按 owner 建组并在握手、收发时鉴权。
- 日志记录操作者、动作、对象 ID、结果、时间与脱敏请求标识，避免记录文件正文、完整每日记录、聊天上下文或密钥。
- 本次可以沿用现有 Token 登录，以减少同步迁移范围。部署说明应明确它在浏览器中的存放方式，并提供 Token 撤销行为。
- 如另行迁移为 HttpOnly Cookie，会同时涉及登录、CSRF、下载、WebSocket 和跨域部署，需要独立完成全链路回归。

## 10. 前端实施说明

### 10.1 建议新增文件

- frontend/src/views/TodayView.vue。
- frontend/src/views/TasksView.vue。
- frontend/src/views/ProjectsView.vue。
- frontend/src/views/JournalView.vue。
- frontend/src/views/LibraryView.vue。
- frontend/src/views/MobileUploadView.vue。
- frontend/src/views/KnowledgeView.vue、KnowledgeMemoriesView.vue。
- frontend/src/components/tasks/TaskQuickAdd.vue、TaskList.vue、TaskDetailPanel.vue。
- frontend/src/components/library/MobileUploadDialog.vue、UploadQueue.vue。
- frontend/src/components/knowledge/KnowledgeScopePicker.vue、CitationDrawer.vue、MemoryEditor.vue。
- frontend/src/api/workspace.ts、tasks.ts、journal.ts、library.ts、uploadSessions.ts。
- frontend/src/api/knowledge.ts 及独立的知识库状态管理。
- 按业务需要新增 Pinia store，避免把所有新数据塞进现有 agent store。

新增 API 封装复用已有 axios 实例，手机 Upload 凭证采用独立实例。更改列表或详情后，主动更新相关缓存，避免今日页面和全部任务展示两个状态。

### 10.2 展示与状态

沿用现有字体、图标、颜色与控件样式。工作台以清晰任务列表和资料操作为主。首页只保留与当天行动有关的统计。

主要操作覆盖加载、空列表、验证失败、网络断开、权限失效、文件超限、重试与成功状态。

最低验收宽度为 360px，桌面检查 1366px。按钮点击区域适合触屏，表单标签明确，状态变化使用 aria-live 或 role=status，弹窗具有焦点管理与关闭行为。

二维码在桌面上足够清晰，具备留白和高对比度。窄屏下可以折叠配额详情，但目标位置与有效期仍可见。

完成状态同时使用图标或文字，避免仅用颜色区分。日期本地化输出，用户输入中的中文、emoji、长文件名和多行内容不会撑破布局。

### 10.3 查找与性能

首版普通业务搜索覆盖任务标题、项目名称、资料名和资料备注。知识库另按第 16 节检索已加入的正文片段。每日记录使用日期导航，未加入知识库的记录不自动纳入 AI 检索；全站统一搜索列入后续阶段。

后端先做数据库分页与普通条件查询。避免一次向前端返回全部文件或全部任务。任务统计应使用数据库聚合，详情关联使用 select_related 或 prefetch_related。

Blob URL 在关闭预览、切换文件和组件销毁时释放。用户切换账号时清理尚未完成的上传、请求和预览引用。

## 11. 后端实施说明

### 11.1 模块边界

建议新增 backend/workspace/、backend/tasks/、backend/journal/、backend/library/、backend/knowledge/。扫码会话与收据可以放入 library，知识模型与索引作业集中在 knowledge，避免首版为每个实体创建独立 Django app。

workspace 负责偏好与首页汇总，tasks 负责项目、任务、标签与任务资料关系，journal 负责每日记录，library 负责资料、文件接收和上传会话。

knowledge 负责知识集合、来源版本、分段、检索、个人记忆与索引作业。agent 继续负责会话、模型协议和流式输出，通过明确的服务接口调用 knowledge；检索服务不直接修改任务或执行文件操作。

文件写入、大小限制、权限检查和清理使用可测试的服务函数复用。业务 View 不应重复实现四套相近的文件接收逻辑。

已经保存的 TransferFile、AgentAttachment 和 ChatMessage 文件先继续由各自模块管理。私人资料库采用独立数据模型，跨模块复制使用显式流程。

### 11.2 事务与清理

短事务完成权限检查、版本检查、配额预占和记录提交。网络等待和磁盘大文件传输在事务外执行。

增加可重复运行的管理命令，完成过期上传收据回收、临时文件清理、deleting 文件重试和回收站过期清理。使用系统定时器或受监督的调度服务运行，并记录最后成功时间。

回收站默认保存 30 天，作为可配置的产品默认值。首次运行清理命令应支持 dry-run 输出数量和目标范围。

### 11.3 AI 连接检测与已有功能

模型测试接口继续使用现有代理、密钥选择和安全检查。新增资料库不能把任意私人文件自动发到模型。

上传资料后，用户显式选择“发送给 AI”才可以读取、转换并加入当前会话附件。转换需核对文件所有权，受 AI 附件 25 MiB 与解析限制约束，原文件大小上限不能直接沿用为 AI 输入上限。

知识库采用另一条明确入口：用户将内容加入知识库，并在会话中启用选定集合后，后续提问可按范围自动检索相关片段，无需对每个片段反复确认。界面应说明相关文本将发送至当前配置的模型服务。文件原件不会因此作为整份附件自动发送；关闭范围后不得继续自动注入对应资料。

测试连接成功仅表示指定协议下收到一次模型文本响应，不能据此声称该模型已支持图像、所有工具或所有文件格式。

## 12. 服务器部署方案

### 12.1 推荐拓扑

浏览器通过 HTTPS 访问 Nginx。Nginx 提供前端 dist，并将 /api/ 和 /ws/ 转发到 Daphne。Django 连接 PostgreSQL，Channels 与缓存使用 Redis。文件保存在持久化卷，清理与备份通过受监督的定时任务执行。

知识解析由独立、受监督的 knowledge-worker 运行，作业状态持久化在数据库。首版可采用带租约的 Django 管理命令轮询作业表；不得依赖请求线程、内存队列或 Channels 广播保证作业完成。开发环境同时提供执行一次待处理作业的命令。

开发可以使用 SQLite 和进程内 Channels，正式服务器使用 Redis Channel Layer，避免多进程聊天广播互相隔离。Channels 官方文档说明 InMemoryChannelLayer 只在各进程内部保存状态，生产支持的官方层为 channels_redis。[Channels Channel Layers](https://channels.readthedocs.io/en/stable/topics/channel_layers.html)

### 12.2 需要交付的部署文件

- backend/Dockerfile。
- 前端构建与 Nginx 静态服务镜像定义。
- compose.yaml，服务至少包含 web、backend、postgres 和 redis。
- deploy/nginx.conf 或等价模板。
- .env.example，只包含变量名与非敏感示例。
- deploy/backup 与 deploy/restore 脚本。
- 部署、升级、回滚和故障排查说明。
- 如清理任务通过独立 scheduler 服务执行，应在 Compose 中明确其启动和日志。
- knowledge-worker 的启动命令、资源上限、作业重试和健康状态；与 backend 使用相同代码版本、数据库及必要的受限媒体挂载。

镜像构建使用锁定依赖，运行用户采用最小文件权限。数据库、媒体、备份和密钥挂载在独立持久化位置。

### 12.3 环境变量与配置

已有变量继续支持 DJANGO_DEBUG、DJANGO_SECRET_KEY、DJANGO_ALLOWED_HOSTS、DJANGO_CORS_ORIGINS、DJANGO_CSRF_TRUSTED_ORIGINS、NEXUS_MASTER_KEY、NEXUS_BUILTIN_LLM_API_KEY、NEXUS_LLM_PRIVATE_ORIGINS、NEXUS_TRUSTED_PROXY_HOPS。

建议新增 DATABASE_URL、REDIS_URL、PUBLIC_BASE_URL、MEDIA_ROOT、UPLOAD_SESSION_TTL_SECONDS、UPLOAD_MAX_FILE_BYTES、UPLOAD_SESSION_MAX_BYTES、UPLOAD_SESSION_MAX_FILES、STORAGE_QUOTA_BYTES、UPLOAD_TEMP_ROOT、TRASH_RETENTION_DAYS 和 BACKUP_DIR。

知识库另需可配置的解析大小、页数、文本量、每账号索引配额、作业超时与重试次数、检索片段数和上下文预算。集中在 knowledge 配置中，需部署调整的值映射为 KNOWLEDGE_ 前缀的环境变量；变量名、单位和默认值以交付的 .env.example 为准。

上述新增变量当前尚未实现。交付时要提供解析、默认值、错误提示及 .env.example 说明，不能只在文档里出现变量名。

生产启动时校验密钥、数据库、媒体目录可写性和 PUBLIC_BASE_URL。检查 DEBUG 关闭，hosts 指向实际域名，代理可信跳数与实际网络拓扑一致。[Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)

### 12.4 Nginx 与连接

- SPA 页面使用 history fallback，/api/、/ws/ 和真实静态文件的错误不能回落成 index.html。
- /api/agent/chat/ 保持 SSE 分段返回，代理关闭响应缓冲，超时与模型等待行为一致。
- /ws/ 显式设置 Upgrade 和 Connection，并验证现有子协议能穿过代理。
- 允许文件体积的网关限制与业务上限配套，既有中转站 500 MiB、聊天 80 MiB、AI 附件 25 MiB 和新扫码上传上限分别校验。
- multipart 边界也占用字节，网关上限需要为封装留出少量余量。
- /media/ 不设置公共直连映射。若使用内部加速下载，由 Django 先鉴权，再走 Nginx internal 路由。
- 上传临时目录设置独立预算，拒绝超大请求时返回可读错误。

Nginx 文档说明响应缓冲关闭后会边接收边转发，上游也可通过 X-Accel-Buffering 控制该行为。WebSocket 升级头需要明确转发。[Nginx response buffering](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering) [Nginx WebSocket proxying](https://nginx.org/en/docs/http/websocket.html)

### 12.5 数据迁移

1. 记录现有数据库迁移状态，清点账号、任务前身数据、会话、日志、文件数量及媒体根目录。
2. 对数据库、媒体和主密钥做可恢复备份。升级窗口内停止写入。
3. 在副本上验证旧密码迁移、uploader 外键回填和新模块迁移。
4. SQLite 转 PostgreSQL 时通过 Django 模型层或经过验证的数据迁移命令导入。明确处理 auth、contenttypes、权限、Token、外键和数据库序列。
5. 对比各模型记录数、关键外键、文件路径、文件大小和抽样摘要。
6. 用原主密钥验证已保存模型 Key 仍可解密，测试输出中只记录成功或失败。
7. 在迁移后的库上执行核心业务验收，再切换实际服务。
8. 需要回滚时恢复与原版本匹配的数据库及媒体快照。仅回退镜像无法撤销已经发生的结构和数据变化。

### 12.6 备份、恢复与运行状态

建议每日自动备份数据库和文件，备份保存至独立位置，记录备份时间、大小、结果和保留策略。密钥与数据库分别保护，但恢复流程必须能够取回对应密钥。

PostgreSQL 可以使用 pg_dump 输出数据库备份，恢复方案需与导出格式对应。数据库备份本身不包含应用媒体文件。[PostgreSQL backup documentation](https://www.postgresql.org/docs/current/backup-dump.html)

个人使用首版可在短维护窗口中暂停写入后备份数据库与媒体，确保文件关联一致。若采用在线备份，应设计文件清单与延迟清理机制。

至少在独立目录或测试实例演练一次恢复，验证登录、私人文件下载、资料归属、AI Key 解密和任务记录。

恢复演练还应覆盖知识正文、源文件、个人记忆、来源关系和引用元数据。索引可重建，但不能只备份索引而丢失原文。恢复后使缓存失效，回收失去租约的作业，核验停用和删除记录没有重新进入检索。

增加轻量存活与就绪检查，分别反映进程状态以及数据库、Redis 等依赖状态。记录磁盘占用、错误率、上传失败数、清理任务最后成功时间和备份最后成功时间。

## 13. 验收清单

以下清单按用户可观察的行为验收。每一项应提供自动化结果、截图或可复现步骤，注明采用的环境与数据。

### 13.1 基础和隐私

- [ ] 原 AI 对话、测试连接、双人聊天和中转站入口可用。
- [ ] qzx 登录默认进入今日页面，yk 仍进入中转站。
- [ ] sqx 无法通过猜测 UUID、标签、项目、查询过滤条件或下载地址读取 qzx 的私人工作台数据。
- [ ] 切换账号后页面和 KeepAlive 缓存中没有上个账号的私人内容。
- [ ] owner 等只读字段无法通过请求体覆盖。

### 13.2 每日任务与记录

- [ ] 新建、刷新、编辑、完成、重新打开、取消、删除、恢复都正确。
- [ ] 同一任务连续点两次完成不会重写完成时间。
- [ ] 快速添加遇到网络重试时只产生一条任务。
- [ ] 昨日计划未完成与真正逾期采用不同条件。
- [ ] 23:59 至 00:01 跨日、空截止时间、UTC 转换和日期筛选正确。
- [ ] 两个浏览器同时修改一条任务或每日记录时，后提交的旧版本得到冲突提示。
- [ ] 项目归档、软删除和恢复后，任务仍能找到与调整。
- [ ] 每日记录保存失败时正文保留，刷新前能知道存在未保存修改。

### 13.3 资料与扫码

- [ ] 电脑生成二维码后，真实手机可打开上传页并上传照片和 PDF。
- [ ] 单次多选至少 3 个文件，逐文件反馈结果，失败文件可独立重试。
- [ ] 上传完成后电脑在两个轮询周期内显示结果，刷新后结果仍存在。
- [ ] 上传到任务时同时进入本人资料库并建立正确附件关联。
- [ ] 会话过期、主动撤销、改密和全局登出后的新写入被拒绝。
- [ ] 随机或他人会话 ID、错误凭证、拿 Upload Token 调私人下载接口都失败。
- [ ] 到期前预占、到期后完成与主动撤销的行为符合第 6.4 节。
- [ ] 超大小、伪造 MIME、异常文件名、重复提交和两个并发上传的边界正确。
- [ ] 断网、写盘失败、进程中断、提交后响应丢失都不会留下重复资料或永久占用配额。
- [ ] 删除目标任务或资料夹期间的上传能给出明确失败，释放预占并清理暂存文件。
- [ ] 数据库和正常日志中不存在二维码原始 token。
- [ ] 私人资料不会自动出现在公开中转站。

### 13.4 上线与恢复

- [ ] 从空环境可按文档启动，同一操作可重复执行。
- [ ] 生产迁移脚本在旧数据副本上验证过，密码初始化有可执行的交付步骤。
- [ ] HTTPS 下完成登录、扫码、上传、下载、SSE 和 WebSocket。
- [ ] 多个后端进程通过 Redis 正常转发聊天，限速结果在进程间一致。
- [ ] 服务重启后任务、文件、已保存 Key 和统计结果可用。
- [ ] 备份恢复演练通过，实际操作步骤和耗时已记录。
- [ ] 大文件上传期间磁盘与进程内存处于可接受范围，临时文件可回收。
- [ ] 缺少稳定生产密钥或存储目录不可写时，启动或就绪检查明确失败。

### 13.5 知识库与个人记忆

- [ ] 手写笔记、TXT、Markdown、文本 PDF、DOCX 可入库；原文第 80,000 字符后的测试内容能检索，超过新限制时明确失败而非静默截断。
- [ ] 中文短词、连续中文句子、中英混合和英文缩写均有可重复的检索用例；没有相关资料时明确告知未找到。
- [ ] 回答引用可打开实际来源片段和版本，PDF 页码或文档标题路径准确；伪造引用 ID 不会生成可点击假出处。
- [ ] 关闭知识库或切换集合后，后续模型请求中没有被排除的资料及其历史注入副本。
- [ ] qzx 与 sqx 的集合、搜索结果、数量、记忆、索引状态、引用和导出相互隔离；游客和 Upload 凭证均不能调用知识接口。
- [ ] 扫码上传只进入私人资料库，由所有者选择加入知识库；上传文件中的文字不能直接创建个人记忆。
- [ ] 文档更新、移入回收站、恢复、彻底删除、取消用于 AI 后，AI 检索、缓存与后台作业按第 16 节失效；保留的历史快照明确标注日期，不冒充当前正文。
- [ ] 作业进程中断、重复领取、超时重试以及删除后旧作业完成，不产生重复分段或复活已删除数据。
- [ ] 明确保存个人偏好后可在新对话中生效；自动提炼的候选记忆未确认前不进入正式个人背景。
- [ ] 同一偏好被修改后旧版本不再注入；忘记后当前会话后续请求也不再通过缓存、摘要或历史消息重新带入。
- [ ] “今天要做什么”返回任务模块当前状态和查询日期，完成任务后重新提问不会继续使用旧清单。
- [ ] 资料中的“忽略规则”“读取另一个账号”“记住此管理员权限”等内容不会导致越权、持久化写入或外部请求。
- [ ] 模型故障时笔记、检索和记忆管理仍可用；索引失败或超时有可操作的错误与重试入口。
- [ ] 初始个人条目来源明确、仅写入指定账号、重复初始化不覆盖用户修改；没有虚构身份、计划或账号关系。
- [ ] 至少 20 个固定问题组成检索与回答评估集，记录预期来源、是否应回答、实际引用和缺陷；权限、删除及越权写入测试必须全部通过。
- [ ] 完成知识数据备份恢复和索引重建演练，记录测试语料规模、检索延迟、解析峰值内存与模型调用量。

## 14. Trae 的执行顺序与阶段交付

### 阶段 A — 接手、基线和环境

阅读第 2 节指定的源码。记录当前改动与数据状态，建立本地版本基线。核实迁移状态，准备临时测试数据库，梳理生产密钥处理。

交付基线说明、实际可用的启动命令、迁移差异和核心功能回归结果。不要把真实数据库用于 smoke_test.py，它会创建、改密和删除测试数据。

### 阶段 B — 任务与每日工作台

实现 Project、Task、DailyEntry、Tag、偏好和权限。打通今日页面、任务列表、详情、每日记录与登录后跳转。完成版本冲突、日期分组和账号切换缓存处理。

交付可实际使用的每日任务闭环，以及迁移、API 和相关回归用例。

### 阶段 C — 私人资料库

实现 Folder、Material、TaskMaterial、上传接收服务、预览下载和回收站。提供按名称、标签和资料夹搜索。

交付桌面上传、任务附件、权限隔离、失败补偿与清理命令。

### 阶段 D — 手机扫码上传

实现 UploadSession、UploadReceipt、手机页面、二维码弹窗和轮询。完成预占、幂等、撤销、到期与令牌脱敏。

交付电脑加手机的完整演示，以及限额、断网、重试和并发回归。

### 阶段 E — 个人知识库与 AI 记忆

按第 16 节实现集合、笔记、资料导入、持久化解析作业、正文分段、中文检索、来源引用和个人记忆管理。接入现有 AI 对话，加入知识范围选择、记忆开关和只读的今日任务查询。

先交付无需模型即可使用的知识管理与搜索，再接入模型回答和明确授权的记忆写入。最后执行个人条目初始化、更新与忘记的完整验证。不得用一个长 system_prompt 或把全部文件塞进每轮聊天替代该模块。

交付迁移、worker 命令、API、页面、固定评估样本和第 13.5 节结果。首版关键词方案可验收，向量增强不阻塞后续部署。

### 阶段 F — 服务器就绪

完成 PostgreSQL、Redis、环境配置、Compose、Nginx、迁移和备份恢复脚本。解决第 2.5 节列出的上线差距。

交付在测试部署环境中可执行的启动与恢复流程。缺少真实服务器信息时，明确列出待填变量和未执行的上线检查。

### 阶段 G — 总体验收

逐项执行第 13 节，修复结果不一致的地方。检查前端构建、后端迁移、旧功能回归、上传权限、知识引用、记忆撤回与备份恢复。

交付修改清单、测试结果、部署说明、回滚步骤、默认值清单、已知限制和下一阶段建议。版本交付不得只包含界面截图。

阶段之间采用可运行的增量，每个阶段完成后再进入下一个。开发过程可以提交进度，不需要等待用户对普通代码修改逐次确认。

## 15. 后续扩展路线

以下功能先保留接口演进空间，首版不需要为它们提前搭建庞大基础设施。

### 15.1 重复任务、周视图和习惯

增加日历周视图和按天或指定星期重复的任务模板。模板与实例分开，模板、owner、occurrence_date 建唯一约束。

每日生成任务由持久化调度触发，页面打开时做有限补偿。生成任务幂等，不能仅在浏览器凌晨运行。

编辑支持“仅本次”和“此后全部”。跳过日期单独记录。删除实例时写入例外状态，防止后台再次生成。已完成历史实例保留原内容，模板变更从指定生效日开始。

### 15.2 提醒

首阶段提醒采用站内到期标记。后续真正的离线提醒需要服务端调度与浏览器推送或外部通知服务。

通知记录使用唯一发送标识，处理重复执行、失败重试、用户取消和时区变化。页面内 setTimeout 只能承担打开页面期间的提醒。

### 15.3 AI 辅助整理

第 16 节的知识问答、引用、笔记保存和个人记忆属于首版。后续可增加把自然语言拆成任务草稿、自动每日总结、多份资料综合摘要和按项目整理笔记。

AI 先生成可编辑草稿，再由用户提交保存。只读取当前账号明确选择的数据，文件内容中的指令不得获得任务修改或文件发布权限。

使用现有模型配置和代理。模型未配置或连接失败时，基础任务与资料操作仍可使用。

### 15.4 OCR、检索增强与离线

首版已支持加入知识库的文本检索。后续增加扫描件 OCR、全站统一搜索、向量与关键词混合检索、重排序；沿用第 16 节的后台作业、版本、权限和来源机制。OCR 未实现时，扫描件应显示“需要 OCR”，不能显示为已成功理解全文。

PWA 首先提供安装入口与静态资源缓存。离线新增任务需要队列、幂等和冲突合并设计，敏感文件和密钥不应默认进入公共缓存。

对象存储、分片续传、共享项目、日历订阅和第三方同步各自作为独立迭代。每项都要给出实际触发场景和验收条件。

## 16. 个人知识库与 AI 记忆实施要求

### 16.1 定位与个性化依据

这部分让工作台中的 AI 能持续利用本人资料和已确认偏好。成功标准是：找得到原文、说得清来源、能更新事实、能忘记信息，且不影响日常任务与原有 AI 功能。

个性化依据仅限本次交接可核实的对话。当前没有完整个人档案或可导入的跨平台记忆导出，不得把推测写成用户事实。姓名、职业、学校、考试计划、健康情况、家庭关系、固定作息均不预填。账号名称仅是权限标识，不用于推断真实身份或关系。

可初始化的内容如下，来源统一记为“2026-11-14 用户在本项目交接对话中的明确要求”，scope 均为 zixxx 项目，evidence_type 为 user_explicit：

1. `workbench_goal`：用户希望将现有项目建设为个人工作台，记录每天要做的事情，并逐步扩展个人管理功能。
2. `mobile_material_input`：用户需要手机扫码上传资料，并能在电脑端继续使用这些资料。
3. `server_deployment_goal`：用户计划后续将项目部署到服务器；当前没有在本交接中提供真实服务器和域名信息。
4. `preserve_existing_features`：对本项目审查和修复时，应保留已有业务功能。用户已授权直接进行本项目普通代码修改与安全修复，不需要逐项重复确认。
5. `api_connectivity_requirement`：用户需要可检测模型 API 是否联通的功能。
6. `implementation_handoff_preference`：本次开发需要详细、可执行的 Trae 交接文档，包含实施步骤和验收要求。
7. `personal_knowledge_goal`：用户需要供 AI 使用的个人知识库，并希望结合已知需求进行个性化。

第 4 条是项目协作背景，不能转换为应用中的管理员权限，也不授权 AI 发布私人资料、删除全部数据或向外部人员发送消息。第 3、5、7 条是需求或目标，不能据此回答“已经部署”“API 现在可用”或“所有功能已经完成”；实际状态必须查询或由实施记录证明。

中文界面和 Asia/Shanghai 是本方案结合当前交流及环境采用的默认值。PostgreSQL、Redis、索引参数、资料分类均是设计建议，不写入“用户亲口确认”的记忆。可提供空的“工作台项目”“个人偏好”“资料笔记”集合模板；学习、工作等分类由用户自行增加。

交付幂等初始化命令，例如 `python manage.py seed_personal_knowledge --owner <现有账号> --dry-run`。实际运行必须明确目标账号，不能给所有注册用户写入这套内容，也不能在数据库迁移中绑定某个账号。唯一键采用 owner、seed_key；只创建缺失条目，已编辑、停用或遗忘的条目不因重复初始化而恢复。若该账号尚无 zixxx 项目，初始化时幂等创建关联项目和集合，不借用其他账号对象。需要重新导入时由用户明确操作。交接文字是外部来源备注，不伪造本应用 Message ID。

### 16.2 首版范围与日常使用路径

首版包含五项能力：知识笔记与集合、资料正文检索、带来源的 AI 回答、个人记忆管理、当前任务的只读查询。模型不可用时，本地知识管理、检索和记忆编辑仍可操作。

资料进入知识库有四条明确路径：

1. 在知识库手写 Markdown 笔记，填写标题、集合和标签。
2. 在本人私人资料库选择 TXT、Markdown、文本 PDF 或 DOCX，点击“加入知识库”。文件仍由 library 管理，knowledge 保存来源关系和解析版本，不再重复计算一份原件存储配额。
3. 在每日记录中选择“加入知识库”，创建带日期的内容快照，保留源记录 ID 与版本。源记录后续变化时标记“来源有更新”，由所有者选择更新快照；旧快照的回答必须按历史日期表达。
4. 在 AI 消息上选择“保存为笔记”，先展示可编辑草稿；保留会话和消息来源。模型生成内容明确标为 ai_generated，不能变成“用户亲口说过”的证据。

二维码投递只完成资料接收。登录的所有者可在电脑端把收到的资料加入指定知识集合；仅持 Upload 凭证的手机页面没有知识检索、索引管理或记忆写入能力。

“今天要做什么”“某任务是否完成”通过 tasks/workspace 的只读服务查询实时数据，并附查询时间与日期范围。首版至少提供“查看今日任务”的明确入口；自然语言日期不能可靠解析时保留日期选择。不得把每天的任务状态长期写进个人偏好，或用过期对话摘要回答当前任务状态。

### 16.3 页面与对话交互

知识库页面使用集合筛选、标题搜索、条目列表和详情编辑。条目显示来源类型、更新时间、是否用于 AI、索引状态和失败后的重试操作。集合删除先提供移出条目或一并移入回收站的明确选择，不隐式删除原始资料。

“用于 AI”控制模型可使用的范围；关闭后仍允许所有者在知识库中查看和搜索自己的正文。手动入库时显示该选项，扫码投递不自动开启。解析和本地索引可在关闭 AI 使用时继续，后台作业不能改变用户设定的开关。

个人记忆页显示每条内容、事实/偏好/目标类型、全局或项目范围、来源、确认时间、有效期和状态。提供编辑、停用、恢复、忘记和导出。候选记忆独立显示，不能与已启用记忆混在一起。项目条目只有当前会话绑定该项目时才使用。

AI 输入区增加“使用知识库”“个人记忆”“当前工作台”三个独立开关。知识库开启后选择集合或明确选择全部本人集合；空集合列表按空范围处理，不能暗中解释成全库。旧会话迁移后均默认关闭，用户启用后保存在该会话设置中。新会话可以采用用户显式保存的默认偏好。

首次启用时直接说明：“相关片段会发送给当前模型服务用于回答，可随时调整范围。”范围已开启后正常问答不重复弹出确认。开关、所选集合和实际使用来源可随时查看。

回答保留现有流式体验。引用显示为可点击的来源编号，打开抽屉查看资料标题、版本、命中片段、页码或标题路径，并通过鉴权接口打开原文。页面不展示服务器物理路径或可绕过权限的媒体地址。

没有命中时展示“在当前范围内未找到相关资料”，可继续给出明确标注的一般建议。检索失败则显示检索失败，不能伪装成“没有资料”。用户已选择“只依据资料回答”时，资料不足应停止给出无依据的结论。

### 16.4 数据模型与约束

以下为建议拆分；Trae 可合并等价实现，但不能省略来源、版本、权限和生命周期约束。所有新对象均有 UUID、创建时间、更新时间；可编辑对象沿用 version 乐观锁。

- KnowledgeCollection：owner、name、description、可选 project、deleted_at。名称限制与普通文本表单一致；项目必须属于同一 owner。
- KnowledgeDocument：owner、collection、title、source_type、source_material/source_entry/source_message、manual_body、content_origin、ai_enabled、current_revision、deleted_at。来源为手写时使用正文；导入时按类型只允许对应来源字段，不能同时关联他人对象或互相矛盾的来源。首版同一 Material 只建立一条有效知识文档，换集合走移动操作。
- KnowledgeRevision：document、revision_no、source_version、source_hash、parser_version、正文或结构化提取结果、index_status、error_code、indexed_at。唯一键为 document、revision_no。index_status 至少区分 pending、processing、ready、failed、needs_ocr、stale；错误字段只存可读的脱敏信息。
- KnowledgeChunk：owner、document、revision、ordinal、text、content_hash、heading_path、page_start/page_end、char_start/char_end、token_estimate。唯一键为 revision、ordinal；owner 必须与 document 一致。PDF 页码采用文件实际页序，从 1 开始；DOCX、Markdown 使用标题与段落位置，不编造排版页码。
- KnowledgeIndexJob：owner、document、revision、pipeline_version、status、attempts、lease_until、claim_token、next_run_at、last_error。document、revision、pipeline_version 唯一；租约与领取标识用于阻止过期 worker 提交结果。
- PersonalMemory：owner、key、content、kind、scope_type、project、status、evidence_type、source_ref、confirmed_at、valid_from/valid_until、version、supersedes、deleted_at。状态至少覆盖 suggested、active、disabled、superseded、forgotten；同一 owner、key、scope 最多一条 active 版本。模型置信度不能代替用户确认。
- MemoryRevision 或等价变更记录：记录谁在何时执行了何种变更及版本关系。普通编辑可保留历史；彻底忘记时删除正文历史，仅保留不含原文的操作时间与防重复初始化标识。
- MessageCitation：关联本人的 assistant Message，保存本轮 source_id、来源类型、知识文档版本/分段或实时对象引用、定位元数据、当时的检索时间。源已撤回时返回不可用状态，不从引用接口泄露旧正文。实时任务引用标明“查询时快照”，不能伪装成当前值。

Conversation 增加知识开关、集合范围、个人记忆开关、项目、工作台读取开关和 context_epoch。新字段兼容旧会话。Message 增加本轮使用的知识/记忆依赖元数据或通过关联表保存，供撤回时识别受影响历史。前端不能指定 owner、confirmed_at 或把证据类型自行升级为 user_explicit。

来源关系的处理必须明确：删除知识文档只影响知识副本；删除或撤回源资料后依赖它的知识文档立即停止检索。每日记录和消息快照随来源删除失效。用户此前明确选择“另存为独立笔记”的副本可独立保留，保存时就应说明此行为。

### 16.5 解析、分段与持久化作业

现有 backend/agent/parsing.py 的 MAX_EXTRACTED_CHARS 为 80,000，附件解析结果会截断。知识库不能直接把 AgentAttachment.extracted_text 当作完整文档索引，也不能从拼接后的字符串猜出 PDF 页码。复用安全的底层解析能力，新增保留页、段落、标题定位的知识解析输出。

执行流程如下：

1. 鉴权并检查来源当前版本、文件类型、配额及未删除状态；提交 KnowledgeDocument、Revision 与 pending 作业到同一数据库事务。ai_enabled 独立保存，不由解析流程开启。
2. worker 原子领取到期作业，记录租约与 claim_token，事务外解析。首版默认并发 1，提供 `process_knowledge_jobs --once` 和受监督循环模式。
3. 以页、标题、段落为边界分段；过长段落再拆分。建议每段约 400 至 800 个中文字符或等量文本，重叠约 80 字符，均为可调整参数。保持代码段和表格的基本可读性，无法还原的结构在来源预览中说明。
4. 按固定 pipeline_version 写入 staging 分段，验证字符覆盖、定位和数量。不得把全部分段一次载入请求进程。
5. 提交前重新核对 owner、来源版本、删除状态和 claim_token；仍有效才原子切换到该版本的 ready 索引。过期作业丢弃输出并释放资源。索引成功不改变 ai_enabled，AI 检索始终读取它的最新值。
6. 失败记录原因与可重试状态。网络或进程故障可按退避重试；格式不支持、加密 PDF、超过限制等错误等待用户处理，不无限重试。

建议首版默认：知识解析文件最大 25 MiB、PDF 最大 200 页、提取文本最多 500,000 字符、每账号最多 10,000 个有效分段；单作业超时 120 秒、最多 3 次尝试。限值均可配置。超过限制时整次解析标记失败并提示拆分，不悄悄只索引前半篇。资料库仍可保存符合其自身上限的原文件。

另设单账号索引存储预算，计入历史版本、staging 和失败作业残留。提交分段前做事务内配额检查，重复作业不重复扣费或占用；版本替换后及时清理无保留必要的旧分段。不能只限制有效分段数而允许无限重建消耗磁盘。

对 DOCX 等压缩容器限制解压后的总大小和条目数；解析子进程设置资源与时间限制，不允许执行宏、脚本或外部引用。纯扫描 PDF 和图片显示 needs_ocr，首版不承诺识别。链接首版只保存用户输入的地址和备注，不自动抓取任意 URL。

文件被替换或知识正文修改后，旧版本立即退出当前检索，新版本显示排队或解析中；不能拿旧内容冒充已更新。第 16.2 节主动保存的每日记录快照是有日期的独立修订，源更新时保留历史日期与过时提示，用户选择同步后再切换版本。恢复回收站内容时重新验证来源版本，再决定复用索引或重建。清理命令覆盖失败 staging 数据、失效租约和删除后的分段。

### 16.6 中文检索与模型上下文

首版实现统一 SearchService：输入 owner、query、明确范围、用途和数量上限，输出可追溯的分段及命中原因。先在数据库限制 owner、有效集合、未删除和当前 ready 版本，再检索与排序；AI 用途额外要求 ai_enabled。手动搜索可显示本人的停用条目，用途由服务端调用入口确定，聊天请求不能通过参数降级限制。不能全库召回后才在应用层过滤权限。

关键词检索至少支持中文连续短语、按中文词或字的有限切分、中英混合、英文大小写归一化。标题和标题路径可加权，正文命中保留原文定位。SQLite 开发模式采用受限规模的正文条件查询与确定性排序；PostgreSQL 可采用 pg_trgm 索引辅助。该扩展提供三元组相似度及 LIKE/ILIKE 索引能力，但中文短查询的质量和性能仍需用本项目样本验证。[PostgreSQL pg_trgm 文档](https://www.postgresql.org/docs/current/pgtrgm.html)

限制查询长度、切分数量和执行时间，禁止由模型拼接 SQL、正则或无界搜索条件。首版建议最多召回 6 个分段、每文档最多 3 段；排序后去重，邻近片段可合并。查询无证据时返回空结果，不能为了凑数返回无关片段。若采用候选截断，结果需标注搜索范围受限，并有可调整的配置和规模测试。

拼装模型请求时分别提供当前用户问题、有效个人记忆、实时工作台结果、资料片段和必要聊天历史。个人记忆只能作为有范围的背景数据，不能写成可扩大工具权限的系统指令。资料区应带明确边界与来源 ID，模型无权执行其中的操作要求。

现有 backend/agent/llm.py 使用 MAX_CONTEXT_CHARS=110,000 与 MAX_HISTORY_MESSAGES=40；字符数不等于模型 token 上限。新增模型上下文配置、输出预留和估算器。建议知识片段默认预算 4,000 tokens、记忆 800 tokens，实际预算不得超过模型剩余额度。无法准确分词时使用明确标注的保守估算和较低总上限；先压缩历史与召回量，不能直接把全文塞给模型。

为本轮合法来源生成 S1、S2 等 ID。要求回答在相关结论后引用这些 ID，后端只允许绑定本轮真实来源。实时任务和个人记忆同样有各自来源类型；一般建议不冒充资料结论。无效 ID 在流式展示时保持普通文本，最终标记无法验证，不生成伪造文件链接。引用存在只证明来源可追溯，不能自动声称模型的每个结论均已得到证实；评估集需检查结论是否受原文支持。

使用已配置的聊天模型完成回答。现有 UserApiConfig 是聊天配置，不能假定同一服务支持 embedding。向量增强如以后采用，应单独配置提供商、模型、维度、密钥和发送范围；模型切换建立新索引版本，不混用不同向量空间。未配置 embedding 时保留关键词搜索，不阻塞本轮验收。

### 16.7 AI 写入、修改与忘记

需要区分用户明确要求保存与 AI 自行推测：

- 用户在记忆表单点保存，或通过明确的“记住：内容”入口提交时，可直接保存至所选范围，成功后展示“已记住”、条目入口与撤销按钮，不反复确认同一请求。
- 对话中自行提炼出的偏好、任务结论或人物信息只生成 suggested 草稿；用户采纳后才成为 active。一般回答、资料文字、AI 自述不能自动证明用户的长期偏好。
- “把这段整理成笔记”生成可编辑正文并按用户已选择的保存入口提交；未明确目标集合时使用可见的默认收件集合。涉及替换已有内容时展示差异，依 version 检查冲突。
- API Key、口令、账号 Token 和二维码凭证不作为知识或记忆保存，也不通过模型提炼进入索引。遇到明确凭证字段时拒绝保存并指向模型设置；普通文字中的疑似凭证提醒用户处理，不能声称自动检测可识别全部秘密。

首版不提供任意自主写库工具。由用户操作或明确命令入口生成本轮 write_intent，绑定 owner、会话、允许的操作、目标范围、过期时间及幂等键。模型仅生成受 schema 约束的条目建议，服务端校验 write_intent 与字段后才能写入。没有该意图的模型输出只能成为候选，不得仅凭模型判断“用户授权”执行写入。写入接口不接受任意文件路径、SQL 或跨账号 ID。

不要求所有模型都原生支持工具调用。优先使用现有聊天协议产生可验证的 JSON 草稿或前端保存动作；格式解析失败则保留草稿和错误提示，不执行部分写入。界面只有在数据库提交成功后才能显示“已记住”或“已保存”，流式文本中的成功表述不作为持久化凭据。

相同 key 与 scope 的新明确指示更新当前版本，旧版本标记 superseded；不同项目的偏好可并存。冲突且无法判断是否替代时保留候选并让用户选择，不能凭模型置信度覆盖。目标和有期限的事实到期后不再作为当前背景，历史查询时明确其时间范围。

回答时当前用户的明确要求优先于存储偏好，同一事项的项目偏好优先于全局默认，当前任务数据优先于历史总结。一次临时要求不自动覆盖长期偏好，只有明确要求持续记住时才更新。

停用、忘记、来源撤回或范围缩小后，立即增加相应 owner/context_epoch，失效检索与上下文缓存。模型请求发送前重验版本；处理中发生撤回时取消可取消的调用，停止后续流式片段，并在最终保存或执行写入前重验。已输出的片段标记为中断且不再注入后续上下文，不能声称撤回了用户已经看到的文字。

仅删除数据库记忆行不够：已注入的旧消息、引用片段和压缩摘要也可能带回该信息。首版采用可验证的保守处理：对受影响会话设置新的模型上下文起点，旧消息仍可在界面查看，但后续模型请求从新起点重新构建；提示“已更新记忆范围，后续回答使用新的上下文”。清除关联摘要和检索缓存。当前聊天尚未启用记忆时不因无关记忆修改丢失上下文。

“忘记”从未来上下文移除并清除该记忆正文及其修订副本；源对话、原始资料和历史回答由各自删除入口管理，界面明确保留范围。应用无法撤回已经发给服务商的请求，也不能宣称删除了服务商侧留存。备份恢复后应先应用独立保存、不含正文的撤回记录，再开放检索，避免旧备份复活被忘记的条目；备份正文按保留期淘汰。

### 16.8 API 合同与流式兼容

所有知识接口位于 /api/knowledge/，使用正常账号认证及新工作台权限；继承 owner 隔离，不继承中转站管理员读取全部资料的规则。最小接口集如下：

- GET/POST /collections/；GET/PATCH/DELETE /collections/:id/。
- GET/POST /documents/；GET/PATCH/DELETE /documents/:id/，DELETE 默认为移入回收站。
- POST /documents/import/，指定一个本人 material_id、entry_id 或 message_id、来源版本和集合；重复请求使用幂等键返回同一结果。
- POST /documents/:id/reindex/、/restore/；永久删除使用独立 /purge/ 操作并明确其内容范围。
- GET /documents/:id/status/；GET /documents/:id/source/ 返回经过权限检查的版本及定位数据。
- POST /search/，接收 query、collection_ids 或显式 scope=all、limit；返回 matches、source_refs、index_warnings 和实际范围。无命中返回 200 加空数组，服务失败用相应错误状态。
- GET/POST /memories/；GET/PATCH /memories/:id/；POST /memories/:id/accept/、/disable/、/forget/。候选接纳、编辑、停用均检查 expected_version，旧版本返回 409。
- POST /write-intents/ 创建由用户明确触发的有限写入意图；应用草稿的接口必须校验该意图、对象范围和幂等键。
- GET /citations/:id/ 重新检查消息与来源访问权，返回可用、源已更新或源不可用状态；未知或他人来源不泄露标题和摘要。
- GET /export/ 导出本人的知识笔记、记忆及来源清单；默认不包含密钥、他人数据和已忘记正文。大规模导出通过持久化作业完成，下载继续鉴权。

知识列表分页，查询和排序字段采用白名单；大文本详情单独获取。统一处理未登录、无权访问、无效来源、409 版本冲突、413 大小超限、429 配额/限速及 503 服务不可用。前端不得把错误当作空列表后覆盖已有内容。

扩展现有 POST /api/agent/chat/ 的请求字段，例如 knowledge={enabled, scope, collection_ids, use_personal_memory, project_id, use_workspace, strict_sources}。所有 ID 服务端重新检查归属；省略新字段时保留旧聊天行为。将实际范围与本轮来源元数据写入会话记录，重新打开会话时引用仍可用。

保留现有 meta、delta、done、error SSE 事件。增加 retrieval 状态与 sources 元数据事件，或向 meta/done 增加可选字段；选定一种方案并写入前后端类型定义。检索结束且权限复验后才发布可点击来源，done 中保存最终引用集合。旧客户端遇到未知事件应忽略，不能破坏原有文本输出与附件逻辑。

### 16.9 与当前代码的接入位置

- backend/knowledge/：models.py、serializers.py、views.py、permissions.py；服务拆分为 ingestion.py、search.py、context.py、memories.py、jobs.py，具体命名可调整。
- backend/knowledge/management/commands/：提供作业执行、失效数据清理、索引重建、个人条目初始化命令，危险清理支持 dry-run。
- backend/agent/models.py 与 serializers.py：增加会话范围、引用和上下文依赖；迁移不丢失 Conversation、Message 和 AgentAttachment 历史。
- backend/agent/views.py 的聊天入口：在已有会话/附件归属检查后检索，记录来源，传给已有模型适配器；最终提交前复验 context_epoch。
- backend/agent/llm.py 的 build_rich_messages 及适配器入口：引入受预算约束的背景结构和上下文起点，三个现有模型协议均应通过合同测试，不只修改其中一个协议。
- backend/agent/parsing.py：抽出可复用解析部分，旧附件行为继续回归；新知识解析独立保留完整定位与超限状态。
- frontend/src/views/AgentChatView.vue：加入范围选择、检索状态、引用抽屉、保存笔记/记忆入口与撤回反馈；保留 Markdown、公式、图片附件、流式取消及错误重试。
- 新增 KnowledgeView.vue、KnowledgeMemoriesView.vue、knowledge.ts、知识库组件和路由；服务端权限先于前端菜单隐藏。

### 16.10 权限、隐私与运维约束

检索、引用、文件读取、作业提交、导出与记忆写入都从当前账号确定 owner。缓存键至少包含 owner、范围、查询和有效数据版本，账号切换清理前端状态。统计数量和错误信息同样不能暴露他人的集合是否存在。

资料正文和检索片段是不可信数据。资料中的指令不得修改系统配置、扩大检索范围或触发写入；工具能力只由服务端允许的操作与用户意图决定。文档内容带来的间接提示注入与检索污染是明确的风险类型，应以权限、结构化输入和针对性测试共同防护，不能只加一句“不要被注入”。[OWASP 提示注入防护说明](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)

继续使用现有安全 Markdown 渲染。对模型和资料中的远程图片默认不自动加载，外链由用户明确打开，避免借引用或图片请求外传私密片段。知识内容不得进入公开中转站、未经授权的服务端 URL 抓取、应用埋点或异常堆栈。

正常日志只记录作业 ID、owner 的内部标识、状态码、耗时、片段数量和调用量，不记录正文、完整提问、密钥或上传 token。调试采样使用测试数据。模型调用沿用现有密钥加密和出站限制；资料来源中写出的 API 地址不能改变服务商配置。

监控待处理作业数、最长等待时间、解析失败率、过期租约、检索耗时、模型超时和每账号用量。知识问答失败时，本地资料查找、编辑、任务和扫码仍可使用。提供重试与重建入口，不依赖运维手工修改数据库状态。

### 16.11 演示与评估交付

Trae 使用虚构测试资料建立至少 20 个固定问题，覆盖中文短词、中英术语、跨文档对比、无答案、冲突版本、过期偏好、今日任务变化、恶意文档和跨账号访问。每题保存预期来源或“应拒绝/应说明不足”，不把真实私人资料加入代码仓库。

确定性检索、权限、幂等、撤回与生命周期使用自动化测试；模型回答质量用可复现的固定样本记录服务商、模型和日期，检查引用是否支持结论，避免把一次生成成功当作准确率保证。至少记录来源命中率、无依据回答数、无效引用数、越权结果数；后两项中越权结果必须为零，无效引用不得被渲染为可信出处。

最终演示顺序：初始化本项目已确认条目；新建一篇笔记；扫码上传文本 PDF 并由所有者加入知识库；向 AI 提问并打开页码引用；修改原文重新索引；保存一条明确个人偏好；在新会话验证生效；忘记偏好并验证当前会话不再注入；完成一项任务后重查今日清单；切换账号验证隔离；重启服务验证作业与知识持久化。

## 17. 可直接发送给 Trae 的任务指令

请阅读项目根目录 TRAE_HANDOFF.md，并按第 14 节完成 zixxx 个人工作台的阶段 A 至 G，第 16 节个人知识库与 AI 记忆属于本轮核心范围。

先核对现有 Vue 3 + Django 项目的入口、权限、数据库迁移和文件存储，再实现今日待办、任务与项目管理、每日记录、私人资料库、手机扫码上传、个人知识库和 AI 记忆。用户已授权直接进行普通开发和安全修复。可逆实现选择采用文档默认方案，并记录差异。

重点完成真实数据持久化、账号隔离、上传凭证范围、失败重试、旧数据兼容、日期语义和服务器部署。按既有项目结构渐进实现，每个阶段交付可运行代码与验证结果。

扫码上传采用限时且仅可投递的凭证，电脑看到上传结果。上传内容默认为私人资料，所有下载继续鉴权。已有 AI 流式输出、模型连接测试、双人聊天和公开中转站均需回归。

知识库先完成笔记、资料分段、中文检索、来源引用与个人记忆管理，再接入 AI 对话；首版不依赖向量服务。用户选定范围后正常问答自动检索，明确“记住”可按有限写入意图保存，推测出的记忆只进入候选。今日任务读取实时数据。实现资料更新、删除、范围缩小与忘记后的缓存及历史上下文失效，防止过期信息重新注入。

个性化初始化只使用第 16.1 节有依据的本项目条目，不编造身份、学习计划或关系，不把项目修改授权变成 AI 的永久系统权限。初始化命令必须指定目标账号，重复执行不覆盖用户修改或恢复已忘记条目。提供持久化索引 worker、重试与重建命令，以及第 13.5 节的完整验证。

最终交付代码、迁移、必要测试、Docker Compose、Nginx 配置、环境示例、备份恢复脚本、索引 worker 与重建命令、知识库评估样本、启动与升级说明，以及第 13 节验收结果。真实服务器信息或新模型 Key 缺失时，完成其余已授权工作，准确列明待提供内容与未验证项。
