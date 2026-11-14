# zixxx 部署说明

本文面向把工作台部署到**单台 4 核 4G 内存服务器**的运维者。所有内存上限按 [TRAE_HANDOFF.md](TRAE_HANDOFF.md) 第 12.7 节设置。

## 1. 前置条件

- 一台 4 核 4G 的 Linux 服务器（Debian 12 / Ubuntu 24.04 均可）。
- 已解析到该服务器的域名，例如 `workbench.example.com`。
- 已安装 Docker 与 Docker Compose 插件：`docker compose version` 能正常输出版本。
- 服务器已配置 2G swap 作为兜底（正常运行不依赖它，只吸收短时突发）。

```bash
# 检查 swap（没有的话按需创建）
free -h
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 2. 取得代码与准备配置

```bash
git clone <仓库地址> /opt/zixxx
cd /opt/zixxx
cp .env.example .env
```

编辑 `.env`，至少填写以下四项：

| 变量 | 说明 |
| --- | --- |
| `DJANGO_SECRET_KEY` | 稳定的随机值。缺失时服务拒绝启动。 |
| `NEXUS_MASTER_KEY` | 加密用户模型 Key 的主密钥。**一旦更换，历史密文将无法解密。** |
| `POSTGRES_PASSWORD` | 数据库密码。 |
| `PUBLIC_BASE_URL` | 站点对外地址，手机扫码二维码依赖它。 |
| `DJANGO_ALLOWED_HOSTS` | 实际域名，逗号分隔。 |

生成两个密钥：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

第二条命令需要 `cryptography`；没有时先 `pip install cryptography`，或在本机生成后复制到服务器。

## 3. 启动

```bash
docker compose build
docker compose up -d
docker compose ps
```

首次启动后端镜像不会自动执行迁移，按顺序执行：

```bash
docker compose exec web python manage.py migrate --noinput
docker compose exec web python manage.py collectstatic --noinput
```

## 4. 创建账号

```bash
# 预置账号的初始口令（若之前用过预设口令，需要在此重设）
docker compose exec web python manage.py init_users

# 为指定账号初始化个人知识条目（可选，幂等）
docker compose exec web python manage.py seed_personal_knowledge --owner qzx
```

`init_users` 会重置仍使用公开预设口令的账号并撤销其 Token。执行后请用新口令登录并尽快再次改密。

## 5. HTTPS 证书

Nginx 需要证书才能提供 HTTPS：

```bash
mkdir -p deploy/certbot-webroot
# 首次签发（把域名换成实际域名）
docker compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d workbench.example.com \
  --agree-tos -m you@example.com --no-eff-email
```

签发后重启 Nginx：

```bash
docker compose restart nginx
```

续期由 `certbot` 服务负责（每天检查两次）：

```bash
docker compose --profile tools up -d certbot
```

## 6. 备份与恢复

```bash
# 备份数据库与资料（默认输出到 ./backups）
deploy/backup.sh

# 恢复（必须显式加 --force）
deploy/restore.sh backups/db-20261114-030000.dump.gz backups/media-20261114-030000.tar.gz --force
```

`restore.sh` 会导入数据库、还原资料目录、应用迁移并重建知识库索引。恢复演练建议在独立目录或测试实例上先做一次，确认登录、私人资料下载、资料归属、模型 Key 解密、任务记录与知识引用都正常。

建议用 cron 每天执行一次备份并把备份同步到另一台机器：

```cron
30 3 * * * /opt/zixxx/deploy/backup.sh /opt/zixxx/backups >> /var/log/zixxx-backup.log 2>&1
```

## 7. 日常运维

```bash
# 查看状态与内存占用
docker compose ps
docker stats --no-stream

# 查看日志
docker compose logs -f --tail=100 web
docker compose logs -f --tail=100 worker

# 健康检查
curl -s http://127.0.0.1/api/health/live/    # 进程存活
curl -s http://127.0.0.1/api/health/ready/   # 数据库与 Redis 就绪
```

worker 被 OOM 终止后，租约到期（默认 120 秒）后作业会被重新领取，不会留下半成品索引：

```bash
docker compose up -d worker
```

## 8. 升级流程

```bash
cd /opt/zixxx
git pull
docker compose build
deploy/backup.sh                       # 先备份
docker compose up -d
docker compose exec web python manage.py migrate --noinput
docker compose exec web python manage.py collectstatic --noinput
```

需要回滚时，恢复与原版本匹配的数据库及媒体快照；只回退镜像无法撤销已经发生的结构变化。

## 9. 尚未包含的部分

- 真实域名、服务器地址与新模型 Key 需要自行填写，本仓库不包含任何真实凭据。
- 证书签发需要服务器能访问 Let's Encrypt。
- 首次上线前请按 [TRAE_HANDOFF.md](TRAE_HANDOFF.md) 第 13 节逐项验收。
