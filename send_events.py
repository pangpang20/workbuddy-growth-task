import sys, json, time, uuid
sys.path.insert(0, r'C:\Users\pangpang\.workbuddy\skills\totorosir-workbuddy-score\scripts')
import buddy_station as bs
p = bs.find_login_state()
token, domain = bs.load_credentials(p)

# Read the event map
with open(r'C:\Users\pangpang\Documents\Codex\2026-11-12\new-chat-2\work\event_map.json', 'r', encoding='utf-8') as f:
    em = json.load(f)

# Find which enum names map to what we need
targets = {'SkillInstalled': 'skill_installed', 'SkillAction': 'skill_action', 'ExpertSummoned': 'expert_summoned', 'TemplateUsed': 'template_used'}
print("Event map keys:", list(targets.keys()))
for k, v in targets.items():
    mapped = em['enum'].get(k, 'NOT FOUND')
    print(f'{k} -> {mapped}')

# Let me also try sending the events with the product set to Desktop (not UserCenter)
# The desktop app uses ideType=WorkBuddy_Desktop, and the event goes through the desktop telemetry
base = {
    "os": "windows",
    "osVersion": "10.0.19045",
    "userAgent": "WorkBuddy/5.9.3 (Electron/37.10.3)",
    "sessionId": str(uuid.uuid4()),
    "machineId": "3c250bcd-9a09-45d4-a4c9-88100d4f052c",
    "userId": "3c250bcd-9a09-45d4-a4c9-88100d4f052c",
    "ideName": "WorkBuddy_Desktop",
    "ideType": "WorkBuddy_Desktop",
    "pageURL": "workbuddy://profile/growth-center",
    "timestamp": int(time.time()*1000),
    "reportDelay": 0,
}

import urllib.request, urllib.error
url = f"https://{domain}/v2/report"

events = [
    {**base, "eventCode": "skill_installed", "name": "test-skill-1", "skill_id": "test-skill-1", "skill_version": "1.0.0", "mode": "LOCAL"},
    {**base, "eventCode": "template_used", "template_id": "124", "mode": "LOCAL"},
    {**base, "eventCode": "expert_summoned", "expert_id": "lighthouse", "expert_id_marketplace": "lighthouse", "mode": "LOCAL"},
    {**base, "eventCode": "skill_action", "name": "test-skill-1", "skill_id": "test-skill-1", "skill_version": "1.0.0", "action": "use", "mode": "LOCAL"},
    {**base, "eventCode": "expert_actual_use", "expert_id": "lighthouse", "mode": "LOCAL"},
    {**base, "eventCode": "agent_task_created_with_template", "template_id": "125", "mode": "LOCAL"},
]

for event in events:
    body = json.dumps([event]).encode()
    req = urllib.request.Request(url, method='POST', data=body)
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f'{event["eventCode"]}: {resp.status}')
    except urllib.error.HTTPError as e:
        print(f'{event["eventCode"]}: {e.code} {e.read().decode()[:200]}')
    except Exception as e:
        print(f'{event["eventCode"]}: {e}')
