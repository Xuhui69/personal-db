# 我的个人数据库（Personal Database）

这是我的私人数据仓库。数据格式见引擎仓库的 `SCHEMA.md`。
引擎（命令行工具）在旁边的 `../personal-db/`，命令写作 `../personal-db/pdb`。

## 三层结构
- `raw/`：原始资料，**只增不改**。绝对不要编辑、覆盖或删除这里的文件。
- `records/`：统一格式的 JSONL，由 `pdb import-md` 生成，**不要手工编辑**。
- `knowledge/`：理解层 Markdown（me / people / projects / playbooks / timeline），由你整理、由我审核。
- `index.db`：搜索索引，可随时用 `../personal-db/pdb rebuild` 重建，不进 git。

## 工作规则
1. 每条写进 `knowledge/` 的结论，都要在句末标出处：`（来源：<record id>）`。没有出处的不写。
2. 只出现过一次的事不算习惯；至少 3 个不同日期的证据才写进"习惯"。
3. 别人说的话不要记成我做的事（"他说已经发了"≠"我发了"）。
4. 更新已有文件时，保留原内容，把变化补充进去，并更新 frontmatter 里的 `updated`。
5. 我对某条结论提出异议时，修改它，并在旁边注明"（已由本人纠正，日期）"。
6. 每次整理完，运行 `../personal-db/pdb rebuild`，然后用 git 提交，提交信息写清楚整理了什么。
7. 查资料优先用 `../personal-db/pdb search "关键词"`，再读具体记录。

## 常用命令
```bash
../personal-db/pdb import-md raw/feishu/书稿 --source book --type section
../personal-db/pdb import-md raw/feishu/朋友圈 --source wechat_moments --type post
../personal-db/pdb rebuild
../personal-db/pdb search "定价 小红书"
../personal-db/pdb export "定价" > context.md   # 给网页版大模型用
../personal-db/pdb stats
```
