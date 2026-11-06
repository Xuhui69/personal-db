#!/usr/bin/env python3
"""Personal Database 的 MCP 服务（stdio，纯标准库）。
任何支持 MCP 的客户端（Claude Desktop、Claude Code、Codex、Cursor……）都能接入。

Claude Code 接入示例：
  claude mcp add personal-db -e PDB_DATA=/path/to/my-data -- python3 /path/to/personal-db/mcp_server.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pdbcli as core  # noqa: E402

ROOT = core.data_dir()

TOOLS = [
    {
        "name": "search_records",
        "description": "在个人数据库的原始记录（书稿、朋友圈、聊天等）中全文搜索。多个关键词用空格分隔。",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string"},
            "source": {"type": "string", "description": "可选：book、wechat_moments 等"},
            "year": {"type": "string", "description": "可选：例如 2021"},
            "limit": {"type": "integer", "default": 10}}, "required": ["query"]},
    },
    {
        "name": "get_record",
        "description": "按 id 获取一条完整记录（含原文和出处）。",
        "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
    },
    {
        "name": "list_knowledge",
        "description": "列出理解层的所有文件（关于我、人物、项目、工作流 Playbook、时间线）。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_knowledge",
        "description": "读取理解层的一个文件，path 如 knowledge/me/profile.md。",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "get_context",
        "description": "围绕一个主题，打包'关于我'和最相关的原始记录，作为完成任务前的背景资料。",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string"}, "limit": {"type": "integer", "default": 15}}, "required": ["query"]},
    },
]


def call_tool(name, a):
    if name == "search_records":
        rows = core.search(ROOT, a["query"], a.get("limit", 10), a.get("source"), a.get("year"))
        return "\n\n".join(
            f"[{r['id']}] {r['source']} {(r['created_at'] or '无日期')[:10]} {r['title']}\n{r['snip']}\n↳ {r['ref']}"
            for r in rows) or "（没有找到）"
    if name == "get_record":
        con = core.open_db(ROOT)
        row = con.execute("SELECT * FROM records WHERE id = ?", (a["id"],)).fetchone()
        con.close()
        return json.dumps(dict(row), ensure_ascii=False, indent=2) if row else "（没有这条记录）"
    if name == "list_knowledge":
        kdir = ROOT / "knowledge"
        files = sorted(f.relative_to(ROOT).as_posix() for f in kdir.rglob("*.md")) if kdir.exists() else []
        return "\n".join(files) or "（理解层还是空的）"
    if name == "read_knowledge":
        p = (ROOT / a["path"]).resolve()
        if not p.is_relative_to((ROOT / "knowledge").resolve()) or not p.exists():
            return "（只能读取 knowledge/ 下存在的文件）"
        return p.read_text(encoding="utf-8")
    if name == "get_context":
        return core.build_context(ROOT, a["query"], a.get("limit", 15))
    raise ValueError(f"未知工具：{name}")


def reply(msg_id, result=None, error=None):
    out = {"jsonrpc": "2.0", "id": msg_id}
    if error:
        out["error"] = error
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        method, mid = msg.get("method"), msg.get("id")
        if mid is None:  # 通知，不需要回复
            continue
        try:
            if method == "initialize":
                reply(mid, {"protocolVersion": msg.get("params", {}).get("protocolVersion", "2025-06-18"),
                            "capabilities": {"tools": {}},
                            "serverInfo": {"name": "personal-db", "version": core.SCHEMA_VERSION}})
            elif method == "tools/list":
                reply(mid, {"tools": TOOLS})
            elif method == "tools/call":
                p = msg["params"]
                try:
                    text = call_tool(p["name"], p.get("arguments") or {})
                    reply(mid, {"content": [{"type": "text", "text": text}]})
                except SystemExit as e:
                    reply(mid, {"content": [{"type": "text", "text": str(e)}], "isError": True})
            elif method == "ping":
                reply(mid, {})
            else:
                reply(mid, error={"code": -32601, "message": f"Method not found: {method}"})
        except Exception as e:  # noqa: BLE001
            reply(mid, error={"code": -32603, "message": str(e)})


if __name__ == "__main__":
    main()
