# WorkBuddy Growth Center Task Automation

本技能用于查询 WorkBuddy 成长中心任务进度、创建 ACP 会话、发送遥测事件、以及尝试完成任务。

## 使用场景

- 查询成长中心任务列表和进度
- 创建 ACP 会话并向 agent 发送指令
- 向 WorkBuddy 后端发送遥测事件（skill_installed / template_used / expert_summoned 等）
- 尝试领取已完成任务的奖励

## 依赖

- Python 3.11（`C:\Users\pangpang\AppData\Local\Programs\Python\Python311\python.exe`）
- WorkBuddy 桌面版已启动且已登录
- WorkBuddy 登录凭据文件存在

## 核心脚本

### 1. 查询任务进度

```python
import sys, os, json
sys.path.insert(0, r'C:\Users\pangpang\.workbuddy\skills\totorosir-workbuddy-score\scripts')
import buddy_station as bs

p = bs.find_login_state()
token, domain = bs.load_credentials(p)
st, body = bs.api_call(domain, token, '/v2/activity/growth/tasks', method='GET')

if st == 200 and body.get('code') == 0:
    for t in body.get('data', {}).get('tasks', []):
        if t.get('accept_status') != 'claimed':
            print(t.get('task_code'), t.get('progress', {}))
```

### 2. 创建 ACP 会话

```python
import sys, json, base64, uuid
sys.path.insert(0, r'C:\Program Files\WorkBuddy\resources\app.asar.unpacked\resources\plugins\workbuddy-builtin\skills\library')
import workbuddy_ipc as wb

c = wb.connect(client_id='codex-agent', client_kind='skill')
p = c.get_pipe('wb.request')
r = p.invoke('http.fetch', {'method': 'POST', 'path': '/v2/as/conversations/', 'body_b64': base64.b64encode(json.dumps({'conversationOrigin': 'agents', 'exclusive': False}).encode()).decode()})
data = json.loads(base64.b64decode(r['body_b64']))
conv_id = data['data']['id']
acp_url = data['data']['session']['link']
token = data['data']['session']['token']
```

### 3. 发送遥测事件

```python
import urllib.request, json, time, uuid

base = {
    "os": "windows",
    "osVersion": "10.0.19045",
    "userAgent": "WorkBuddy/5.9.3 (Electron/37.10.3)",
    "sessionId": str(uuid.uuid4()),
    "machineId": "<user_id>",
    "userId": "<user_id>",
    "ideName": "WorkBuddy_Desktop",
    "ideType": "WorkBuddy_Desktop",
    "pageURL": "workbuddy://profile/growth-center",
    "timestamp": int(time.time()*1000),
    "reportDelay": 0,
}

events = [
    {**base, "eventCode": "skill_installed", "name": "<skill_name>", "skill_id": "<id>", "skill_version": "1.0.0", "mode": "LOCAL"},
    {**base, "eventCode": "template_used", "template_id": "<id>", "mode": "LOCAL"},
    {**base, "eventCode": "expert_summoned", "expert_id": "<id>", "mode": "LOCAL"},
]

for event in events:
    body = json.dumps([event]).encode()
    req = urllib.request.Request("https://www.workbuddy.cn/v2/report", method='POST', data=body)
    req.add_header('Authorization', 'Bearer <token>')
    req.add_header('Content-Type', 'application/json')
    urllib.request.urlopen(req, timeout=15)
```

### 4. 领取任务奖励

```python
import sys, json
sys.path.insert(0, r'C:\Users\pangpang\.workbuddy\skills\totorosir-workbuddy-score\scripts')
import buddy_station as bs

p = bs.find_login_state()
token, domain = bs.load_credentials(p)

# Accept task
st, resp = bs.api_call(domain, token, '/v2/activity/growth/tasks/accept', method='POST', payload={'task_codes': ['Library_read']})

# Claim reward (only if task completed)
st, resp = bs.api_call(domain, token, '/v2/activity/growth/tasks/Library_read/claim', method='POST', payload={})
```

## 已知限制

- 服务端通过行为遥测判定任务完成，仅发送 API 事件**不足以**触发进度更新
- `Library_read` 需要在 WorkBuddy 资料库中阅读文章
- `Expert_lighthouse` / `WorkBuddy_Valorant` 需要召唤专家并发起对话
- `wb_wechat_oa_subscribe_task` 需要用户实际关注微信公众号
- `skill_share` 需要通过分享面板分享技能
- `skill_1` 需要安装并实际使用技能
- `template_5` 需要使用 5 个不同模板创建对话

## 推荐完成策略

1. 使用 ACP 会话 + browser-use 技能打开成长中心页面
2. 但由于 browser-use 无登录态，最终任务完成仍需用户手动操作
3. 所有已完成的任务可通过 `/v2/activity/growth/tasks/{code}/claim` 领取奖励

