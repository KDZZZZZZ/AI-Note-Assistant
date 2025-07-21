import sqlite3, hashlib, os
from pathlib import Path
DB_FILE = "lines.db"

# ---------- 建表 & 初始化 ----------
def init_db(md_path: str = "../my-app/public/note.md") -> None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DROP TABLE IF EXISTS lines")
        conn.execute("""
            CREATE TABLE lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT,
                content TEXT
            )
        """)
        with open(md_path, encoding="utf-8") as f:
            for line in f:
                content = line.rstrip("\n")
                h = hashlib.sha1(content.encode()).hexdigest()[:8]
                conn.execute("INSERT INTO lines(hash, content) VALUES(?, ?)", (h, content))
        conn.commit()
def build_full_context() -> str:
    lines = [f"{i+1}:{sha8(ln)}:{ln.rstrip()}"
             for i, ln in enumerate(Path("../my-app/public/note.md").read_text(encoding="utf-8").splitlines())]
    return "\n".join(lines)

def sha8(s: str) -> str:
    import hashlib
    return hashlib.sha1(s.encode()).hexdigest()[:8]
# ---------- 基本 CRUD ----------
def insert_row(after_id: int, content: str) -> int:
    """在 after_id 之后插入新行，返回新行 id"""
    with sqlite3.connect(DB_FILE) as conn:
        # To avoid "UNIQUE constraint failed" errors, we need to update IDs from largest to smallest.
        # SQLite's UPDATE doesn't directly support ORDER BY, so we select the IDs first.
        ids_to_update = conn.execute("SELECT id FROM lines WHERE id > ? ORDER BY id DESC", (after_id,)).fetchall()
        for (row_id,) in ids_to_update:
            conn.execute("UPDATE lines SET id = id + 1 WHERE id = ?", (row_id,))

        new_id = after_id + 1
        h = hashlib.sha1(content.encode()).hexdigest()[:8]
        conn.execute("INSERT INTO lines(id, hash, content) VALUES(?, ?, ?)",
                     (new_id, h, content))
        conn.commit()
    return new_id

def delete_row(row_id: int) -> None:
    """删除指定 id，随后把 id 连续化"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM lines WHERE id = ?", (row_id,))
        conn.execute("UPDATE lines SET id = id - 1 WHERE id > ?", (row_id,))
        conn.commit()

def get_all_rows() -> list[tuple[int, str]]:
    """返回 [(id, content), ...]"""
    with sqlite3.connect(DB_FILE) as conn:
        return conn.execute("SELECT id, content FROM lines ORDER BY id").fetchall()