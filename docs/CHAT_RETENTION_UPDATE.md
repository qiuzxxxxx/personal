# 聊天记录保留与 AI 保留策略更新

## 更新内容

- 站内聊天改为持久留言：文字与文件消息保存于服务器数据库，对方离线时上线后仍可阅读。
- 移除阅后即焚、自动到期删除与端到端加密相关功能；聊天消息与文件不再按时间自动销毁。
- 双向文件互传：双方均可发送文件，文件通过鉴权接口下载。
- 删除仅从自己的列表中隐藏（`deleted_for_sender` / `deleted_for_recipient`），服务器记录与物理文件保留，用于内容安全与审计。
- 管理员账号的 AI 聊天记录永久保留；成员和访客账号的 AI 消息、无引用附件仅保留 24 小时。

## 数据库升级

上传新版 `backend` 后执行：

```bash
cd /www/wwwroot/aiwork/backend
set -a
. /etc/aiwork/aiwork.env
set +a
/www/wwwroot/aiwork/.venv/bin/python manage.py migrate --noinput
systemctl restart aiwork
```

本次迁移：`chat/0005_remove_chatmessage_burn_fields.py`，删除 `burn_after_read_seconds`、`read_at`、`expires_at` 三个字段。已有聊天消息会保留，不会因迁移被删除。

## 自动清理

聊天消息不再自动清理。`cleanup_retention_data` 仅清理非管理员账号超过 24 小时的 AI 聊天记录与无引用附件；生产环境可继续沿用原定时任务：

```bash
cat > /etc/cron.d/aiwork-retention <<'EOF'
* * * * * root /usr/bin/flock -n /tmp/aiwork-retention.lock /bin/bash -lc 'set -a; . /etc/aiwork/aiwork.env; set +a; cd /www/wwwroot/aiwork/backend && /www/wwwroot/aiwork/.venv/bin/python manage.py cleanup_retention_data >> /www/wwwroot/aiwork/backend/var/retention.log 2>&1'
EOF

chmod 644 /etc/cron.d/aiwork-retention
```

手工验证：

```bash
cd /www/wwwroot/aiwork/backend
set -a
. /etc/aiwork/aiwork.env
set +a
/www/wwwroot/aiwork/.venv/bin/python manage.py cleanup_retention_data
tail -n 50 /www/wwwroot/aiwork/backend/var/retention.log
```

## 前端发布

重新构建并覆盖服务器 `front/dist`：

```bash
cd frontend
npm ci
npm run build
```

发布后强制刷新浏览器缓存。旧版前端仍能收发消息，但会显示已下线的阅后即焚选项；请确保前后端同时升级。

## 接口变化

- `POST /api/chat/messages/`：仅接收 `content`，不再接受 `burn_after_read_seconds`。
- `POST /api/chat/files/`：仅接收文件与可选 `content`，不再接受 `burn_after_read_seconds`。
- `DELETE /api/chat/messages/<uuid>/`：仅支持 `scope=self`，从自己的列表隐藏；`scope=everyone` 返回 400。
- `DELETE /api/chat/messages/clear/`：仅支持 `scope=self`，清空自己的列表。
- 聊天消息响应移除 `burn_after_read_seconds`、`read_at`、`expires_at`。
- `python manage.py cleanup_retention_data`：仅清理 AI 数据，不再清理聊天消息。
