# 用途

这个仓库收集了面向游戏美术相关工作的 agent skills。

## 安装

- 把需要的 skill 目录复制到你的 agent skills 根目录下。
- 如果 agent 支持从仓库安装，也可以直接把本仓库地址发给它处理。

## 当前包含的 skill

- `blender-cli`
  - 用于在终端里运行 Blender、检查命令行能力、后台执行任务，以及在 Blender 不在 PATH 时定位可执行文件。
- `design-reference-flow`
  - 用于 staged concept design、参考图搜索整理、Obsidian Canvas 汇总、可复用 prompt library 沉淀，以及基于参考图的迭代式出图。
- `lark-whiteboard-write`
  - 用于通过已登录浏览器，把本地图片上传到飞书文档内嵌白板。
- `perforce-p4`
  - 用于让 agent 通过 `p4` CLI 处理 Perforce Helix Core 的初始化、workspace、同步、分支、冲突等工作。
- `unreal-custom-node`
  - 用于为 Unreal Engine 材质 Custom Node 生成可直接粘贴的 HLSL 代码。
- `unreal-editor-python-debug`
  - 用于通过 `UnrealEditor-Cmd.exe` 和 Unreal Python，在真实 UE 工程里做调试、验证和批量检查。
- `yunwu-image-gen`
  - 用于通过 Yunwu API 生成图片并保存到本地。

## 目录复制说明

这些 skill 不是单文件 skill，迁移时要复制整个目录，不要只拿 `SKILL.md`：

- `design-reference-flow/`
  - 目录里的 `agents/`、`assets/`、`references/`、`scripts/` 都是 skill 的一部分，路径关系不能打散。
- `perforce-p4/`
  - 自带面向团队成员的说明文档和参考资料，建议整个目录一起带上。
- `unreal-custom-node/`
  - `references/` 目录提供导出格式和使用说明，建议整目录保留。

其余 skill 当前主要入口是 `SKILL.md`，但为了避免后续补充文件后丢内容，仍建议按目录整体复制。

## 依赖

按 skill 不同，仓库里部分能力依赖以下工具：

- `obsidian-cli`
  - 主要给 `design-reference-flow` 用于读写 Obsidian 文档。
  - https://obsidian.md/cli
  - https://github.com/kepano/obsidian-skills/tree/main/skills/obsidian-cli
- `bb-browser`
  - 主要给 `design-reference-flow` 用于访问参考图网站。
  - https://github.com/epiral/bb-browser
- Python `3.11+`
  - `design-reference-flow` 的脚本链依赖本地 Python 运行。
- Blender
  - `blender-cli` 需要本机已安装 Blender，或能在本机定位到 Blender 可执行文件。
- Unreal Engine
  - `unreal-custom-node` 和 `unreal-editor-python-debug` 面向本机已有 UE 工程的场景。
- Perforce CLI `p4`
  - `perforce-p4` 依赖本机可用的 Perforce 命令行环境。

## 补充说明

- `design-reference-flow` 中提到的 `$brainstorming` 只是对话风格参考，不是硬依赖。
- `perforce-p4` 里的 `p4-connection.json` 属于本机连接配置，不应直接提交到仓库。