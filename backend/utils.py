import time
import threading
from pathlib import Path
from db import get_all_rows

WRITE_LOCK = threading.Lock()
LAST_WRITE_TIME = 0.0
WRITE_DELAY = 0.3  # 300 ms

def safe_write(path: Path, content: str) -> None:
    """
    原子写文件，并记录时间戳。
    300 ms 内 watchdog 会忽略该文件修改事件。
    """
    global LAST_WRITE_TIME
    with WRITE_LOCK:
        path.write_text(content, encoding="utf-8", newline="\n")
        LAST_WRITE_TIME = time.time()

def should_ignore_event() -> bool:
    """
    watchdog 事件过滤函数：300 ms 内返回 True
    """
    return time.time() - LAST_WRITE_TIME < WRITE_DELAY

def export_md(path: str = "../my-app/public/note.md") -> None:
    """把数据库写回 Markdown"""
    rows = get_all_rows()
    content = "\n".join([row[1] for row in rows])
    safe_write(Path(path), content)

def describe_patch(patch: list) -> str:
    """把 JSON patch 翻译成一句中文"""
    if not patch:
        return "没有需要修改的地方。"
    actions = []
    for p in patch:
        id = p["id"]
        if p.get("new") == "":
            actions.append(f"删除了第 {id} 行")
        else:
            actions.append(f"把第 {id} 行改为「{p['new']}」")
    return "；".join(actions) + "。"