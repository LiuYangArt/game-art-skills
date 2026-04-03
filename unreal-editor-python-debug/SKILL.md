---
name: unreal-editor-python-debug
description: 用 UnrealEditor-Cmd.exe 和 Unreal Python 在真实 UE 工程内调试材质、资产、日志、命令行验证与批量检查。Use when the user asks to inspect a .uproject, validate a material or Custom Node in-engine, run a Python probe inside Unreal, recompile an asset, read Saved/Logs or ShaderDebugInfo, compare installed UE versions, or debug an issue that only reproduces inside Unreal rather than in offline tools.
---

<!-- Methodology sources: UnrealEditor-Cmd commandlet workflow; Unreal Python commandlet usage; real UE5.5 asset/material debugging experience. -->

# Unreal Editor Python Debug

## Overview

把“只在 Unreal 工程里才能复现”的问题拉回到可自动化的命令行和 Python 探针流程里。

优先使用 [`scripts/run_ue_python_cmd.py`](scripts/run_ue_python_cmd.py) 选择 Unreal 版本并运行 `UnrealEditor-Cmd.exe`，再用定制化的 Unreal Python 探针脚本读取资产、触发重编译、检查日志和 `Saved/ShaderDebugInfo`。

需要具体调试模式与常见陷阱时，读取 [`references/unreal-python-debugging-guide.md`](references/unreal-python-debugging-guide.md)。

## Workflow

### 1. 先确认问题是否属于“必须在 Unreal 内验证”

出现下面任一情况时，不要只靠离线工具：

- `Saved/Logs/*.log` 里才有报错
- 报错涉及 `MaterialTemplate.ush`、`/Engine/Generated/Material.ush`
- Custom Node / Material / Niagara / Editor Utility 在 Unreal 内外行为不一致
- 需要读取 `.uproject`、`.uasset`、材质图、EditorOnlyData、ShaderDebugInfo
- 需要知道最低或指定 UE 版本下是否复现

### 2. 先选 Unreal 版本，再跑命令行

默认优先使用本机已安装的最低版本 `UE_*`，除非用户明确指定版本。

推荐入口：

```powershell
python scripts/run_ue_python_cmd.py `
  --project "D:\Path\YourProject.uproject" `
  --script "E:/Path/probe.py" `
  --grep "[CodexProbe]" `
  --quiet-editor-output
```

这个脚本会：

- 自动发现已安装 Unreal 版本
- 默认选择最低版本
- 运行 `UnrealEditor-Cmd.exe`
- 定位最新日志文件
- 可选输出匹配行或日志尾部
- 可选把 Unreal 原始 stdout/stderr 收敛起来，只在失败时展开

### 3. Python 探针要尽量小而准

探针脚本只做一件具体的事：

- 读取一个资产的类名、路径、属性
- 触发一个材质重编译
- 打印编译相关方法
- 搜索某个 EditorOnlyData 或日志特征

不要一开始就写很大的“全能脚本”。先用最小探针确认根因。

### 4. 优先看哪三类证据

1. Unreal 命令行退出码和 `Saved/Logs/*.log`
2. `Saved/ShaderDebugInfo/...` 里导出的 shader/debug 文件
3. Python 探针输出的 `[CodexProbe]` 日志

如果三者冲突，以 Unreal 工程真实日志和导出 shader 文件为准。

## Common Patterns

### 模式 A：材质 / Custom Node 编译错误

做法：

- 读取最新 `Saved/Logs/*.log`
- 搜索 `MaterialTemplate.ush`、`Generated/Material.ush`、`undeclared identifier`
- 如果需要，进入 `Saved/ShaderDebugInfo` 读取对应 `*.usf`
- 判断是：
  - 代码语法错误
  - Unreal 节点接口和代码正文不一致
  - 坐标系、材质域、平台宏等 Unreal 特有问题

### 模式 B：读取资产元数据或能力面

做法：

- 用 [`scripts/probe_asset.py`](scripts/probe_asset.py) 加载资产
- 读取类名、可见属性、编译相关方法
- 如果 Python API 没暴露足够多的图结构信息，不要强行猜；转去日志和 ShaderDebugInfo

### 模式 C：重编译并验证

做法：

- 在 Unreal Python 里调用可用的重编译入口
- 重新读取日志
- 明确区分：
  - commandlet 成功执行
  - Python 脚本成功执行
  - 资产真的编译成功

这三者不是一回事。

## Guardrails

- 默认用正斜杠路径传给 `-script=`，避免 Windows 反斜杠转义导致路径损坏。
- 不要把 commandlet 成功退出当成资产验证通过。
- 如果 Python API 没暴露某个图结构字段，不要编造字段名；转去日志、反射属性或导出 shader 文件。
- 如果需要跨版本复现，先跑最低版本，再按需跑用户指定版本。
- 除非用户明确要求，不要在工程里批量改资产。
- 默认更推荐 `--quiet-editor-output + --grep` 组合，这比直接把整段 Unreal 启动日志打到终端更适合排查单个问题。

## Resource Guide

调用 [`scripts/run_ue_python_cmd.py`](scripts/run_ue_python_cmd.py) 以：

- 自动选择最低 Unreal 版本
- 运行 `UnrealEditor-Cmd.exe`
- 传入环境变量给 Unreal Python 探针
- 输出日志路径和匹配结果
- 在需要时用 `--quiet-editor-output` 收敛终端噪音

调用 [`scripts/probe_asset.py`](scripts/probe_asset.py) 以：

- 加载指定资产
- 输出类名、路径、部分属性信息
- 检查编译相关方法
- 可选触发材质重编译

读取 [`references/unreal-python-debugging-guide.md`](references/unreal-python-debugging-guide.md) 以获取：

- 何时用 Unreal 内验证
- 常见路径和日志位置
- Unreal Python / commandlet 调试的高频坑

## Response Style

- 默认用中文说明。
- 默认先写“这次验证是在 Unreal 内还是离线工具内完成的”。
- 默认给出实际使用的 `UnrealEditor-Cmd.exe` 版本和工程路径。
- 默认把“证据”和“结论”分开写，避免把推断说成事实。
