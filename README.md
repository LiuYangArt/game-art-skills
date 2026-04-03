# 用途
- 用于游戏美术工作中的一些agent skill

# 安装
- 安装到你agent对应的skills路径下
- 可以把本仓库地址丢给你的agent，让它自动安装

# 当前包含的 skill
- `yunwu-image-gen`
- `unreal-custom-node`
- `unreal-editor-python-debug`
- `concept-design-flow`
  - 用于 staged concept design、参考图搜索整理、Obsidian Canvas 汇总、Nano Banana prompt pack 沉淀
  - 这是一个多文件 skill，复制时要带上整个目录，不要只拿 `SKILL.md`

# 依赖
## obsidian cli
- 用于读写obsidian文档
- https://obsidian.md/cli
- https://github.com/kepano/obsidian-skills/tree/main/skills/obsidian-cli
## bb-browser
- 用于访问参考图网站等
- https://github.com/epiral/bb-browser
## Python 3.11+
- `concept-design-flow` 的脚本链依赖本地 Python 运行

# 补充说明
- `concept-design-flow` 目录里的 `assets/`、`references/`、`scripts/`、`agents/` 都是 skill 的一部分，路径关系不能打散
- `concept-design-flow` 中提到的 `$brainstorming` 只是对话风格参考，不是硬依赖
