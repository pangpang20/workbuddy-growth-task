import sys, os, json, urllib.request
sys.path.insert(0, r'C:\Users\pangpang\.workbuddy\skills\totorosir-workbuddy-score\scripts')
import buddy_station as bs

p = bs.find_login_state()
print("auth file:", p)
token, domain = bs.load_credentials(p)
print("domain:", domain, "token len:", len(token))

# Direct HTTP to growth tasks (bypass daemon proxy)
st, body = bs.api_call(domain, token, '/v2/activity/growth/tasks', method='GET')
print("status:", st)
if isinstance(body, dict) and body.get('code') == 0:
    for t in body.get('data', {}).get('tasks', []):
        if t.get('accept_status') != 'claimed':
            print(t.get('task_code'), t.get('progress', {}))
else:
    print(body)
