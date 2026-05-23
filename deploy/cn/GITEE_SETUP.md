# Gitee 镜像（可选，但强烈推荐）

国内服务器从 GitHub `git clone` 可能 10-60 秒不等，加上 Gitee 镜像后稳定 < 1 秒。

## 一次性设置（5 分钟）

### 1. 注册 Gitee 账号
- 打开 https://gitee.com/signup
- 用手机号注册即可（无需实名，但**推送大于 100 MB 的仓库**才需实名）

### 2. 在 Gitee 创建空仓库
- 入口：https://gitee.com/projects/new
- 仓库名：`ai-manju-xiaoyunque`（与 GitHub 同名）
- **不要**勾选 README/.gitignore/许可证
- 保存后会得到一个 URL，形如 `https://gitee.com/<你的用户名>/ai-manju-xiaoyunque.git`

### 3. 生成 Gitee 私人令牌
- 入口：https://gitee.com/profile/personal_access_tokens
- 标题随意（如 `github-mirror`）
- 勾选权限：`projects` + `pull_requests` + `issues`
- 提交后**立即复制**长令牌（只显示一次）

### 4. 在 GitHub 配置 3 个 Secret
打开 https://github.com/bistuwangqiyuan/ai-manju-xiaoyunque/settings/secrets/actions

新增 3 个 Secret：

| Name | Value |
|---|---|
| `GITEE_USERNAME` | 你的 Gitee 用户名（如 `bistuwangqiyuan`） |
| `GITEE_PASSWORD` | 第 3 步复制的私人令牌 |
| `GITEE_REPO` | 第 2 步的仓库 URL（带 `.git`） |

### 5. 触发首次同步
```bash
git commit --allow-empty -m "chore: trigger gitee mirror"
git push
```

GitHub Actions 会自动执行 `.github/workflows/gitee-mirror.yml`，把 main 分支强制推到 Gitee。

之后**每次 push 到 main**都会自动同步，无需操作。

## 验证

```bash
# 任何机器上：
curl -fsSL https://gitee.com/<你的用户名>/ai-manju-xiaoyunque/raw/main/README.md | head
```

能看到 README 内容即成功。

## 之后 install.sh 就会优先走 Gitee

`deploy/cn/install.sh` 默认从 Gitee 拉代码，GitHub 作为回退。如果你的 Gitee 用户名 != `bistuwangqiyuan`，
请在执行 install.sh 前设置：

```bash
export GIT_URL=https://gitee.com/你的用户名/ai-manju-xiaoyunque.git
bash <(curl -fsSL https://gitee.com/你的用户名/ai-manju-xiaoyunque/raw/main/deploy/cn/install.sh)
```
