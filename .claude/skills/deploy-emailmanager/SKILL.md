---
name: deploy-emailmanager
description: 部署邮件管理器到 PKU NAS（Docker Compose）
---

# 部署 Email Manager 到 NAS

将 emailmanager 项目部署到群晖 NAS（pkunas）。

## 前置条件

- 代码已提交并推送到 GitHub (`ni1o1/emailmanager`, main 分支)
- NAS 可通过 `remote-ssh` skill 连接（默认用 `pkunas-lan` 局域网直连，不通则用 `pkunas` frp 隧道）

## 部署步骤

### 1. 确认本地代码已推送

```bash
cd "/Users/yuqing/课题/项目/emailmanager" && git status && git log --oneline -3
```

如果有未提交的更改，先提交推送。

### 2. 选择 NAS 连接方式

优先尝试局域网直连：

```bash
python3 ~/.claude/skills/remote-ssh/scripts/remote_tools.py -s pkunas-lan bash "echo OK"
```

如果失败，改用 frp 隧道（需先确保 frpc_visitor 容器运行）：

```bash
docker ps --filter name=frpc_visitor --format '{{.Names}}'
# 如果没运行：
docker start frpc_visitor
# 然后用 -s pkunas 替代 -s pkunas-lan
```

以下用 `$NAS` 代表选定的服务器名（`pkunas-lan` 或 `pkunas`）。

### 3. 拉取最新代码

```bash
python3 ~/.claude/skills/remote-ssh/scripts/remote_tools.py -s $NAS bash "cd /home/ni1o1/emailmanager && git pull"
```

### 4. 停止旧容器、重建并启动

```bash
python3 ~/.claude/skills/remote-ssh/scripts/remote_tools.py -s $NAS bash "cd /home/ni1o1/emailmanager && docker compose down && docker compose up -d --build"
```

超时设置建议 300 秒（NAS 构建镜像较慢）。

### 5. 验证部署

```bash
python3 ~/.claude/skills/remote-ssh/scripts/remote_tools.py -s $NAS bash "docker ps --filter name=emailmanager --format '{{.Names}} {{.Status}}' && echo '---' && docker logs emailmanager --tail 15"
```

确认：
- 容器状态为 `Up`
- 日志显示 "配置验证通过" 和 "邮件监控已启动"
- 飞书收到启动通知

## 项目结构（NAS 端）

| 路径 | 说明 |
|------|------|
| `/home/ni1o1/emailmanager/` | 项目根目录（git 仓库） |
| `/home/ni1o1/emailmanager/.env` | 环境变量（API Key、邮箱密码等，不在 git 中） |
| `/home/ni1o1/emailmanager/state.db` | SQLite 状态数据库（挂载到容器） |
| `/home/ni1o1/emailmanager/logs/` | 日志目录（挂载到容器） |

## 回滚

如果新版本有问题：

```bash
# 在 NAS 上回退到上一个 commit
python3 ~/.claude/skills/remote-ssh/scripts/remote_tools.py -s $NAS bash "cd /home/ni1o1/emailmanager && git log --oneline -5"
# 记下要回退的 commit hash，然后：
python3 ~/.claude/skills/remote-ssh/scripts/remote_tools.py -s $NAS bash "cd /home/ni1o1/emailmanager && git checkout <commit_hash> && docker compose down && docker compose up -d --build"
```

## 查看运行日志

```bash
# 实时日志（最近50行）
python3 ~/.claude/skills/remote-ssh/scripts/remote_tools.py -s $NAS bash "docker logs emailmanager --tail 50"
```
