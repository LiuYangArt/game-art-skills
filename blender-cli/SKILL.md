---
name: blender-cli
description: Use when the user wants to run Blender from the terminal, validate a Blender extension, execute Blender in background mode, inspect command-line capabilities with --help or /?, or when Blender is installed but not available in PATH and you need to locate the executable first.
---

# Blender CLI

## Overview

这个 skill 用于在 Windows 环境下稳定调用 Blender 命令行，并处理最常见的阻塞点：`PATH` 里没有 `blender`、不知道可执行文件在哪、需要先看 `--help`、或者要在后台模式里跑脚本与扩展校验。

优先把它当成“定位 + 验证 + 执行”的工作流，而不是只记某一条命令。

## 适用场景

当用户出现下面这些意图时使用这个 skill：

- 想从终端运行 Blender
- 想执行 `blender --version`、`blender --help`
- 想在后台模式运行 Python 表达式或脚本
- 想验证 Blender Extension / add-on 是否能被导入或注册
- 明确说自己已经装了 Blender，但命令行找不到
- 需要先探测本机 Blender 安装路径，再决定后续命令

## 工作流

### 1. 先检查 PATH

先不要假设 `blender` 在 `PATH` 中。优先用 PowerShell 检查：

```powershell
Get-Command blender -ErrorAction SilentlyContinue
```

如果找到了，优先直接使用返回的可执行路径，避免重复搜索磁盘。

### 2. PATH 里没有时，先查常见安装目录

在 Windows 上，优先检查这些目录，而不是一开始就全盘递归：

```powershell
Get-ChildItem "C:\Program Files\Blender Foundation" -Directory -ErrorAction SilentlyContinue
Get-ChildItem "C:\Program Files (x86)\Steam\steamapps\common\Blender" -ErrorAction SilentlyContinue
Get-ChildItem "C:\Program Files (x86)\Steam\steamapps\common\Blender" -Filter blender.exe -Recurse -ErrorAction SilentlyContinue
```

如果用户提到 Steam 安装版，优先检查：

```text
C:\Program Files (x86)\Steam\steamapps\common\Blender
```

### 3. 还没找到时，再做磁盘检索

只有在常见路径都没命中时，再递归搜索磁盘。先搜最可能的盘符，再决定是否扩大范围。

优先示例：

```powershell
Get-ChildItem "C:\" -Filter blender.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 5 FullName
Get-ChildItem "D:\" -Filter blender.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 5 FullName
```

注意：

- 递归搜索可能很慢，先和用户对齐“要不要全盘找”
- 一旦拿到首个可信路径，先验证，不要继续无意义扫描

### 4. 找到后先做最小验证

拿到可执行文件路径后，先跑版本命令验证它真能用：

```powershell
& "C:\path\to\blender.exe" --version
```

如果这一步失败，不要直接继续跑复杂命令，先看报错。

### 5. 按需查看帮助

当用户说“看看 CLI 能做什么”或需要确认参数时，优先使用帮助命令。

官方常用帮助入口：

```powershell
& "C:\path\to\blender.exe" --help
& "C:\path\to\blender.exe" -h
& "C:\path\to\blender.exe" /?
```

说明：

- `-h` 和 `--help` 都可以打印帮助
- Windows 下也可以使用 `/?`
- 如果用户只是想知道有哪些能力，先跑帮助，再根据帮助内容选子命令

### 6. 常见执行模式

#### 后台模式

适合做校验、执行表达式、跑脚本，不打开 GUI：

```powershell
& "C:\path\to\blender.exe" --background --factory-startup --python-expr "import bpy; print(bpy.app.version_string)"
```

#### 运行脚本

```powershell
& "C:\path\to\blender.exe" --background --python your_script.py
```

#### 运行内联表达式

```powershell
& "C:\path\to\blender.exe" --background --python-expr "print('hello from blender')"
```

#### 扩展命令入口

当任务与 Blender Extension 打包、校验、安装有关时，优先查看：

```powershell
& "C:\path\to\blender.exe" --command extension --help
```

如果帮助中存在目标子命令，再继续使用对应动作，例如 `validate`、`build`、`list`、`install-file`。

## 推荐执行顺序

除非用户已经给了准确路径，否则按这个顺序推进：

1. `Get-Command blender`
2. 常见目录探测
3. 必要时检索磁盘
4. `--version`
5. `--help` / `/?`
6. 真实业务命令

## 输出要求

在回答用户时，尽量返回：

- 你最终使用的 Blender 可执行文件绝对路径
- 已验证的版本号
- 实际执行的命令意图
- 如果失败，给出关键报错而不是只说“不能用”

如果是第一次找到 Blender，最好明确说明：

- 不需要额外安装 Blender CLI
- CLI 就是 `blender.exe` 的命令行用法
- 没进 `PATH` 时，直接用绝对路径也完全可以

## 不要做的事

- 不要在已经找到可执行文件后继续全盘搜索
- 不要假设所有机器都安装在 `Blender Foundation`
- 不要在没做 `--version` 验证前就宣称 CLI 可用
- 不要只给出 `blender ...` 简写，若 `PATH` 未配置，必须改用绝对路径

## 参考依据

优先使用 Blender 官方命令行文档核对参数，尤其是：

- `--help` / `-h`
- Windows `/?`
- `--background`
- `--python`
- `--python-expr`
- `--command extension --help`
