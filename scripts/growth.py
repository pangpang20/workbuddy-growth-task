# -*- coding: utf-8 -*-
"""WorkBuddy 成长中心 CLI。

用法示例：
  python scripts/growth.py tasks
  python scripts/growth.py accept Library_read
  python scripts/growth.py claim Library_read
  python scripts/growth.py events --event skill_installed --id my-skill --dry-run
  python scripts/growth.py acp "你好，回复 OK" --wait 60
"""

import argparse
import base64
import json
import os
import sys
import time
import threading
import uuid
import urllib.request
import urllib.error
import http.client
from urllib.parse import urlparse

from wb_env import api, credentials, load_ipc

TASKS_PATH = "/v2/activity/growth/tasks"
DEFAULT_EVENTS = ("skill_installed", "template_used", "expert_summoned")


def _print_json(value):
    print(json.dumps(value, ensure_ascii=False))


def _fail(message, status=None):
    sys.stderr.write(message + "\n")
    return 1


# --- 任务查询与领取 -------------------------------------------------------

def cmd_tasks(args):
    st, body = api(TASKS_PATH, "GET")
    if st != 200 or not isinstance(body, dict) or body.get("code") != 0:
        return _fail("查询失败 status=%s body=%s" % (st, body))
    for task in body.get("data", {}).get("tasks", []):
        status = task.get("accept_status")
        if not args.all and status == "claimed":
            continue
        progress = json.dumps(task.get("progress", {}), ensure_ascii=False)
        print("%s\t%s\t%s" % (task.get("task_code"), status, progress))
    return 0


def cmd_accept(args):
    st, body = api(TASKS_PATH + "/accept", "POST", {"task_codes": args.task_codes})
    _print_json(body)
    return 0 if st == 200 else 1


def cmd_claim(args):
    code = 0
    for task_code in args.task_codes:
        st, body = api("%s/%s/claim" % (TASKS_PATH, task_code), "POST", {})
        print("%s\t%s" % (task_code, st))
        _print_json(body)
        if st != 200:
            code = 1
    return code


def cmd_subscribe(args):
    probes = [
        ("GET", "/v2/activity/growth/subscribe-task/status", None),
        ("POST", "/v2/activity/growth/subscribe-task/subscribe", {}),
        ("POST", "/v2/activity/growth/subscribe-task/check", {}),
        ("POST", "/v2/activity/growth/subscribe-task", {}),
    ]
    for method, path, payload in probes:
        st, body = api(path, method, payload)
        print("%s %s %s -> %s" % (st, method, path, json.dumps(body, ensure_ascii=False)[:300]))
    return 0


# --- 遥测事件 -------------------------------------------------------------

def _event_target(code, target):
    if code == "skill_installed":
        return {"name": target, "skill_id": target, "skill_version": "1.0.0"}
    if code == "template_used":
        return {"template_id": target}
    if code == "expert_summoned":
        return {"expert_id": target, "expert_id_marketplace": target}
    return {"target": target}


def cmd_events(args):
    _, token, domain, _ = credentials()
    machine_id = args.machine_id or os.environ.get("WB_MACHINE_ID")
    if not machine_id:
        return _fail("缺少 machineId：请传 --machine-id 或设置环境变量 WB_MACHINE_ID")
    url = args.url or "https://%s/v2/report" % domain
    base = {
        "os": "windows",
        "osVersion": os.environ.get("WB_OS_VERSION", "10.0.19045"),
        "userAgent": "WorkBuddy/5.9.3 (Electron/37.10.3)",
        "sessionId": str(uuid.uuid4()),
        "machineId": machine_id,
        "userId": machine_id,
        "ideName": "WorkBuddy_Desktop",
        "ideType": "WorkBuddy_Desktop",
        "pageURL": "workbuddy://profile/growth-center",
        "timestamp": int(time.time() * 1000),
        "reportDelay": 0,
    }
    for code in args.event:
        event = {**base, "eventCode": code, "mode": "LOCAL", **_event_target(code, args.id)}
        payload = json.dumps([event], ensure_ascii=False).encode("utf-8")
        if args.dry_run:
            print("[dry-run] %s %s" % (url, payload.decode("utf-8")))
            continue
        request = urllib.request.Request(url, method="POST", data=payload)
        request.add_header("Authorization", "Bearer " + token)
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                print("%s\t%s" % (code, response.status))
        except urllib.error.HTTPError as exc:
            print("%s\t%s %s" % (code, exc.code, exc.read().decode("utf-8", "replace")[:200]))
        except Exception as exc:  # noqa: BLE001
            print("%s\tERR %s" % (code, exc))
    return 0


# --- ACP 会话 -------------------------------------------------------------

def cmd_acp(args):
    wb = load_ipc()
    with wb.connect(client_id="codex-agent", client_kind="skill") as client:
        pipe = client.get_pipe("wb.request")

        def call(method, path, body=None):
            kwargs = {"method": method, "path": path}
            if body:
                kwargs["body_b64"] = base64.b64encode(json.dumps(body).encode()).decode()
            result = pipe.invoke("http.fetch", kwargs)
            raw = result.get("body_b64")
            text = base64.b64decode(raw).decode() if raw else ""
            try:
                return result.get("status"), json.loads(text) if text else {}
            except ValueError:
                return result.get("status"), text[:300]

        _, conv = call("POST", "/v2/as/conversations/", {"conversationOrigin": "agents", "exclusive": False})
        conv_id = conv["data"]["id"]
        session = conv["data"]["session"]
        acp_url, token = session["link"], session["token"]

        _, sess = call("POST", "/v2/as/conversations/%s/session" % conv_id, {})
        session_id = sess.get("data", {}).get("sessionId", "")
        conn_id = str(uuid.uuid4())

        print("conv=%s\nsession=%s\nacp_url=%s" % (conv_id, session_id, acp_url))
        sys.stdout.flush()

        parsed = urlparse(acp_url)
        connection = http.client.HTTPSConnection(parsed.hostname, 443, timeout=300)
        headers = {
            "Authorization": "Bearer " + token,
            "Accept": "text/event-stream",
            "acp-connection-id": conn_id,
            "X-Conversation-ID": conv_id,
            "x-codebuddy-request": "1",
            "Cache-Control": "no-cache",
        }
        connection.request("GET", parsed.path, headers=headers)
        response = connection.getresponse()
        print("sse_status=%s" % response.status)
        sys.stdout.flush()

        lines = []
        done = threading.Event()

        def read_sse():
            try:
                while True:
                    line = response.fp.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if not decoded:
                        continue
                    lines.append(decoded)
                    if "agent_message" in decoded or "completed" in decoded:
                        done.set()
                    if len(lines) > 5000:
                        break
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=read_sse, daemon=True).start()
        time.sleep(2)

        prompt_body = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "session/prompt",
            "params": {"sessionId": session_id, "prompt": [{"type": "text", "text": args.prompt}]},
        }).encode()
        request = urllib.request.Request(acp_url, data=prompt_body, method="POST")
        request.add_header("Authorization", "Bearer " + token)
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json, text/event-stream")
        request.add_header("acp-connection-id", conn_id)
        request.add_header("X-Conversation-ID", conv_id)
        request.add_header("x-codebuddy-request", "1")
        try:
            with urllib.request.urlopen(request, timeout=60) as resp:
                print("prompt_status=%s" % resp.status)
        except Exception as exc:  # noqa: BLE001
            print("prompt_status=%s body=%s" % (getattr(exc, "code", "ERR"), str(exc)[:200]))
        sys.stdout.flush()

        deadline = time.time() + args.wait
        while time.time() < deadline and not done.is_set():
            time.sleep(2)

        chunks = []
        for line in lines:
            if '"sessionUpdate":"agent_message_chunk"' not in line:
                continue
            try:
                payload = json.loads(line.split("data: ", 1)[1])
                content = payload.get("params", {}).get("update", {}).get("content", {})
                if isinstance(content, dict) and content.get("text"):
                    chunks.append(content["text"])
            except Exception:  # noqa: BLE001
                pass
        print("--- FINAL AGENT MESSAGE ---")
        print("MESSAGE:", "".join(chunks)[:2000])
        print("--- END MESSAGE ---")
        connection.close()
    return 0


# --- 入口 -----------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(prog="growth", description="WorkBuddy 成长中心任务工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("tasks", help="查询任务与进度")
    p.add_argument("--all", action="store_true", help="包含已领取的任务")
    p.set_defaults(func=cmd_tasks)

    p = sub.add_parser("accept", help="接取任务")
    p.add_argument("task_codes", nargs="+")
    p.set_defaults(func=cmd_accept)

    p = sub.add_parser("claim", help="领取已完成任务的奖励")
    p.add_argument("task_codes", nargs="+")
    p.set_defaults(func=cmd_claim)

    p = sub.add_parser("subscribe", help="探测公众号关注任务接口")
    p.set_defaults(func=cmd_subscribe)

    p = sub.add_parser("events", help="发送遥测事件")
    p.add_argument("--event", action="append", help="事件码，可重复；默认发送三类常用事件")
    p.add_argument("--id", default="test-skill", help="事件关联的 skill/template/expert 标识")
    p.add_argument("--machine-id", help="机器/用户 ID，默认取环境变量 WB_MACHINE_ID")
    p.add_argument("--url", help="上报地址，默认 https://<domain>/v2/report")
    p.add_argument("--dry-run", action="store_true", help="只打印请求体，不发送")
    p.set_defaults(func=cmd_events)

    p = sub.add_parser("acp", help="创建 ACP 会话并发送指令")
    p.add_argument("prompt", nargs="?", default="Hello! Respond with one word: OK")
    p.add_argument("--wait", type=int, default=120, help="等待回复的秒数")
    p.set_defaults(func=cmd_acp)

    return parser


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    if args.command == "events" and not args.event:
        args.event = list(DEFAULT_EVENTS)
    try:
        return args.func(args)
    except RuntimeError as exc:
        return _fail(str(exc))


if __name__ == "__main__":
    sys.exit(main())
