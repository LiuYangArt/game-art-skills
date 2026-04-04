# design-reference-flow

## 这次分享需要一起带上的内容

这个 skill 不是单文件 skill，不能只复制 `SKILL.md`。

需要一起保留的目录和文件：

- `SKILL.md`
- `agents/openai.yaml`
- `assets/`
- `references/`
- `scripts/`

原因：

- `SKILL.md` 里大量使用相对路径引用 `references/*` 和 `assets/*`
- scripted fast path 直接调用 `scripts/search_runner.py`、`scripts/ref_curator.py`、`scripts/prompt_builder.py`、`scripts/canvas_builder.py`
- `agents/openai.yaml` 提供了给 agent 使用的显示信息

这几个目录的相对位置不要改，否则文档链接和脚本路径会失效。

## 不需要一起带的作者本机残留

这些文件没有复制进仓库，因为它们属于作者自己的工作痕迹，不是 skill 运行必需品：

- `notes.md`
- `task_plan.md`
- `automation-upgrade-plan.md`
- `scripts/__pycache__/`

## 运行依赖

硬依赖：

- `obsidian-cli` 或等价的 Obsidian 读写能力
- `bb-browser`
- Python `3.11+`

软依赖：

- `$brainstorming`
  - 只被当成对话风格参考，不装也不会导致脚本链失效
- subagents
  - 只在用户明确要求并行搜索时使用，不是必须

## 当前仓库里的安装方式

把整个 `design-reference-flow/` 目录复制到团队成员自己的 skills 根目录下即可。

如果团队成员用的是 Codex，通常是：

```text
~/.codex/skills/design-reference-flow
```

如果团队成员用的是别的 agent，也保持目录完整迁移，不要拆文件。
