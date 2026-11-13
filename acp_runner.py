import sys, json, base64, urllib.request, uuid, time, threading, http.client
from urllib.parse import urlparse
sys.path.insert(0, r'C:\Program Files\WorkBuddy\resources\app.asar.unpacked\resources\plugins\workbuddy-builtin\skills\library')
import workbuddy_ipc as wb

PROMPT = sys.argv[1] if len(sys.argv) > 1 else 'Hello! Respond with one word: OK'
WAIT_SECONDS = int(sys.argv[2]) if len(sys.argv) > 2 else 120

c = wb.connect(client_id='codex-agent', client_kind='skill')
p = c.get_pipe('wb.request')

def api(method, path, body=None):
    kwargs = {'method': method, 'path': path}
    if body:
        kwargs['body_b64'] = base64.b64encode(json.dumps(body).encode()).decode()
    r = p.invoke('http.fetch', kwargs)
    raw = base64.b64decode(r.get('body_b64', b'')).decode() if r.get('body_b64') else ''
    try:
        return r.get('status'), json.loads(raw) if raw else {}
    except Exception:
        return r.get('status'), raw[:300]

status, conv = api('POST', '/v2/as/conversations/', {'conversationOrigin': 'agents', 'exclusive': False})
conv_id = conv['data']['id']
session_info = conv['data']['session']
acp_url = session_info['link']
token = session_info['token']

status2, sess = api('POST', f'/v2/as/conversations/{conv_id}/session', {})
session_id = sess.get('data', {}).get('sessionId', '')
conn_id = str(uuid.uuid4())

print(f'conv={conv_id}')
print(f'session={session_id}')
print(f'acp_url={acp_url}')
sys.stdout.flush()

parsed = urlparse(acp_url)
host = parsed.hostname
path = parsed.path

ctx = __import__('ssl').create_default_context()
http_conn = http.client.HTTPSConnection(host, 443, timeout=300, context=ctx)
headers = {
    'Authorization': f'Bearer {token}',
    'Accept': 'text/event-stream',
    'acp-connection-id': conn_id,
    'X-Conversation-ID': conv_id,
    'x-codebuddy-request': '1',
    'Cache-Control': 'no-cache',
}
http_conn.request('GET', path, headers=headers)
response = http_conn.getresponse()
print(f'sse_status={response.status}')
sys.stdout.flush()

sse_lines = []
sse_done = threading.Event()

def read_sse():
    try:
        while True:
            line = response.fp.readline()
            if not line:
                break
            decoded = line.decode('utf-8', errors='replace').strip()
            if decoded:
                sse_lines.append(decoded)
                if 'agent_message' in decoded or 'completed' in decoded:
                    sse_done.set()
                if len(sse_lines) > 5000:
                    break
    except Exception:
        pass

sse_thread = threading.Thread(target=read_sse, daemon=True)
sse_thread.start()
time.sleep(2)

prompt_body = json.dumps({
    'jsonrpc': '2.0', 'id': 1, 'method': 'session/prompt',
    'params': {'sessionId': session_id, 'prompt': [{'type': 'text', 'text': PROMPT}]},
}).encode()

req = urllib.request.Request(acp_url, data=prompt_body, method='POST')
req.add_header('Authorization', f'Bearer {token}')
req.add_header('Content-Type', 'application/json')
req.add_header('Accept', 'application/json, text/event-stream')
req.add_header('acp-connection-id', conn_id)
req.add_header('X-Conversation-ID', conv_id)
req.add_header('x-codebuddy-request', '1')

try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        print(f'prompt_status={resp.status}')
except Exception as e:
    code = getattr(e, 'code', 'ERR')
    body_txt = ''
    if hasattr(e, 'read'):
        try:
            body_txt = e.read().decode()[:300]
        except Exception:
            pass
    print(f'prompt_status={code} body={body_txt}')
sys.stdout.flush()

deadline = time.time() + WAIT_SECONDS
while time.time() < deadline and not sse_done.is_set():
    time.sleep(2)

print('--- FINAL AGENT MESSAGE ---')
final_text = []
thoughts = []
for line in sse_lines:
    if '"sessionUpdate":"agent_message_chunk"' in line:
        try:
            payload = json.loads(line.split('data: ', 1)[1])
            chunk = payload.get('params', {}).get('update', {}).get('content', {})
            if isinstance(chunk, dict) and chunk.get('text'):
                final_text.append(chunk['text'])
        except Exception:
            pass
print('THOUGHTS:', ''.join(thoughts)[:3000])
print('MESSAGE:', ''.join(final_text)[:2000])
print('--- END MESSAGE ---')
for line in sse_lines[-80:]:
    print(line)
http_conn.close()


