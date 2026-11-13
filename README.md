# workbuddy-growth-task

WorkBuddy 成长中心任务自动化技能。通过统一 CLI 查询任务、接取、领取奖励、发送遥测事件、发起 ACP 会话。

## 功能

- **查询任务**：拉取成长中心任务列表与进度
- **接取 / 领取**：对可领取的任务调用 accept / claim 接口
- **遥测事件**：向 WorkBuddy 后端发送 `skill_installed` / `template_used` / `expert_summoned` 等事件
- **ACP 会话**：通过 WorkBuddy 内置 `workbuddy_ipc` 创建 ACP 会话并向 agent 发送指令

## 目录结构

```
workbuddy-growth-task/
├── SKILL.md          # Trae / WorkBuddy 技能描述（含 frontmatter）
├── README.md         # 本文档
├── LICENSE
└── scripts/
    ├── growth.py     # 统一 CLI：tasks / accept / claim / subscribe / events / acp
    └── wb_env.py     # 自动探测依赖模块、读取登录态、封装 API 调用
```

## 前置条件

- Python 3.8+
- WorkBuddy 桌面版已安装并已登录
- 本机存在 `buddy_station` 模块（由 `~/.workbuddy/skills/*/scripts/buddy_station.py` 提供）
- `acp` 子命令额外需要 WorkBuddy 客户端正在运行，以及内置的 `workbuddy_ipc`

路径无需手动配置，`scripts/wb_env.py` 会自动探测。探测失败时可通过环境变量覆盖：

| 变量 | 含义 |
|------|------|
| `WB_BUDDY_STATION_DIR` | `buddy_station.py` 所在目录 |
| `WB_LIBRARY_DIR` | WorkBuddy 内置 skill library 目录（含 `workbuddy_ipc`） |
| `WB_CONFIG_DIR` | WorkBuddy 配置根目录，默认 `~/.workbuddy` |
| `WB_MACHINE_ID` | 发送遥测事件时使用的机器 / 用户 ID |
| `WB_OS_VERSION` | 遥测中的 osVersion，默认 `10.0.19045` |

## 快速上手

```bash
cd workbuddy-growth-task

# 列出未领取的任务与进度
python scripts/growth.py tasks
python scripts/growth.py tasks --all         # 包含已领取的任务

# 接取 / 领取奖励
python scripts/growth.py accept Library_read
python scripts/growth.py claim Library_read

# 探测公众号关注任务接口（只读）
python scripts/growth.py subscribe

# 发送遥测事件；--dry-run 只打印请求体，不上报
python scripts/growth.py events --event skill_installed --id my-skill --dry-run

# 创建 ACP 会话并发送指令
python scripts/growth.py acp "你好，回复 OK" --wait 60
```

`tasks` 每行输出 `task_code`、`accept_status`、`progress`，字段以制表符分隔。

## 子命令

| 命令 | 说明 |
|------|------|
| `tasks [--all]` | 查询成长中心任务与进度；默认过滤掉已领取 |
| `accept <task_code>...` | 接取一个或多个任务 |
| `claim <task_code>...` | 领取一个或多个已完成任务的奖励 |
| `subscribe` | 只读探测公众号关注任务相关接口 |
| `events [--event CODE]... [--id ID] [--machine-id ID] [--url URL] [--dry-run]` | 发送遥测事件；默认发送三类常用事件 |
| `acp [PROMPT] [--wait SECONDS]` | 创建 ACP 会话并向 agent 发送指令 |

## 已知限制

- 服务端通过行为遥测判定任务完成，仅发送 API 事件通常**不足以**推进进度
- 需要真实操作才能完成的任务：`Library_read`（阅读资料库文章）、`Expert_lighthouse` / `WorkBuddy_Valorant`（召唤专家对话）、`wb_wechat_oa_subscribe_task`（关注公众号）、`skill_share`（分享面板）、`skill_1`（安装并实际使用技能）、`template_5`（使用 5 个模板建对话）
- 已完成的任务可通过 `claim` 领取奖励；未完成时接口会返回错误码

## 风险提示

`events` 子命令会向 WorkBuddy 上报接口提交带有 machineId / userAgent 的事件。伪造行为遥测以完成任务可能违反平台条款，可能带来账号风险，只在明确知情时使用，并优先使用 `--dry-run` 校验请求体。

## 许可证

见 [LICENSE](LICENSE)。
