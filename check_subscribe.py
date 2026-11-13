import sys, json
sys.path.insert(0, r'C:\Users\pangpang\.workbuddy\skills\totorosir-workbuddy-score\scripts')
import buddy_station as bs
p = bs.find_login_state()
token, domain = bs.load_credentials(p)

# Try the subscribe-task endpoint which might have a completion check
for method, path, body in [
    ('GET', '/v2/activity/growth/subscribe-task/status', None),
    ('POST', '/v2/activity/growth/subscribe-task/subscribe', {}),
    ('POST', '/v2/activity/growth/subscribe-task/check', {}),
    ('POST', '/v2/activity/growth/subscribe-task', {}),
]:
    if method == 'GET':
        st, resp = bs.api_call(domain, token, path, method='GET')
    else:
        st, resp = bs.api_call(domain, token, path, method='POST', payload=body)
    print(f'{st} {method} {path} -> {json.dumps(resp, ensure_ascii=False)[:300]}')
