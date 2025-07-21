from db import insert_row, delete_row

# ---------- 工具定义（JSON Schema） ----------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "insert_line",
            "description": "在指定行之后插入新行",
            "parameters": {
                "type": "object",
                "properties": {
                    "after_id": {"type": "integer", "description": "在此行 id 之后插入"},
                    "content":  {"type": "string", "description": "要插入的 Markdown 行内容"}
                },
                "required": ["after_id", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_line",
            "description": "删除指定行 id",
            "parameters": {
                "type": "object",
                "properties": {
                    "row_id": {"type": "integer", "description": "要删除的行 id"}
                },
                "required": ["row_id"]
            }
        }
    }
]

# ---------- 工具执行器 ----------
def call_tool(name: str, kwargs: dict) -> str:
    if name == "insert_line":
        new_id = insert_row(kwargs["after_id"], kwargs["content"])
        return f"✅ 已插入，新行 id = {new_id}"
    if name == "delete_line":
        delete_row(kwargs["row_id"])
        return f"✅ 已删除行 {kwargs['row_id']}"
    return "❌ 未知工具"