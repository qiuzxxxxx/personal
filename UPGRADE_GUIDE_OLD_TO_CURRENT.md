# AIWork 旧版升级到当前新版

本文适用于已经运行在宝塔面板中的旧版 AIWork，默认生产目录如下：

```text
/www/wwwroot/aiwork/
├── backend/                 Django 源码、media、staticfiles、var
├── front/dist/              Vue 生产构建
└── .venv/                   Python 虚拟环境
/etc/aiwork/aiwork.env       生产环境变量与密钥
```

目标域名示例为 `https://aiwork.qzx1028.space`，后端由 `aiwork.service` 启动 Daphne，Nginx 将 `/api/`、`/admin/`、`/ws/` 反向代理到 `127.0.0.1:8000`。

## 1. 本次新版内容

- 登录页公告：公开读取，只有最高管理员可以发布、修改和撤下。
- 站内聊天持久留言与双向文件互传；删除仅从自己的列表隐藏，服务器记录留存。
- 管理员 AI 对话永久保存，其他账号 AI 消息和无引用附件保存 24 小时。
- 新增统一清理命令 `cleanup_retention_data`。
- 修复私人资料库预览、下载地址被重复拼接 `/api` 的问题。
- 保留已有的账号管理、聊天权限、文件公告、文件可见时效、1 GiB 中转与扫码上传等功能。

本次关键迁移：

```text
chat/0003_chatmessage_retention.py
transfer/0004_transferannouncement_login_fields.py
```

`migrate` 会自动按依赖顺序执行旧版尚未执行的其他迁移，不要手工修改 `django_migrations` 表。

## 2. 升级前必须备份

先确认当前服务正常：

```bash
systemctl status aiwork --no-pager
curl -fsS https://aiwork.qzx1028.space/api/health/ready/
```

创建备份目录并加载生产变量：

```bash
BACKUP_DIR=/www/backup/aiwork-$(date +%Y%m%d-%H%M%S)
mkdir -p "$BACKUP_DIR"
set -a
. /etc/aiwork/aiwork.env
set +a
```

备份 PostgreSQL、媒体文件、环境配置和当前前端：

```bash
PGPASSWORD="$POSTGRES_PASSWORD" /www/server/pgsql/bin/pg_dump \
  -h "${POSTGRES_HOST:-127.0.0.1}" \
  -p "${POSTGRES_PORT:-5432}" \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  -Fc -f "$BACKUP_DIR/aiwork.dump"

tar -C /www/wwwroot/aiwork/backend -czf "$BACKUP_DIR/media.tar.gz" media
cp -a /etc/aiwork/aiwork.env "$BACKUP_DIR/aiwork.env"
cp -a /www/wwwroot/aiwork/front/dist "$BACKUP_DIR/frontend-dist"
cp -a /etc/systemd/system/aiwork.service "$BACKUP_DIR/aiwork.service"
```

检查备份不是空文件：

```bash
ls -lh "$BACKUP_DIR"
```

## 3. 本地准备上传文件

在 Windows 项目目录执行：

```powershell
cd D:\ai\frontend
npm ci
npm run build
```

需要上传：

```text
D:\ai\backend\                 后端源码
D:\ai\frontend\dist\          新前端构建
```

不要上传或覆盖：

```text
backend/media/
backend/var/
backend/db.sqlite3
/www/wwwroot/aiwork/.venv/
/etc/aiwork/aiwork.env
```

也不需要上传 `frontend/node_modules`、本地虚拟环境、缓存目录或旧 ZIP。

## 4. 替换服务器代码

通过宝塔文件管理上传新版后端源码和 `frontend/dist`。推荐先上传到临时目录，再切换：

```bash
systemctl stop aiwork

mkdir -p /www/wwwroot/aiwork/releases/current-backend
mkdir -p /www/wwwroot/aiwork/releases/current-frontend
```

将后端源码解压到 `releases/current-backend`，前端构建解压到 `releases/current-frontend`。确认内容正确后，保留生产数据并同步源码：

```bash
rsync -a --delete \
  --exclude media/ \
  --exclude var/ \
  --exclude db.sqlite3 \
  /www/wwwroot/aiwork/releases/current-backend/ \
  /www/wwwroot/aiwork/backend/

rsync -a --delete \
  /www/wwwroot/aiwork/releases/current-frontend/ \
  /www/wwwroot/aiwork/front/dist/
```

执行 `rsync --delete` 前必须确认两个源目录分别确实包含 `manage.py` 和 `index.html`，不要对空目录执行。

## 5. 安装依赖并迁移

```bash
cd /www/wwwroot/aiwork/backend
set -a
. /etc/aiwork/aiwork.env
set +a

/www/wwwroot/aiwork/.venv/bin/pip install -r requirements.txt
/www/wwwroot/aiwork/.venv/bin/python manage.py check --deploy
/www/wwwroot/aiwork/.venv/bin/python manage.py migrate --noinput
/www/wwwroot/aiwork/.venv/bin/python manage.py collectstatic --noinput
```

不要再次运行会覆盖业务数据的初始化脚本。`init_users` 只在预置账号缺失或明确需要初始化时执行；它不会读取现有密码。

## 6. 配置自动清理

仅 24 小时 AI 保留策略会在接口访问时惰性清理；聊天消息不再自动删除。同时建议每分钟运行统一清理命令：

```bash
mkdir -p /www/wwwroot/aiwork/backend/var

cat > /etc/cron.d/aiwork-retention <<'EOF'
* * * * * root /usr/bin/flock -n /tmp/aiwork-retention.lock /bin/bash -lc 'set -a; . /etc/aiwork/aiwork.env; set +a; cd /www/wwwroot/aiwork/backend && /www/wwwroot/aiwork/.venv/bin/python manage.py cleanup_retention_data >> /www/wwwroot/aiwork/backend/var/retention.log 2>&1'
EOF

chmod 644 /etc/cron.d/aiwork-retention
```

手工执行一次：

```bash
/bin/bash -lc 'set -a; . /etc/aiwork/aiwork.env; set +a; cd /www/wwwroot/aiwork/backend && /www/wwwroot/aiwork/.venv/bin/python manage.py cleanup_retention_data'
```

## 7. 启动与健康检查

```bash
chown -R www:www /www/wwwroot/aiwork/backend/media
chown -R www:www /www/wwwroot/aiwork/backend/var
systemctl daemon-reload
systemctl restart aiwork
systemctl status aiwork --no-pager -l
```

检查本机与公网：

```bash
curl -i -H 'Host: aiwork.qzx1028.space' -H 'X-Forwarded-Proto: https' \
  http://127.0.0.1:8000/api/health/ready/

curl -i https://aiwork.qzx1028.space/api/health/live/
curl -i https://aiwork.qzx1028.space/api/health/ready/
curl -i https://aiwork.qzx1028.space/api/transfer/login-announcement/
```

预期健康检查返回 `200`；未发布公告时登录公告接口返回 `200` 且 `content` 为空字符串。

## 8. 功能验收

使用最高管理员登录后逐项确认：

1. 文件中转站顶部出现“登录页公告”按钮。
2. 发布公告后退出登录，登录页能看到公告；留空保存可以撤下。
3. 站内聊天可发送文字留言与文件，双方都能互传；删除只从自己的列表隐藏。
4. 最高管理员删除消息时同样只影响自己的列表，服务器记录保留。
5. 私人资料库图片预览、文件下载正常。
6. 手机扫码上传使用公网 HTTPS 域名。
7. AI 对话、WebSocket 聊天、文件中转上传下载均正常。

浏览器仍显示旧界面时，先按 `Ctrl + F5`；若仍无效，确认服务器 `front/dist/index.html` 引用的是本次构建产生的新哈希文件。

## 9. 常见故障

查看后端日志：

```bash
journalctl -u aiwork -n 150 --no-pager
```

查看 Nginx 日志：

```bash
tail -n 100 /www/wwwlogs/aiwork.qzx1028.space.log
tail -n 100 /www/wwwlogs/aiwork.qzx1028.space.error.log
```

- `502`：Daphne 没启动或端口 8000 未监听。
- `400 Bad Request`：检查 `DJANGO_ALLOWED_HOSTS` 和反向代理 Host 请求头。
- 新接口 `404`：后端源码未覆盖完整，或 Daphne 尚未重启。
- 页面仍是旧版：前端 `dist` 未覆盖或浏览器缓存仍在使用旧哈希资源。
- 文件下载 `404`：检查 `MEDIA_ROOT`、物理文件和 `www` 用户读取权限。

## 10. 回滚

功能异常时先停止服务：

```bash
systemctl stop aiwork
```

恢复升级前的后端源码和前端目录。若新版迁移已经写入数据库且必须彻底回滚，应在确认备份路径后恢复 PostgreSQL；恢复会覆盖升级后的新增数据：

```bash
set -a
. /etc/aiwork/aiwork.env
set +a

PGPASSWORD="$POSTGRES_PASSWORD" /www/server/pgsql/bin/pg_restore \
  -h "${POSTGRES_HOST:-127.0.0.1}" \
  -p "${POSTGRES_PORT:-5432}" \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --clean --if-exists /你的备份目录/aiwork.dump
```

最后重新启动并检查：

```bash
systemctl restart aiwork
curl -fsS https://aiwork.qzx1028.space/api/health/ready/
```

不要在没有数据库备份的情况下执行 `flush`、删除迁移记录或手工删除生产表。
