# zixxx 安全与代码审查报告

以下为 2026-11-13 的历史审查记录。当前版本的升级步骤与安全配置见 [README](README.md#九安全说明)。

审查日期：2026-11-13 · 审查范围：`backend/`（Django 5 + Channels）、`frontend/`（Vue 3 + TS）、部署配置与测试数据残留
方法：89 项接口自动化断言 + WebSocket 用例 + `vue-tsc` 静态检查 + 生产构建 + 全路由浏览器扫描（0 控制台错误）+ 关键权限代码人工复核 + 数据清点

---

## 一、通过项

1. **权限矩阵**（89/89 断言通过）
   - 中转站：匿名仅公开件；登录非最高管理员 = 公开 + 自己投递；最高管理员（qzx / zx）全量；私密件下载限「上传者 + 最高管理员」；PATCH/DELETE 仅最高管理员。
   - 账号三级：最高管理员（qzx / zx，rank 2）＞ 管理员（sqx，rank 1）＞ 普通（guest，rank 0）。改密需 `操作者 rank ≥ 目标 rank` 且非本人；日志越级查询 403；重置密码即吊销目标旧 Token。
   - AI 对话：未登录 401、guest 403（`CanUseAgent`）；密聊：仅 zx / sqx，WebSocket 握手校验 Token，非聊天账号以 4401 拒连。
2. **密钥安全**：模型 API Key 以 Fernet（AES-128-CBC + HMAC-SHA256）密文入库；`GET /api/agent/config/` 仅返回 `has_key` 与掩码提示且 `Cache-Control: no-store`；对话请求只带 `use_saved`，明文不出后端进程；断言验证「响应无明文 / 库中为密文 / 可解密」。
3. **文件安全**：`/media` 无静态暴露，全部经鉴权下载接口；响应带 `X-Content-Type-Options: nosniff` 与 `Content-Security-Policy: sandbox`；非安全图片扩展名强制附件下载；上传有扩展名黑名单（可执行/脚本）、体积上限（中转 500 MB / 聊天 80 MB / AI 附件 25 MB）、文件名 `Path.name` 净化与 NUL 剥离；匿名署名禁止冒用预置账号。
4. **渲染安全**：markdown-it `html:false`、KaTeX `trust:false`、外链强制 `rel="noopener noreferrer"`；`v-html` 仅消费经净化的 markdown 输出；预览 SVG 被排除（仅下载）。
5. **代码卫生**：项目源码（不含 node_modules / venv）无 `console.log` / `debugger` / `TODO` / `FIXME` / 调试 `print` 残留；无硬编码密钥；类型检查零错误。
6. **审计日志**：登录成功/失败、退出、改密（含操作人）、中转站上传/修改/删除、模型配置保存均入库，含 IP 与时间戳；记录失败不影响业务；日志读取按层级授权。

## 二、残留风险与上线清单（按优先级）

1. **DEBUG 开关**：`settings.DEBUG` 默认 `1` 且 `CORS_ALLOW_ALL_ORIGINS = DEBUG`。上线必须 `DJANGO_DEBUG=0` 并显式设置 `DJANGO_ALLOWED_HOSTS`、`DJANGO_CORS_ORIGINS`、`DJANGO_CSRF_TRUSTED_ORIGINS`，反向代理启用 HTTPS。
2. **WebSocket Token 位于 query string**（`/ws/chat/?token=…`）：可能进入代理/访问日志。上线请在代理层屏蔽 query 记日志，或改为首帧/header 传 Token。
3. **SSRF 面**：AI `base_url` 由登录账号自配，后端会向该地址发起请求（BYO-endpoint 设计）。个人自托管可接受；若开放给不可信用户，需做出网白名单/禁内网段。
4. **声明同意为前端约束**：免密上传接口按设计保持开放，同意勾选仅前端拦截；如需法律级强制需后端校验同意记录。
5. **主密钥备份**：`backend/.master.key`（600 权限、已 git-ignore）丢失将导致已存 Key 不可解密；生产建议改用环境变量 `NEXUS_MASTER_KEY` 并纳入密钥管理。
6. **静态数据保护**：聊天与对话内容明文存于 SQLite（《使用声明》已告知）；建议 `db.sqlite3` 与 `media/` 权限 600、定期备份，必要时磁盘级加密。
7. **预置弱口令**：`123456` 仅用于初始化，上线立即修改（`init_users` 不覆盖已改密码）。
8. **进程模型**：InMemory Channel Layer 仅单进程；多进程/多机部署换 Redis Channel Layer。

## 三、测试数据清理记录（本次执行）

| 类别 | 清理量 | 清理后 |
| --- | --- | --- |
| 密聊消息（seed 演示 + smoke + ws smoke） | 17 条 + 关联磁盘文件 | 0 |
| AI 会话（smoke / UI 测试 / seed 演示） | 6 个（级联消息） | 0 |
| AI 附件记录 + 磁盘文件 | 8 条 + 12 文件 | 0 |
| 审计日志（自检噪声） | 100 + 1 条 | 0 |
| 中转站测试/演示文件 | 历轮自删 + 孤儿清扫 4 文件 | 仅存用户真实文件 `ai.mp4`、`b_ec2bc…jpg` |
| 一次性账号 `smoke_agent` | 每轮自毁 | 不存在 |
| 临时脚本（`.tmp/*`、`mock_llm_check.py`、`debug-*.cjs` 等） | 已删除 | 保留回归脚本于 `.tools/`（git-ignore） |

账号表保持 4 个预置账号：`qzx` / `zx` / `sqx` / `guest`。
