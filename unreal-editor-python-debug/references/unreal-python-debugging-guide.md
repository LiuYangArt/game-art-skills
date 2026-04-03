# UnrealEditor-Cmd + Python 调试指南

## 什么时候应该进 Unreal 内调试

出现这些情况时，优先用 Unreal 内验证：

- 问题只在编辑器或 commandlet 中复现
- 错误信息来自 `Saved/Logs/*.log`
- 编译错误指向 `MaterialTemplate.ush`、`Generated/Material.ush`
- 涉及 `.uasset`、材质图、Niagara、EditorOnlyData、命令行 commandlet

## Unreal 基础世界约定

调试视觉问题时，先记住这两个基础事实：

- Unreal 常见世界坐标是 `Z-up`
- 默认世界长度单位是厘米

这意味着很多“看起来 shader 坏了”的问题，其实可能是：

- 把 `Y-up` 示例直接移植到 Unreal
- 把水平平面写成了 `XZ` 而不是 `XY`
- 把无单位参数直接套进了以厘米为单位的世界空间逻辑

## 证据优先级

建议按下面顺序收集证据：

1. `Saved/Logs/*.log`
2. `Saved/ShaderDebugInfo/...`
3. Unreal Python 探针输出
4. 离线 `dxc` 或其他模拟验证

离线工具只能说明“在近似包装环境里成立”，不能替代 Unreal 真实编译结果。

## 高频坑

### 1. `-script=` 路径转义

Windows 下把脚本路径传给 `UnrealEditor-Cmd.exe -run=pythonscript -script=...` 时，优先使用正斜杠。

坏例子：

- `E:\Portable Apps\AppData\AGENTS\ue_material_probe.py`

好例子：

- `E:/Portable Apps/AppData/AGENTS/ue_material_probe.py`

否则可能在日志里出现路径损坏、控制字符或脚本找不到。

### 2. commandlet 成功不等于资产成功

这三件事要分开判断：

- `PythonScriptCommandlet` 是否成功运行
- Python 探针脚本是否成功运行
- 目标资产是否真正通过编译或验证

### 3. Python API 不一定暴露图结构

某些 Unreal Python 反射路径下，材质图表达式列表不一定像 C++ 或编辑器 UI 那样直接可见。

如果你拿不到：

- `expressions`
- `editor_only_data.expression_collection`

不要立即认定资产里没有表达式。先转去：

- 日志
- `Saved/ShaderDebugInfo`
- `dir(obj)` / `get_editor_property()` 探测

### 4. ShaderDebugInfo 非常值钱

当材质编译失败时，`Saved/ShaderDebugInfo` 往往能回答这些问题：

- 代码是否被原样注入
- 失败发生在哪个 permutation / shader stage
- 变量是否根本没有生成
- 是 HLSL 语法问题，还是 Unreal 节点接口不一致

## 推荐探针风格

- 统一用 `[CodexProbe]` 前缀打印日志，方便 `grep`
- 一次只验证一个假设
- 先读，再触发重编译，再读新日志
- 跑 `UnrealEditor-Cmd.exe` 时，默认优先用 `--quiet-editor-output` 收敛原始 stdout/stderr，再配合 `--grep` 看关键证据

## 推荐命令形态

```powershell
python scripts/run_ue_python_cmd.py `
  --project "D:\Path\YourProject.uproject" `
  --script "E:/Path/probe.py" `
  --grep "[CodexProbe]" `
  --grep "error:" `
  --quiet-editor-output
```

这套模式更适合日常排查，因为终端里保留的是“结论相关证据”，不是整段 Unreal 启动噪音。

## 适合复用的任务

- 材质/Custom Node 编译诊断
- 资产类与属性探测
- UE 版本差异复现
- 批量只读审计
- 轻量命令行重编译验证
