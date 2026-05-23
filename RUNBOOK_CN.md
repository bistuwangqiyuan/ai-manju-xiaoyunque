# 国内一键部署 · 小云雀 AI 漫剧（15 分钟上线）

> 目标：让国内用户**最快 15 分钟**把整套漫剧平台跑起来；
> 国内 CDN 加速、国内 pip/npm/Docker 镜像、国内备份 git 源（Gitee）、
> Caddy 自动 HTTPS、SSL 证书自动续期、SQLite→Postgres 持久化。
>
> 你需要做的只有三件事：**1) 买台服务器 → 2) SSH 进去 → 3) 粘贴一行命令**。

---

## 0. 技术栈一览

| 层 | 选型 | 原因 |
|---|---|---|
| **服务器** | 腾讯云 / 阿里云 **轻量应用服务器** 2 vCPU 2GB ¥9-24/月起 | 国内带宽便宜、按月付、面板友好；可选**香港节点免备案** |
| **容器** | Docker 27 + Compose v2，daemon 接 4 个国内镜像加速 | 国内 `docker pull` 秒级 |
| **后端** | FastAPI + 自带 worker，Python 3.11，pip 走清华镜像 | 沿用 v8 镜像，0 改动业务代码 |
| **前端** | Next.js 15 standalone，npm 走 npmmirror | Vercel 平替，自托管，无地域限制 |
| **数据库** | Postgres 16-alpine（容器内，挂数据卷） | 免运维，可后续迁腾讯云 RDS |
| **反代+HTTPS** | Caddy 2.8（自动 Let's Encrypt） | 1 行配置自动续期，比 Nginx 简单 10 倍 |
| **代码源** | GitHub（主）+ Gitee（国内镜像，自动同步） | 上服务器拉代码 < 1 秒 |
| **CI/CD** | GitHub Actions（已配） + `upgrade.sh`（服务器一键升级） | 也可手动 `git pull && ./upgrade.sh` |

> 这套与原 Railway+Vercel 方案**并存不冲突**：海外用户走 Railway/Vercel，国内用户走这套。

---

## 1. 第一步 · 买一台轻量服务器（5 分钟）

### 推荐配置

- **CPU/内存**：2 vCPU / 2 GB（起步够用，可后续升级）
- **带宽**：5 Mbps（国内出口够 100 并发；想跑大流量上 10 Mbps）
- **系统镜像**：**Ubuntu 24.04 LTS** ★ 推荐
- **地域**：
  - 用户主要在国内 → **上海 / 广州 / 北京**（需要域名备案）
  - 不想备案 → **香港**（免备案，¥24-32/月）

### 三大厂商推荐链接（任选其一）

| 厂商 | 入口 | 当前促销（2026-05） | 备注 |
|---|---|---|---|
| 腾讯云 | https://cloud.tencent.com/act/pro/lighthouse | 2C2G 4M ¥9/月起（学生新人价） | 控制台最友好 |
| 阿里云 | https://www.aliyun.com/product/swas | 2C2G 3M ¥99/年 | 老牌稳定 |
| 华为云 | https://www.huaweicloud.com/product/hecs.html | 2C2G 3M ¥99/年 | 政企友好 |

> 注册需身份证实名认证，约 2 分钟。下单后在控制台「重置密码」设置一个 root 密码。

### 服务器购买后必做：开放端口

进控制台 → 防火墙 / 安全组 → 放行：`22 (SSH)`、`80 (HTTP)`、`443 (HTTPS)`。

---

## 2. 第二步 · SSH 连上去（1 分钟）

**Windows 用户**（PowerShell 自带 ssh）：

```powershell
ssh root@<你的服务器公网 IP>
# 输入刚才设置的 root 密码
```

**macOS / Linux**：

```bash
ssh root@<你的服务器公网 IP>
```

---

## 3. 第三步 · 一行命令安装（5-10 分钟）

### 3a. 没有域名（直接用 IP 访问，HTTP）

```bash
bash <(curl -fsSL https://gitee.com/bistuwangqiyuan/ai-manju-xiaoyunque/raw/main/deploy/cn/install.sh)
```

> 脚本自动：装 Docker → 配国内镜像 → 拉代码（Gitee 失败自动回退 GitHub）→ 生成强随机密码 → 构建镜像 → 启动整栈 → 健康检查。

**完成后访问**：`http://<服务器公网 IP>/`

### 3b. 有域名（推荐，自动 HTTPS）

**先**到域名厂商把一条 `A` 记录指向服务器 IP，例如 `manju.example.com → 123.45.67.89`，**等 1 分钟 DNS 生效**。

然后：

```bash
export DOMAIN=manju.example.com
export ACME_EMAIL=you@example.com
bash <(curl -fsSL https://gitee.com/bistuwangqiyuan/ai-manju-xiaoyunque/raw/main/deploy/cn/install.sh)
```

> Caddy 会自动从 Let's Encrypt 申请证书（约 30 秒），自动续期。

**完成后访问**：`https://manju.example.com/`

---

## 4. 填 API Key（按需，可后填）

```bash
cd /opt/xyq/deploy/cn
nano .env       # 或 vim .env
```

**最少必填只有 3 个**（脚本已自动填好）：`POSTGRES_PASSWORD` / `JWT_SECRET` / `DOMAIN`。

**想跑真实 AI**（否则走 mock 也能体验全流程）：至少填 2 个就够：

- `VOLC_ARK_API_KEY=` → 火山方舟（https://console.volcengine.com/ark）
- `ANTHROPIC_API_KEY=` → Claude（https://console.anthropic.com/ ；或用国内中转 `ANTHROPIC_BASE_URL=`）

填完热重启：

```bash
docker compose --env-file .env restart backend
```

---

## 5. 常用运维命令

```bash
cd /opt/xyq/deploy/cn

# 看后端实时日志（Ctrl+C 退出）
docker compose --env-file .env logs -f backend

# 看前端日志
docker compose --env-file .env logs -f web

# 看所有容器状态
docker compose --env-file .env ps

# 重启某个服务
docker compose --env-file .env restart backend

# 升级到最新（拉 git + 重建 + 滚动重启）
bash upgrade.sh

# 备份 Postgres + storage 到 ./backups/
bash backup.sh

# 停服
docker compose --env-file .env down

# 完全清理（含数据卷，慎用！）
docker compose --env-file .env down -v
```

---

## 6. 监控 / 续期 / 报警

- **HTTPS 续期**：Caddy 自动，无需操作
- **磁盘报警**：服务商控制台 → 监控 → 加阈值
- **数据库备份**：建议 `crontab -e` 加：`0 3 * * * /opt/xyq/deploy/cn/backup.sh`
- **进阶**：把 `./backups/*.pgdump` 上传到腾讯云 COS / 阿里云 OSS

---

## 7. 故障排查

| 现象 | 解决 |
|---|---|
| `Permission denied` 安装失败 | 用 `sudo bash install.sh`（脚本会提示） |
| `docker pull` 慢 | 已配 4 个国内加速。再不行换：`https://docker.mirrors.sjtug.sjtu.edu.cn` |
| `git clone` 慢 | 脚本已优先 Gitee；如 Gitee 也失败：在国内服务器 `git config --global url."https://gitclone.com/github.com/".insteadOf https://github.com/` |
| backend 起不来 | `docker compose --env-file .env logs backend` 看堆栈；常见是 `DATABASE_URL` / `JWT_SECRET` 没写入 |
| 80/443 占用 | `lsof -i:80` 杀掉自带 nginx：`systemctl stop nginx && systemctl disable nginx` |
| HTTPS 一直签发不下来 | 检查 DNS 是否真生效（`dig manju.example.com`）；端口 80 必须能从公网访问（用于 ACME 验证） |
| 升级后报 schema 不一致 | Alembic 迁移：`docker exec xyq-backend python -m app.migrate` |

---

## 8. 进阶：用腾讯云对象存储 COS 存视频（可选）

容器内默认把 mp4 写到 `storage-data` 数据卷。若想用 COS：

```env
# .env 里加
S3_ENDPOINT=cos.ap-shanghai.myqcloud.com
S3_REGION=ap-shanghai
S3_BUCKET=xyq-prod-1300000000
S3_ACCESS_KEY=xxxxxxxx
S3_SECRET_KEY=xxxxxxxx
S3_PUBLIC_BASE_URL=https://xyq-prod-1300000000.cos.ap-shanghai.myqcloud.com
```

代码已支持 S3 兼容 API（COS 完全兼容），重启 backend 即生效。

---

## 9. 进阶：用腾讯云 RDS / PolarDB 替代容器 Postgres（生产推荐）

不想自己管数据库？腾讯云 PostgreSQL Serverless 体验版 ¥1/月：

1. 控制台 → PostgreSQL → 购买实例 → 选 Serverless
2. 创建数据库 `xyq`，建用户 `xyq` / 强密码
3. 修改 `.env`：

   ```env
   DATABASE_URL=postgresql+psycopg2://xyq:密码@gz-postgres-xxx.sql.tencentcdb.com:5432/xyq
   ```

4. 注释掉 docker-compose.yml 里 `postgres` 服务（或保留作为本地开发用）
5. `docker compose --env-file .env up -d backend`

---

## 10. 上线后 3 分钟自检 ✅

```bash
# 1) 健康检查
curl https://manju.example.com/api/health
# {"ok":true,"version":"..."}

# 2) 前端能加载
curl -I https://manju.example.com/
# HTTP/2 200

# 3) 注册一个测试账号 + 创建测试任务
python3 /opt/xyq/scripts/deploy_smoke.py --base-url https://manju.example.com
```

全绿即上线成功 🎉

---

## 关于成本

| 项目 | 月度 |
|---|---|
| 轻量服务器 2C2G 4M | ¥9 - ¥24（学生/促销价 ¥9） |
| 域名 .com | ¥6 - ¥8 |
| 备案 | 免费（仅时间成本，14-21 天） |
| HTTPS 证书 | ¥0（Let's Encrypt） |
| COS 对象存储（可选） | ¥0.118/GB/月 |
| **合计（无 AI 调用）** | **¥15 - ¥32 / 月** |
| AI 调用（按用量） | 火山豆包 ¥0.01/千 tokens；其它见 `docs/api-contracts-2026-05.md` |

---

## 与原 Railway/Vercel 方案的对照

| 维度 | 国内方案（本文档） | 海外方案（`RUNBOOK.md`） |
|---|---|---|
| 国内访问速度 | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 部署难度 | 一行命令 | 三次点击 |
| 月成本 | ¥15-32 | $0-5（免费额度） |
| HTTPS | Caddy 自动 | 平台自带 |
| 弹性扩缩 | 手动加配 | 自动 |
| 数据归属 | 完全自主 | 在 Railway/Neon |
| 适合场景 | 国内 ToC、企业、需要备案 | 海外、个人 demo |

> 两套都已配齐，按需选择。
