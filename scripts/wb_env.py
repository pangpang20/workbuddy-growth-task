# -*- coding: utf-8 -*-
"""WorkBuddy 环境探测：动态定位依赖模块、读取登录态、调用接口。

不写死任何用户路径，全部按环境变量 + 候选目录探测。可覆盖的变量：
  WB_BUDDY_STATION_DIR  buddy_station.py 所在目录
  WB_LIBRARY_DIR        WorkBuddy 内置 skill library 目录（含 workbuddy_ipc）
  WB_CONFIG_DIR         WorkBuddy 配置根目录，默认 ~/.workbuddy
"""

import glob
import os
import sys

_HOME = os.path.expanduser("~")
_LIB_REL = os.path.join(
    "resources", "app.asar.unpacked", "resources", "plugins",
    "workbuddy-builtin", "skills", "library",
)


def config_dir():
    return os.environ.get("WB_CONFIG_DIR") or os.path.join(_HOME, ".workbuddy")


def _station_dirs():
    env = os.environ.get("WB_BUDDY_STATION_DIR")
    if env:
        yield env
    yield os.path.dirname(os.path.abspath(__file__))
    for hit in glob.glob(os.path.join(config_dir(), "skills", "*", "scripts", "buddy_station.py")):
        yield os.path.dirname(hit)


def find_station_dir():
    for d in _station_dirs():
        if os.path.isfile(os.path.join(d, "buddy_station.py")):
            return d
    raise RuntimeError(
        "未找到 buddy_station.py。请安装包含该模块的技能，"
        "或用环境变量 WB_BUDDY_STATION_DIR 指向其 scripts 目录。"
    )


def _library_dirs():
    env = os.environ.get("WB_LIBRARY_DIR")
    if env:
        yield env
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        root = os.environ.get(key)
        if not root:
            continue
        for app in ("WorkBuddy", "CodeBuddy CN"):
            yield os.path.join(root, app, _LIB_REL)
            yield os.path.join(root, "Programs", app, _LIB_REL)


def find_library_dir():
    for d in _library_dirs():
        if os.path.isdir(os.path.join(d, "workbuddy_ipc")):
            return d
    raise RuntimeError(
        "未找到 WorkBuddy 内置 skill library（workbuddy_ipc）。"
        "请确认 WorkBuddy 桌面版已安装，或用 WB_LIBRARY_DIR 指定该目录。"
    )


def _import(module_name, finder):
    try:
        return __import__(module_name)
    except ImportError:
        pass
    directory = finder()
    if directory not in sys.path:
        sys.path.insert(0, directory)
    return __import__(module_name)


def load_station():
    """返回 buddy_station 模块。"""
    return _import("buddy_station", find_station_dir)


def load_ipc():
    """返回 workbuddy_ipc 模块（需要 WorkBuddy 客户端在运行）。"""
    return _import("workbuddy_ipc", find_library_dir)


def credentials():
    """返回 (buddy_station, token, domain, auth_path)。未登录时抛 RuntimeError。"""
    bs = load_station()
    path = bs.find_login_state()
    if not path:
        raise RuntimeError("未找到 WorkBuddy 登录态，请先在 WorkBuddy 客户端登录。")
    token, domain = bs.load_credentials(path)
    return bs, token, domain, path


def api(path, method="GET", payload=None):
    """调用 WorkBuddy 开放接口，返回 (status, body)。"""
    bs, token, domain, _ = credentials()
    return bs.api_call(domain, token, path, method=method, payload=payload)
