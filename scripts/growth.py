# -*- coding: utf-8 -*-
"""WorkBuddy 成长中心 CLI。

用法示例：
  python scripts/growth.py tasks --all
  python scripts/growth.py accept Library_read
  python scripts/growth.py claim Library_read
  python scripts/growth.py claim-all
  python scripts/growth.py auto-check --wait 15
  python scripts/growth.py events --event skill_installed --id my-skill --dry-run
  python scripts/growth.py acp "你好，回复 OK" --wait 60
  python scripts/growth.py acp --expert lighthouse "请介绍你的专长"
  python scripts/growth.py batch-acp --expert douyinyin -p "prompt1" -p "prompt2" -p "prompt3"
  python scripts/growth.py batch-acp -f prompts.txt
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
import ssl as _ssl
from urllib.parse import urlparse

from wb_env import api, credentials, load_ipc

TASKS_PATH = "/v2/activity/growth/tasks"
DEFAULT_EVENTS = ("skill_installed", "template_used", "expert_summoned")


def _print_json(value):
    print(json.dumps(value, ensure_ascii=False))


def _fail(message):
    sys.stderr.write(message + "\n")
    return 1


# --- 任务查询 / 领取 / 批量 claim -----------------------------------------

def _query_tasks(timeout=10):
    """返回 list[dict]，每个 dict 是 task 原样。"""
    st, body = api(TASKS_PATH, "GET")
    if st != 200 or not isinstance(body, dict) or body.get("code") != 0:
        raise RuntimeError("查询任务失败 status=%s body=%s" % (st, body))
    return body.get("data", {}).get("tasks", [])


def _claim_task(code):
    st, body = api("%s/%s/claim" % (TASKS_PATH, code), "POST", {})
    return st, body


def cmd_tasks(args):
    try:
        tasks = _query_tasks()
    except RuntimeError as exc:
        return _fail(str(exc))
    for t in tasks:
        code = t.get("task_code")
        status = t.get("accept_status")
        progress = t.get("progress", {})
        if isinstance(progress, dict):
            current = progress.get("current", 0)
            target = progress.get("target", 1)
        else:
            current, target = 0, 1
        if not args.all and status == "claimed":
            continue
        if args.verbose:
            print(f"{code}\t{status}\t{current}/{target}\t{json.dumps(progress, ensure_ascii=False)}")
        else:
            print(f"{code}\t{status}\t{current}/{target}")
    return 0


def cmd_accept(args):
    st, body = api(TASKS_PATH + "/accept", "POST", {"task_codes": args.task_codes})
    _print_json(body)
    return 0 if st == 200 else 1


def cmd_claim(args):
    code = 0
    for tc in args.task_codes:
        st, body = _claim_task(tc)
        print(f"{tc}\t{st}\t{json.dumps(body, ensure_ascii=False)[:200]}")
        if st != 200:
            code = 1
    return code


def cmd_claim_all(args):
    """自动查询所有 current>=target 且未 claimed 的任务，逐个领取。"""
    try:
        tasks = _query_tasks()
    except RuntimeError as exc:
        return _fail(str(exc))
    claimed = 0
    for t in tasks:
        code = t.get("task_code")
        status = t.get("accept_status")
        progress = t.get("progress", {})
        current = progress.get("current", 0) if isinstance(progress, dict) else 0
        target = progress.get("target", 1) if isinstance(progress, dict) else 1
        if status == "claimed" or current < target:
            continue
        st, body = _claim_task(code)
        ok = st == 200
        claimed += 1 if ok else 0
        mark = "✅" if ok else "❌"
        print(f"{mark} {code}\t{st}\t{json.dumps(body, ensure_ascii=False)[:150]}")
    if claimed == 0:
        print("(没有需要领取的任务)")
    print(f"总计领取：{claimed}")
    return 0


def cmd_auto_check(args):
    """N 秒后查询全部任务，然后对已完成的批量 claim。"""
    print(f"等待 {args.wait} 秒让服务端处理遥测...")
    sys.stdout.flush()
    time.sleep(args.wait)
    print("\n=== 当前任务状态 ===")
    cmd_tasks(argparse.Namespace(all=True, verbose=False))
    print()
    return cmd_claim_all(argparse.Namespace())


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


# --- ACP 会话（抽成内部函数 + 命令） -------------------------------------

def _run_acp_once(prompt, expert_id=None, wait=120, verbose=False):
    """跑一次 ACP 会话，返回 (conv_id, message_text_or_none)。"""
    wb = load_ipc()
    with wb.connect(client_id="codex-agent", client_kind="skill") as client:
        pipe = client.get_pipe("wb.request")

        def _ipc_call(method, path, body=None):
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

        payload = {"conversationOrigin": "agents", "exclusive": False}
        if expert_id:
            payload["expertId"] = expert_id

        _, conv = _ipc_call("POST", "/v2/as/conversations/", payload)
        if not isinstance(conv, dict) or not conv.get("data"):
            raise RuntimeError("创建会话失败: %s" % conv)
        conv_id = conv["data"]["id"]
        session = conv["data"]["session"]
        acp_url, token = session["link"], session["token"]

        _, sess = _ipc_call("POST", "/v2/as/conversations/%s/session" % conv_id, {})
        session_id = sess.get("data", {}).get("sessionId", "")
        conn_id = str(uuid.uuid4())

        if verbose:
            print("conv=%s" % conv_id)
            sys.stdout.flush()

        parsed = urlparse(acp_url)
        sse_conn = http.client.HTTPSConnection(parsed.hostname, 443, timeout=300, context=_ssl.create_default_context())
        sse_headers = {
            "Authorization": "Bearer " + token,
            "Accept": "text/event-stream",
            "acp-connection-id": conn_id,
            "X-Conversation-ID": conv_id,
            "x-codebuddy-request": "1",
            "Cache-Control": "no-cache",
        }
        sse_conn.request("GET", parsed.path, headers=sse_headers)
        sse_resp = sse_conn.getresponse()
        if verbose:
            print("sse_status=%s" % sse_resp.status)
            sys.stdout.flush()

        chunks = []
        done = threading.Event()

        def read_sse():
            buf = []
            try:
                while True:
                    raw = sse_resp.readline()
                    if not raw:
                        break
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    if line == "":
                        etext = "\n".join(buf); buf = []
                        if not etext:
                            continue
                        if etext.startswith(":") and "heartbeat" in etext:
                            continue
                        dl = ""
                        for ln in etext.splitlines():
                            if ln.startswith("data:"):
                                dl = ln[len("data:"):].lstrip(); break
                        if not dl:
                            continue
                        try:
                            payload = json.loads(dl)
                        except ValueError:
                            continue
                        params = payload.get("params", {}) or {}
                        su = params.get("sessionUpdate") or (params.get("update") or {}).get("sessionUpdate", "")
                        if su == "agent_message_chunk":
                            content = params.get("content") or (params.get("update") or {}).get("content") or {}
                            text = content.get("text", "") if isinstance(content, dict) else ""
                            if text:
                                chunks.append(text)
                        if su in ("agent_message_end", "tool_result_end", "completed"):
                            done.set()
                    else:
                        buf.append(line)
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=read_sse, daemon=True).start()
        time.sleep(2)

        prompt_body = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "session/prompt",
            "params": {"sessionId": session_id, "prompt": [{"type": "text", "text": prompt}]},
        }).encode()
        req = urllib.request.Request(acp_url, data=prompt_body, method="POST")
        req.add_header("Authorization", "Bearer " + token)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        req.add_header("acp-connection-id", conn_id)
        req.add_header("X-Conversation-ID", conv_id)
        req.add_header("x-codebuddy-request", "1")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                prompt_status = resp.status
        except Exception as exc:  # noqa: BLE001
            prompt_status = getattr(exc, "code", "ERR")

        deadline = time.time() + wait
        while time.time() < deadline and not done.is_set():
            time.sleep(2)

        if verbose:
            print("prompt_status=%s" % prompt_status)
        try:
            sse_conn.close()
        except Exception:  # noqa: BLE001
            pass
        return conv_id, "".join(chunks)


def cmd_acp(args):
    expert_id = args.expert
    conv_id, msg = _run_acp_once(args.prompt, expert_id=expert_id, wait=args.wait, verbose=True)
    tag = expert_id or "(default)"
    print(f"--- ACP expert={tag} conv={conv_id} ---")
    print("MESSAGE:", msg[:2000] if msg else "(无回复)")
    return 0


def cmd_batch_acp(args):
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            prompts = [ln.strip() for ln in f if ln.strip()]
    else:
        prompts = args.prompts or [args.prompt]
    if not prompts:
        return _fail("batch-acp 至少需要一个 prompt（-p 或 -f）")

    expert_id = args.expert
    tag = expert_id or "(default)"
    total = len(prompts)
    ok = 0
    for idx, prompt in enumerate(prompts, 1):
        print(f"\n=== [{idx}/{total}] expert={tag} prompt={prompt[:50]} ===")
        sys.stdout.flush()
        try:
            conv_id, msg = _run_acp_once(prompt, expert_id=expert_id, wait=args.wait, verbose=args.verbose)
            ok += 1
            snippet = (msg[:120] + "...") if len(msg) > 120 else msg
            print(f"conv={conv_id} | {snippet}")
        except Exception as exc:  # noqa: BLE001
            print(f"失败: {exc}")
        sys.stdout.flush()
        if args.sleep and idx < total:
            time.sleep(args.sleep)
    print(f"\n=== 完成：{ok}/{total} 成功 ===")
    return 0 if ok == total else 1


# --- 入口 -----------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(prog="growth", description="WorkBuddy 成长中心任务工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("tasks", help="查询任务与进度")
    p.add_argument("--all", action="store_true", help="包含已领取的任务")
    p.add_argument("--verbose", "-v", action="store_true", help="附带完整 progress JSON")
    p.set_defaults(func=cmd_tasks)

    p = sub.add_parser("accept", help="接取任务")
    p.add_argument("task_codes", nargs="+")
    p.set_defaults(func=cmd_accept)

    p = sub.add_parser("claim", help="领取已完成任务的奖励")
    p.add_argument("task_codes", nargs="+")
    p.set_defaults(func=cmd_claim)

    p = sub.add_parser("claim-all", help="自动查询并领取全部已完成未领的任务")
    p.set_defaults(func=cmd_claim_all)

    p = sub.add_parser("auto-check", help="等待 N 秒让服务端处理遥测，再自动 claim")
    p.add_argument("--wait", type=int, default=15, help="等待秒数")
    p.set_defaults(func=cmd_auto_check)

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
    p.add_argument("--expert", "-e", help="绑定的 expertId（服务端可能会走专家路由）")
    p.add_argument("--wait", type=int, default=120, help="等待回复的秒数")
    p.set_defaults(func=cmd_acp)

    p = sub.add_parser("batch-acp", help="批量跑 ACP 会话")
    p.add_argument("prompt", nargs="?", help="单个 prompt（与 -p 二选一）")
    p.add_argument("-p", "--prompt", action="append", dest="prompts", help="prompt 列表，可多次传")
    p.add_argument("-f", "--file", help="从文本文件逐行读 prompt")
    p.add_argument("--expert", "-e", help="绑定的 expertId")
    p.add_argument("--wait", type=int, default=60, help="每个会话等待秒数")
    p.add_argument("--sleep", type=int, default=0, help="会话间等待秒数")
    p.add_argument("--verbose", "-v", action="store_true")
    p.set_defaults(func=cmd_batch_acp)

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
