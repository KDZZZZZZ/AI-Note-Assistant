from pathlib import Path
from openai import OpenAI
import json
from tools import TOOLS, call_tool
from utils import export_md, safe_write, should_ignore_event, describe_patch
from db import init_db, build_full_context, get_all_rows
import os
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Request, WebSocket
from pathlib import Path
import asyncio

app = FastAPI()
load_dotenv()
api_key = os.getenv("API_KEY")
base_url = os.getenv("BASE_URL")

client = OpenAI(
    api_key=api_key,
    base_url=base_url
)
@app.post("/save_file")
async def save_file(file: UploadFile = File(...)):
    save_dir = Path("../my-app/public")
    save_dir.mkdir(parents=True, exist_ok=True)
    fixed_path = save_dir / "demo.pdf"          # 固定名
    with open(fixed_path, "wb") as f:
        f.write(await file.read())
    return {"filePath": str(fixed_path)}

@app.post("/import_md")
async def import_md(file: UploadFile = File(...)):
    save_path = Path("../my-app/public/note.md")
    content_bytes = await file.read()
    safe_write(save_path, content_bytes.decode('utf-8'))
    init_db() # Re-initialize database after import
    return {"status": "success"}

@app.post("/clear_md")
async def clear_md():
    file_path = Path("../my-app/public/note.md")
    safe_write(file_path, "")
    init_db()
    return {"status": "success"}

@app.post("/api/")
def init():
    global messages
    messages = []
    messages.append({
        "role": "system",
        "content": """
        你是 Markdown 笔记总结大师，能调用 insert_line / delete_line / update_line。
        如果用户没有提到要写入在笔记中，你要自主判断是否对笔记进行修改，你的任务是从文档和与用户的交互中提取信息，将有价值的精华记录在笔记当中。
        下面给出**完整 Markdown**（每行格式：`行号:hash:内容`），请根据用户指令**自主决定修改哪些行**，并返回 JSON Patch：

        [{"id":"行号","old_hash":"原摘要","new":"新内容"}]

        """
        })
    global client
    client = OpenAI(
    api_key=api_key,
    base_url=base_url
)
    init_db()

@app.post("/upload_files")
def upload_files():

    file_object = client.files.create(
        file=Path("../my-app/public/demo.pdf"),
        purpose="file-extract"
    )
    file_content = client.files.content(file_id=file_object.id).text
    messages.append({
        "role": "system",
        "content": file_content
    })
    print(messages)

@app.post("/chat")
async def chat(request: Request):
    raw_body = await request.body()
    question = raw_body.decode("utf-8")
    md_ctx = build_full_context()
    messages.append({"role": "user", "content": question})
    md_msg = {"role":"system","name":"markdown 笔记","content":md_ctx+" "}
    for i, m in enumerate(messages):
        if m.get("name") == "markdown 笔记":
            messages[i] = md_msg
            break
    else:
        messages.insert(0, md_msg)

    while True:
        resp = client.chat.completions.create(
            model="kimi-k2-0711-preview",
            messages=messages,
            tools=TOOLS,
            temperature=0
        )

        if resp.choices[0].finish_reason != "tool_calls":
            break

        # 1) 先把 assistant 消息原样追加
        messages.append(resp.choices[0].message.model_dump())

        # 2) 再追加每条工具结果
        for tc in resp.choices[0].message.tool_calls:
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tc.function.name,
                "content": call_tool(tc.function.name, json.loads(tc.function.arguments))
            })

    reply = resp.choices[0].message.content
    print("Kimi 回复：", reply)
    # After tool calls, the DB is the source of truth, so export it to MD file
    export_md()
    description = describe_patch(json.loads(reply)) if reply.startswith("[") else reply
    return {"status": "updated", "summary": description}
    #return {"status": "updated", "reply": reply}



def delete_file():
    try:
        file_list = client.files.list()
        for file in file_list.data:
            client.files.delete(file_id=file.id)
        print("所有云端文件已成功删除。")
        return True
    except Exception as e:
        print(f"删除文件时出错: {e}")
        return False

@app.post("/cleanup")
async def cleanup_files():
    if delete_file():
        return {"status": "success", "message": "云端文件清理成功。"}
    else:
        return {"status": "error", "message": "云端文件清理失败。"}



if __name__ == "__main__":
    import uvicorn
    # 自动调用初始化
    init()
    print("后端服务已初始化，正在启动...")
    # 启动FastAPI服务器
    uvicorn.run(app, host="0.0.0.0", port=8000)


