# personal-db

一个属于你自己的 Personal Database：**本地优先、不绑定任何模型、可以随身迁移**。

把你的书稿、朋友圈、聊天、笔记沉淀成统一格式的数据，让 Claude、Codex、Cursor、ChatGPT、DeepSeek 等任何大模型都能读懂你、调用你的经验。

## 设计原则

- **数据就是文件**：原文、记录、理解全部是 Markdown / JSONL，用 git 管理。换电脑 `git clone` 即可。
- **索引可丢弃**：SQLite 索引由文件生成，删掉随时 `pdb rebuild`。
- **结论必须有出处**：理解层的每条结论都指回原始记录，可核查、可纠正。
- **引擎与数据分离**：本仓库（引擎）开源；你的数据放在另一个私有仓库，永不公开。
- **零依赖**：只需要 Python 3.9+（Mac 自带），中文全文检索开箱即用。

## 结构

```
personal-db/          ← 本仓库（开源）
├── SCHEMA.md         数据规范
├── pdb               命令行入口
├── pdbcli.py         导入 / 重建索引 / 搜索 / 导出
├── mcp_server.py     MCP 服务，供各类 Agent 调用
└── templates/my-data 数据仓库模板

my-data/              ← 你的数据（私有，绝不公开）
├── raw/              原始资料，只增不改
├── records/          统一格式记录（JSONL）
├── knowledge/        理解层：me / people / projects / playbooks / timeline
└── index.db          搜索索引（不进 git）
```

## 快速开始

```bash
./pdb init ~/my-data                       # 新建数据仓库
export PDB_DATA=~/my-data                  # 告诉引擎数据在哪
# 把 Markdown 放进 ~/my-data/raw/ 之后：
./pdb import-md raw/feishu/书稿 --source book
./pdb rebuild
./pdb search "定价"
./pdb export "定价" > context.md           # 粘贴给任何网页版大模型
```

## 接入 Agent（MCP）

```bash
claude mcp add personal-db -e PDB_DATA=$HOME/my-data -- python3 /完整路径/personal-db/mcp_server.py
```

提供的工具：`search_records`、`get_record`、`list_knowledge`、`read_knowledge`、`get_context`。

## 路线图

- [x] 数据规范 v0.1、Markdown 导入、中文全文检索、上下文导出、MCP 服务
- [ ] 飞书转换器（lark-cli 增量同步）
- [ ] 朋友圈专用转换器（按日期拆分动态）
- [ ] 向量检索（可选，本地 embedding）
- [ ] 屏幕采集接入（screenpipe 作为数据源）

## 许可

MIT
