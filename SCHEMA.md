# Personal Database 数据规范 v0.1

这份规范是整个系统的"宪法"。引擎可以重写、模型可以更换，但只要数据遵守这份规范，就永远能被读取和迁移。

## 三层结构

```
my-data/
├── raw/          第1层 原始层：原样保存，永不修改
├── records/      第2层 记录层：统一格式 JSONL，一行一条记录
├── knowledge/    第3层 理解层：Markdown，人和模型都能直接读
└── index.db      索引：由 records 生成，可删可重建，不进 git
```

### 规则

1. **raw/ 只增不改**。导入新数据就新增文件，不覆盖、不编辑旧文件。
2. **records/ 由脚本生成**，不手工编辑。要修正内容，改 raw 或改转换器后重新导入。
3. **knowledge/ 里每条结论都要带出处**，格式：`（来源：record_id 或 raw/路径）`。
4. **index.db 永远是可丢弃的**。任何时候删掉它，运行 `pdb rebuild` 都能完整恢复。

## 记录格式（records/）

文件位置：`records/<source>/<YYYY>.jsonl`，按来源和年份分文件，一行一条 JSON。

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✅ | `sha256(source + ref + content)` 前 16 位。同一内容重复导入不会重复 |
| `source` | ✅ | 数据来源，小写下划线：`book`、`wechat_moments`、`wechat_chat`、`xiaohongshu`、`note` |
| `type` | ✅ | 记录类型：`chapter`、`section`、`post`、`message`、`note`、`doc` |
| `created_at` | ⭕ | ISO 8601，例如 `2021-03-15T22:10:00`；未知则为 `null` |
| `author` | ✅ | `me` 表示本人，其他人用名字 |
| `title` | ⭕ | 标题或所属章节路径，例如 `第三章 / 定价的逻辑` |
| `content` | ✅ | 正文纯文本或 Markdown |
| `ref` | ✅ | 指回原始层的位置：`raw/feishu/书稿/第3章.md#定价的逻辑` |
| `media` | ⭕ | 关联的图片/附件路径列表 |
| `tags` | ⭕ | 标签列表 |
| `imported_at` | ✅ | 导入时间 |

示例：

```json
{"id":"3f9a1c2b7d4e8f01","source":"book","type":"section","created_at":null,"author":"me","title":"第三章 / 定价的逻辑","content":"……","ref":"raw/feishu/书稿/第3章.md#定价的逻辑","media":[],"tags":[],"imported_at":"2026-11-05T22:00:00"}
```

## 理解层（knowledge/）

| 目录 | 内容 |
|---|---|
| `me/` | 我是谁：身份、核心观点、价值观、表达风格、习惯（≥3 个不同日期的证据才算习惯） |
| `people/` | 一人一个文件，含别名、关系、共同经历 |
| `projects/` | 一个项目一个文件，含目标、进展、决策 |
| `playbooks/` | 我怎么做事：目标、工具、步骤、产物、踩过的坑 |
| `timeline/` | 按年/季度的个人时间线：在做什么、在想什么、观点如何变化 |

每个文件开头使用 frontmatter：

```markdown
---
title: 小红书虚拟品上架流程
aliases: [上架SOP]
updated: 2026-11-05
---
```

## 新增数据来源

只需要写一个"转换器"：把原始文件转成上面的记录格式，写入 `records/<新source>/`。数据库结构不变。

## 版本

规范变更时更新版本号，并在 `CHANGELOG` 中说明如何迁移旧记录。
