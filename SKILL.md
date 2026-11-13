---
name: workbuddy-growth-task
description: Query and automate WorkBuddy growth center tasks, including progress checks, ACP sessions, telemetry events and reward claiming. Use when the user asks about WorkBuddy growth tasks or task rewards. Do not use for other apps.
---

# WorkBuddy 成长中心任务

通过 `scripts/growth.py` 操作 WorkBuddy 成长中心：查询任务、接取、领取奖励、发送遥测、发起 ACP 会话。

## 前置条件

- Python 3.8+，WorkBuddy 桌面版已安装并已登录
- 本机存在 `buddy_station` 模块（提供登录态读取）；通常由 `~/.workbuddy/skills/*/scripts/` 提供
- `acp` 子命令额外需要 WorkBuddy 客户端正在运行，以及内置的 `workbuddy_ipc`

路径无需手动配置，`scripts/wb_env.py` 会自动探测。探测失败时用环境变量覆盖：

| 变量 | 含义 |
|------|------|
| `WB_BUDDY_STATION_DIR` | `buddy_station.py` 所在目录 |
| `WB_LIBRARY_DIR` | WorkBuddy 内置 skill library 目录（含 `workbuddy_ipc`） |
| `WB_CONFIG_DIR` | WorkBuddy 配置根目录，默认 `~/.workbuddy` |
| `WB_MACHINE_ID` | 发送遥测事件时使用的机器/用户 ID |
| `WB_OS_VERSION` | 遥测中的 osVersion，默认 `10.0.19045` |

## 命令

所有命令在技能目录下执行，形如 `python scripts/growth.py <子命令>`。

```bash
# 列出未领取的任务与进度
python scripts/growth.py tasks
# 包含已领取的任务
python scripts/growth.py tasks --all

# 接取任务
python scripts/growth.py accept Library_read

# 领取已完成任务的奖励
python scripts/growth.py claim Library_read

# 探测公众号关注任务接口（只读探测）
python scripts/growth.py subscribe

# 发送遥测事件；--dry-run 只打印请求体
python scripts/growth.py events --event skill_installed --id my-skill --dry-run

# 创建 ACP 会话并发送指令，等待 60 秒
python scripts/growth.py acp "你好，回复 OK" --wait 60
```

`tasks` 每行输出 `task_code`、`accept_status`、`progress`，字段以制表符分隔。

## 注意事项

- `events` 会向 WorkBuddy 上报接口提交带有 machineId / userAgent 的事件。伪造行为遥测以完成任务可能违反平台条款，可能带来账号风险，只在明确知情时使用，并优先使用 `--dry-run` 校验。
- 服务端以行为遥测判定任务完成，仅发送 API 事件通常**不足以**推进进度。
- 需要真实操作才能完成的任务：`Library_read`（阅读资料库文章）、`Expert_lighthouse` / `WorkBuddy_Valorant`（召唤专家对话）、`wb_wechat_oa_subscribe_task`（关注公众号）、`skill_share`（分享面板）、`skill_1`（安装并使用技能）、`template_5`（使用 5 个模板建对话）。
- 已完成的任务可通过 `claim` 领取奖励；未完成时接口会返回错误码。
