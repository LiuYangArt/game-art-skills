---
name: obsidian-cli
description: Use when 需要通过 Obsidian CLI 或 obsidian:// URI 在终端读取/检索/创建笔记，或从 URI（含 .canvas）完整提取文本与附件路径。
---

# Obsidian CLI

## 概览

目标是把 Obsidian 的“打开、读取、搜索、写入、URI 解析”变成可复用终端流程。优先直连 CLI，避免全盘扫描。

## 快速流程（默认）

1. 执行环境检测。
2. 用 `obsidian read/search/open` 直接访问目标 vault + path。
3. 若输入是 `obsidian://`，先解码 `vault/file` 再执行 CLI 命令。
4. 若目标是 `.canvas`，额外解析附件节点并验证图片文件是否存在。

## 环境检测

按顺序执行：

```powershell
obsidian help
```

判定规则：
- 找不到 `obsidian` 或命令失败：按“Windows 启用与排查”处理。

## 高效 URI 提取流程（推荐）

当用户给的是 `obsidian://open?vault=...&file=...`：

1. 解析 URI 参数，先拿到 `vault` 和 `file`（URL Decode）。
2. 直接读取目标文件：
   - `obsidian read vault="<vault-name>" path="<vault-relative-path>"`
3. 如果后缀是 `.canvas`：
   - 解析 JSON `nodes`；
   - 提取 `type=text` 节点文本；
   - 提取 `type=file` 节点的附件路径；
   - 用 vault 根路径拼接后校验附件存在性。
4. 只有当 CLI 不可用时，才回退到本地文件系统读取。

这条流程可以一次拿到：画布文本内容、连线结构、图片文件清单、缺失附件列表。

## Windows 启用与排查

1. 确认 Obsidian 版本满足官方要求（Installer `1.12+`，并开启 Catalyst）。
2. 在 Obsidian 设置中打开 `General -> Installer command line support`。
3. 关闭并重新打开终端会话，再次执行 `where.exe obsidian`。
4. 若仍失败，重启 Obsidian 后重试。

当 CLI 暂不可用时，使用回退方式：

```powershell
& "$env:LOCALAPPDATA\Programs\Obsidian\Obsidian.exe" "obsidian://open?vault=<vault-name>"
```

## 常见任务

优先使用命令行子命令；具体模板见 [references/obsidian-cli-reference.md](references/obsidian-cli-reference.md)。

- 打开指定库或文件。
- 新建笔记并写入基础内容。
- 打开今日笔记（daily）。
- 按关键词搜索并跳转结果。
- 从 URI 或 `.canvas` 批量提取文本与附件路径。

## 执行约束

- 先检测、后执行；不要假设 `obsidian` 一定存在于 PATH。
- Windows 路径与参数统一加引号，避免空格导致失败。
- 优先 `obsidian read/search` 精确读取，避免直接递归扫描 vault。
- 如果操作会批量写入大量笔记，先做最小样本验证（1-2 条）再放量。
- 当用户要求跨平台命令时，先声明当前命令针对 Windows。

## 参考资料

- 命令模板与参数：`references/obsidian-cli-reference.md`
- 官方 CLI 文档：`https://help.obsidian.md/cli`
