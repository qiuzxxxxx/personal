# 上线前安全审查

审查日期：2026-11-15  
范围：Django / DRF / Channels 后端、Vue 前端、依赖清单、当前生产设置与仓库部署材料。  
结论：代码层已修复本轮发现的高风险问题；**当前仓库还不具备可直接面向公网发布的部署交付物，完成文末阻断项前不要公开上线。**

## 本轮修复

1. **私密文件权限收紧**：私密中转文件的列表元数据与下载现在仅最高管理员可访问；上传者本人不再有例外。对应 [backend/transfer/views.py](backend/transfer/views.py)。
2. **修正匿名额度耗尽路径**：拒绝可执行后缀的检查现在早于匿名上传额度预留，非法文件不会消耗访客额度。对应 [backend/transfer/views.py](backend/transfer/views.py)。
3. **禁止向公网模型接口明文发送凭据**：远程 HTTP Base URL 被拒绝；loopback HTTP 与显式配置的内网 origin 仍可用。同步修正了 `.env.example` 中该变量的说明。对应 [backend/agent/endpoints.py](backend/agent/endpoints.py) 与 [.env.example](.env.example)。
4. **生产设置失败即停止**：生产环境必须提供至少 50 字符的 Django 密钥、明确的非通配 Host、PostgreSQL 与密码，以及可持久化的模型密钥；`DJANGO_DEBUG=1` 和 SQLite 会阻止启动。默认 HSTS 不再替所有子域启用 include/preload。对应 [backend/config/settings.py](backend/config/settings.py)。
5. **更新文件大小文档**：聊天、中转站和扫码上传的文件限制按当前代码更正为每文件最多 1 GiB；AI 附件仍是 25 MiB。对应 [README.md](README.md)。

## 仍需上线前完成

### 阻断公网发布

- **部署入口缺失**：仓库没有当前可用的 Nginx / systemd / 容器编排配置，README 也说明需自行编写。现在无法审查 TLS 终止、静态资源安全响应头、WebSocket 转发、请求体上限或 `/media/` 是否被错误公开。应先补齐部署配置，并确保物理文件目录不映射到公开 URL。
- **密钥尚未部署**：在服务器安全地生成并注入独立的 `DJANGO_SECRET_KEY`、`NEXUS_MASTER_KEY`、PostgreSQL 密码及三个预置账号初始密码；不要复用示例值。生产的 `.master.key` 若代替环境变量，必须放在持久化、仅服务账号可读的卷中并纳入离线备份。
- **旧模型 Key 必须轮换**：你先前把 DeepSeek Key 发在对话里。当前源码扫描未找到明文 `sk-…` Key，但已发出的 Key 应在服务商后台吊销并新建，再只通过服务端环境变量注入；不要重新写入源码、截图、日志或前端配置。
- **HTTPS 与代理边界**：公网只能开放 HTTPS 反向代理；Daphne、PostgreSQL、Redis 应绑定内网/回环地址并由防火墙隔离。代理必须覆盖而非透传用户提供的 `X-Forwarded-Proto`、`X-Forwarded-For`、`Host`，否则生产信任代理头会失效或被伪造。`.env.example` 的 `NEXUS_TRUSTED_PROXY_HOPS=1` 只适用于确实只有一层可信代理的拓扑。
- **反向代理必须支持 1 GiB 流式上传**：将请求体限制、读写超时、临时磁盘空间和并发连接数设置到明确值；生产构建不能使用 Vite 开发服务器。文件只能经应用下载 API 返回（公开文件允许匿名下载，私密资料必须授权），禁止 Nginx 对 `backend/media/` 配置静态别名。
- **备份与恢复没有成套交付**：配置 PostgreSQL、媒体文件和主密钥的加密、异地备份及保留周期，并在上线前实际完成一次隔离环境恢复。数据库与密文备份必须与 `NEXUS_MASTER_KEY` 一起恢复。

### 上线后风险控制

- **Redis 是多进程部署的前置条件**：生产未配置 Redis 时，限速和 Channels 广播只在单个进程有效。多 Daphne worker / 多实例部署前配置 Redis；部署健康检查和告警需覆盖 DB、Redis、磁盘余量、上传失败率与 worker 积压。
- **存储配额是软防线**：匿名中转站按客户端地址限流，但账号上传、二维码会话反复创建及多 IP 上传仍可能持续增长磁盘。增加全局容量告警、保留/清理策略和反向代理并发限制；`visible_until` 只控制可见与下载失效，不代表物理删除。
- **静态站点安全响应头尚未验证**：Django 为 API 和文件下载设置了部分安全头，但生产前端由未提供的 Web 服务器配置提供。部署时需为 HTML 设置严格的 Content-Security-Policy、`X-Content-Type-Options: nosniff`、`Referrer-Policy` 和防点击劫持策略。登录 Token 当前保存在 `localStorage`；Markdown 禁止原始 HTML，外链使用 `noopener noreferrer`，但任何前端 XSS 仍可读取 Token。
- **客户端地址限流依赖代理重写头部**：应确保唯一信任边界由反向代理控制。若代理不规范化转发头，攻击者可能伪造地址来绕过登录/匿名上传限速。

## 审查结果与边界

- 逐项检查了登录与单设备 Token 轮换、账号权限、私密文件下载、WebSocket 对端校验、API Key 加密与模型目标地址校验、上传与解析限制、Markdown 输出处理、数据库/部署配置。
- 当前依赖版本中，Django `5.2.19` 包含 2026-11-03 发布的安全修复；Vite `6.4.6` 已包含截至本审查日披露的一项高危 Vite 开发服务器问题的修复；Axios `1.21.1` 与锁文件中的 `follow-redirects 1.16.3` 高于其修复下限。前端 `npm audit` 因沙箱无法连接 npm registry（EACCES）未能完成，所以不能据此宣称全部传递依赖无漏洞。
- 本次未对公网服务器、TLS 配置或真实部署环境做动态渗透测试；当前目录也没有可验证的生产目标。Django `check --deploy`、前端构建和接入测试应在最终服务器配置落地后再次执行。
- 当前源码和已跟踪文件中未检出 `sk-…` 格式的明文 Key；本地 `.master.key`、数据库文件被 `.gitignore` 排除。发布前仍应独立检查 Git 历史、构建工件、备份包和服务器日志，忽略规则本身不会清除已提交过的秘密。
