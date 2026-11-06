#!/usr/bin/env python3
"""Personal Database 命令行工具（只用 Python 标准库，无需安装依赖）

用法:
  ./pdb init    ~/my-data                      # 新建一个数据仓库
  ./pdb import-md raw/feishu/书稿 --source book # Markdown 转成记录
  ./pdb rebuild                                 # 从 records 重建索引
  ./pdb search  "定价"                          # 全文搜索
  ./pdb export  "定价" > context.md             # 导出上下文包，可粘贴给任何大模型
  ./pdb stats                                   # 统计

数据仓库位置：--data 参数 > 环境变量 PDB_DATA > ~/my-data
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = ENGINE_DIR / "templates" / "my-data"
SCHEMA_VERSION = "0.1"


# ---------- 基础 ----------

def data_dir(arg=None) -> Path:
    p = arg or os.environ.get("PDB_DATA") or "~/my-data"
    return Path(p).expanduser().resolve()


def now_iso() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def make_id(source: str, ref: str, content: str) -> str:
    return hashlib.sha256(f"{source}\n{ref}\n{content}".encode("utf-8")).hexdigest()[:16]


def iter_records(root: Path):
    rec_dir = root / "records"
    if not rec_dir.exists():
        return
    for f in sorted(rec_dir.rglob("*.jsonl")):
        with f.open(encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    print(f"⚠️  跳过损坏的行：{f}:{line_no}", file=sys.stderr)


# ---------- init ----------

def cmd_init(args):
    target = Path(args.path).expanduser().resolve()
    if target.exists() and any(target.iterdir()):
        sys.exit(f"❌ {target} 已存在且不为空，为了安全不覆盖。")
    shutil.copytree(TEMPLATE_DIR, target, dirs_exist_ok=True)
    print(f"✅ 已创建数据仓库：{target}")
    print("下一步：cd 进去，运行 git init，然后把飞书导出的文件放进 raw/feishu/")


# ---------- import-md ----------

DATE_PATTERNS = [
    re.compile(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?(?:\s+(\d{1,2}):(\d{2}))?"),
]


def find_date(*texts):
    for t in texts:
        if not t:
            continue
        for pat in DATE_PATTERNS:
            m = pat.search(t)
            if m:
                y, mo, d, hh, mm = m.groups()
                try:
                    return dt.datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0)).isoformat()
                except ValueError:
                    continue
    return None


HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def split_markdown(text: str, level: int):
    """按标题切块。level=2 表示在 #、## 处切开，更深的标题留在正文里。
    返回 [(标题路径, 最近一级标题, 正文)]"""
    chunks, stack, buf = [], [], []   # stack: [(深度, 标题)]

    def flush():
        body = "\n".join(buf).strip()
        if body:
            chunks.append((" / ".join(t for _, t in stack), stack[-1][1] if stack else "", body))
        buf.clear()

    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else HEADING.match(line)
        if m and len(m.group(1)) <= level:
            flush()
            depth = len(m.group(1))
            while stack and stack[-1][0] >= depth:
                stack.pop()
            stack.append((depth, m.group(2)))
        else:
            buf.append(line)
    flush()
    return chunks


IMG = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")


def cmd_import_md(args):
    root = data_dir(args.data)
    src = Path(args.path).expanduser()
    if not src.is_absolute():
        src = (root / src) if (root / src).exists() else src.resolve()
    if not src.exists():
        sys.exit(f"❌ 找不到 {src}")
    try:
        src.resolve().relative_to(root / "raw")
    except ValueError:
        sys.exit(f"❌ 只能从 {root/'raw'} 里导入。请先把文件放进 raw/，保证原文有存档。")

    files = [src] if src.is_file() else sorted(src.rglob("*.md"))
    existing = {r["id"] for r in iter_records(root)}
    out_dir = root / "records" / args.source
    out_dir.mkdir(parents=True, exist_ok=True)

    added = skipped = 0
    buckets = {}
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        rel = f.resolve().relative_to(root).as_posix()
        file_date = find_date(f.stem)
        chunks = [(f.stem, f.stem, text.strip())] if args.split == "file" else split_markdown(text, args.level)
        for title, leaf, body in chunks:
            if len(body) < args.min_chars:
                continue
            full_title = f"{f.stem} / {title}" if title and title != f.stem else f.stem
            ref = f"{rel}#{title}" if title else rel
            rid = make_id(args.source, ref, body)
            if rid in existing:
                skipped += 1
                continue
            created = find_date(leaf, body[:80]) or file_date
            rec = {
                "id": rid, "source": args.source, "type": args.type,
                "created_at": created, "author": args.author,
                "title": full_title, "content": body, "ref": ref,
                "media": IMG.findall(body), "tags": [], "imported_at": now_iso(),
            }
            year = (created or "")[:4] or "undated"
            buckets.setdefault(year, []).append(rec)
            existing.add(rid)
            added += 1

    for year, recs in buckets.items():
        with (out_dir / f"{year}.jsonl").open("a", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"✅ 导入完成：新增 {added} 条，跳过重复 {skipped} 条（共扫描 {len(files)} 个文件）")
    if added:
        print("下一步：./pdb rebuild")


# ---------- rebuild ----------

def cmd_rebuild(args):
    root = data_dir(args.data)
    db_path = root / "index.db"
    tmp = root / "index.db.tmp"
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    con.executescript(
        """
        CREATE TABLE records(
          id TEXT PRIMARY KEY, source TEXT, type TEXT, created_at TEXT,
          author TEXT, title TEXT, content TEXT, ref TEXT, media TEXT, tags TEXT);
        CREATE VIRTUAL TABLE records_fts USING fts5(
          title, content, content='records', content_rowid='rowid', tokenize='trigram');
        CREATE TABLE knowledge(path TEXT PRIMARY KEY, content TEXT);
        CREATE VIRTUAL TABLE knowledge_fts USING fts5(
          path, content, content='knowledge', content_rowid='rowid', tokenize='trigram');
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
        """
    )
    n = 0
    for r in iter_records(root):
        con.execute(
            "INSERT OR IGNORE INTO records VALUES(?,?,?,?,?,?,?,?,?,?)",
            (r["id"], r.get("source"), r.get("type"), r.get("created_at"), r.get("author"),
             r.get("title"), r.get("content"), r.get("ref"),
             json.dumps(r.get("media", []), ensure_ascii=False),
             json.dumps(r.get("tags", []), ensure_ascii=False)),
        )
        n += 1
    k = 0
    kdir = root / "knowledge"
    if kdir.exists():
        for f in sorted(kdir.rglob("*.md")):
            con.execute("INSERT INTO knowledge VALUES(?,?)",
                        (f.relative_to(root).as_posix(), f.read_text(encoding="utf-8", errors="replace")))
            k += 1
    con.execute("INSERT INTO records_fts(records_fts) VALUES('rebuild')")
    con.execute("INSERT INTO knowledge_fts(knowledge_fts) VALUES('rebuild')")
    con.execute("INSERT INTO meta VALUES('schema_version', ?)", (SCHEMA_VERSION,))
    con.execute("INSERT INTO meta VALUES('built_at', ?)", (now_iso(),))
    con.commit()
    con.close()
    os.replace(tmp, db_path)
    print(f"✅ 索引已重建：{n} 条记录，{k} 个知识文件 → {db_path}")


# ---------- search ----------

def open_db(root: Path):
    db = root / "index.db"
    if not db.exists():
        sys.exit("❌ 还没有索引，请先运行：./pdb rebuild")
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    return con


def search(root: Path, query: str, limit=10, source=None, year=None):
    """返回 [dict]。3 个字及以上走全文索引；更短的词用 LIKE 兜底（中文常见两字词）。"""
    con = open_db(root)
    terms = [t for t in query.split() if t]
    where, params = [], []
    if source:
        where.append("r.source = ?"); params.append(source)
    if year:
        where.append("r.created_at LIKE ?"); params.append(f"{year}%")
    long_terms = [t for t in terms if len(t) >= 3]
    short_terms = [t for t in terms if len(t) < 3]
    for t in short_terms:
        where.append("(r.title LIKE ? OR r.content LIKE ?)"); params += [f"%{t}%", f"%{t}%"]
    if long_terms:
        fts_q = " AND ".join('"' + t.replace('"', '""') + '"' for t in long_terms)
        sql = ("SELECT r.*, snippet(records_fts, 1, '【', '】', '…', 30) AS snip "
               "FROM records_fts JOIN records r ON r.rowid = records_fts.rowid "
               "WHERE records_fts MATCH ?" + "".join(f" AND {w}" for w in where) +
               " ORDER BY rank LIMIT ?")
        rows = con.execute(sql, [fts_q] + params + [limit]).fetchall()
    else:
        sql = ("SELECT r.*, substr(r.content, 1, 120) AS snip FROM records r" +
               (" WHERE " + " AND ".join(where) if where else "") +
               " ORDER BY r.created_at DESC LIMIT ?")
        rows = con.execute(sql, params + [limit]).fetchall()
    con.close()
    return [dict(r) for r in rows]


def cmd_search(args):
    root = data_dir(args.data)
    rows = search(root, args.query, args.limit, args.source, args.year)
    if not rows:
        print("（没有找到）")
        return
    for r in rows:
        when = (r["created_at"] or "无日期")[:10]
        print(f"■ [{r['source']}] {when}  {r['title']}")
        print(f"  {r['snip'].replace(chr(10), ' ')}")
        print(f"  ↳ {r['ref']}  (id: {r['id']})\n")


# ---------- export ----------

def build_context(root: Path, query: str, limit=15) -> str:
    out = [f"# 个人上下文包\n\n> 查询：{query}　生成时间：{now_iso()}\n"
           "> 以下内容来自我的个人数据库。回答时请优先依据这些资料，并引用 id。\n"]
    me = root / "knowledge" / "me"
    if me.exists():
        for f in sorted(me.glob("*.md")):
            out.append(f"\n## 关于我：{f.stem}\n\n{f.read_text(encoding='utf-8').strip()}\n")
    out.append("\n## 相关原始记录\n")
    for r in search(root, query, limit):
        out.append(f"\n### {r['title']}（{(r['created_at'] or '无日期')[:10]}，id: {r['id']}）\n\n"
                   f"{r['content'].strip()}\n")
    return "".join(out)


def cmd_export(args):
    print(build_context(data_dir(args.data), args.query, args.limit))


# ---------- stats ----------

def cmd_stats(args):
    root = data_dir(args.data)
    by = {}
    for r in iter_records(root):
        key = (r.get("source"), (r.get("created_at") or "")[:4] or "无日期")
        by[key] = by.get(key, 0) + 1
    if not by:
        print("（还没有记录）")
        return
    total = 0
    for (s, y), c in sorted(by.items()):
        print(f"{s:20s} {y:8s} {c:6d}")
        total += c
    print(f"{'合计':18s} {'':8s} {total:6d}")


# ---------- main ----------

def main():
    p = argparse.ArgumentParser(description="Personal Database 命令行工具")
    p.add_argument("--data", help="数据仓库路径（默认 $PDB_DATA 或 ~/my-data）")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="新建数据仓库"); s.add_argument("path"); s.set_defaults(fn=cmd_init)

    s = sub.add_parser("import-md", help="把 raw/ 里的 Markdown 转成记录")
    s.add_argument("path", help="raw/ 下的文件或文件夹")
    s.add_argument("--source", required=True, help="来源名，如 book、wechat_moments")
    s.add_argument("--type", default="section")
    s.add_argument("--author", default="me")
    s.add_argument("--split", choices=["heading", "file"], default="heading")
    s.add_argument("--level", type=int, default=2, help="按几级标题切块（默认 2）")
    s.add_argument("--min-chars", type=int, default=10)
    s.set_defaults(fn=cmd_import_md)

    s = sub.add_parser("rebuild", help="从 records 和 knowledge 重建索引"); s.set_defaults(fn=cmd_rebuild)

    s = sub.add_parser("search", help="全文搜索")
    s.add_argument("query"); s.add_argument("--limit", type=int, default=10)
    s.add_argument("--source"); s.add_argument("--year")
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser("export", help="导出上下文包（给任何大模型）")
    s.add_argument("query"); s.add_argument("--limit", type=int, default=15)
    s.set_defaults(fn=cmd_export)

    s = sub.add_parser("stats", help="按来源和年份统计"); s.set_defaults(fn=cmd_stats)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
