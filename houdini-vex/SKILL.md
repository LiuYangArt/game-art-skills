---
name: houdini-vex
description: 为 Houdini / SideFX VEX 编写、解释、修正可直接粘贴到 Attribute Wrangle、Point Wrangle、Primitive Wrangle、Detail Wrangle、Vertex Wrangle、Volume Wrangle、POP Wrangle 等节点中的代码，并在条件允许时先做真实 Houdini 节点编译与 cook 验证。Use when the user asks for Houdini VEX、Wrangle snippet、@P/@Cd/@N、noise、chramp、nearpoints、pcopen、setpointattrib、volumesample、按点/面/体素处理几何，或需要把自然语言需求翻成可执行 VEX。
---

<!-- Methodology sources: SideFX official VEX language reference, VEX snippets docs, VEX functions index, VEX contexts docs. -->

# Houdini VEX

## Overview

把用户的自然语言需求翻译成可直接放进 Houdini Wrangle 节点的 VEX 代码，并同时说清楚运行上下文、依赖属性、参数和假设。

默认优先覆盖最常见的一线场景：`Attribute Wrangle` / `Point Wrangle` / `Primitive Wrangle` / `Detail Wrangle` / `Volume Wrangle` / `POP Wrangle` 中的 `CVEX` 代码片段。除非用户明确要求，否则不要默认生成完整 `.vfl` shader 文件，也不要把 Python SOP、HScript 或 HDK 解法混进来。

## Validation First

这个 skill 的首要目标不是“一次把效果做满”，而是先保证给出去的 VEX 片段：

1. 语法成立
2. 能在目标 Wrangle 节点里编译
3. 能在最小测试网络里 `cook`

效果不完全对可以再迭代，但没有验证结果时，不要把代码表述成“能跑”。

Wrangle snippet 的权威验证方式不是离线 `vcc`，而是真实 Houdini 节点编译与 `cook`。原因是 `@P`、`@Cd`、`@ptnum`、`chf("freq")` 这类写法带有 Wrangle 节点上下文，脱离节点外壳后并不等价于完整 `.vfl` 文件。

只要本机能找到 `hython`，默认调用 [`scripts/validate_vex.py`](scripts/validate_vex.py) 做真实节点验证。只有在用户明确说“先别验证”或本机没有 Houdini CLI 时，才跳过，并明确告诉用户“未实机校验”。

## Working Defaults

如果用户没有给全上下文，按下面顺序做最小假设，并把假设写出来：

1. 节点是 SOP 里的 `Attribute Wrangle`
2. `Run Over` 是 `Points`
3. 主要输入使用第 1 输入几何
4. 输出目标是直接修改或新增属性，而不是生成独立文件
5. 可调项优先暴露为 `chf` / `chi` / `chv` / `chs` / `chramp` 参数

只有当上下文缺失会直接改变代码结构时才追问，例如：

- 是 `Points`、`Primitives`、`Detail` 还是 `Voxels`
- 是当前输入还是其他输入取样
- 是 SOP/POP/Volume 还是 shader 上下文
- 需要直接写 `@attrib`，还是必须显式调用 `set*attrib` / `addpoint` / `addprim`

## Workflow

### 1. 先锁定执行上下文

先整理这几件事：

- 节点类型：`Attribute Wrangle`、`POP Wrangle`、`Volume Wrangle` 等
- `Run Over` 粒度：`Points`、`Primitives`、`Vertices`、`Detail`、`Voxels`
- 当前元素上有哪些已知属性，例如 `@P`、`@N`、`@Cd`、`@uv`、`@pscale`
- 是否需要读取其他输入，例如 `point(1, ...)`、`prim(1, ...)`、`nearpoints(1, ...)`
- 是否需要额外参数，例如频率、幅度、种子、阈值、ramp

如果用户只说“写一段 VEX”，默认按点级 Wrangle 处理。

### 2. 先定义数据约定，再写代码

在代码前先明确：

- 读取哪些属性
- 新建或覆写哪些属性
- 每个关键属性的预期类型
- 需不需要通过 `i@`、`f@`、`v@`、`s@`、`p@` 显式标注类型
- 是否要从节点参数读取可调值

默认规则：

- 对当前元素读写，优先直接使用 `@attrib`
- 对其他输入或任意元素随机访问，使用 `point()` / `prim()` / `vertex()` / `detail()` / `set*attrib()`
- 调参项不要硬编码，优先外提为 `ch*` 参数
- 对常见属性可以使用 Houdini 已知类型简写，例如 `@Cd`、`@N`、`@orient`
- 对不确定类型或跨输入读取的属性，显式写类型，不依赖自动推断

### 3. 生成代码时遵守这些硬规则

- 输出可直接粘贴的完整片段，不要留伪代码或 TODO
- 默认使用 VEX 常见、直接的写法，不额外发明 helper 框架
- 不做“兼容多种上下文”的 fallback 分支；按当前目标上下文直接写
- 能用 `@attrib` 直接完成时，不要无意义改写成 `setpointattrib`
- 涉及随机时，显式说明种子来源，例如 `@ptnum`、`@primnum` 或用户给定 seed
- 涉及噪声时，说明空间基准，例如对象空间、世界空间、rest 空间或 uv 空间
- 涉及归一化、除法、长度倒数时，主动处理零值风险
- 需要跨元素收集时，优先用 `nearpoints`、`pcfind`、`pcopen`、`xyzdist`、`primuv` 这类 VEX 原生方法
- 需要写新几何时，使用 `addpoint`、`addprim`、`addvertex`，并把拓扑副作用说清楚
- 不要写递归；VEX 官方文档明确说明递归不可用

### 4. 默认先验证，再谈效果

只要本机能找到 `hython`，在回答用户前默认运行：

```powershell
python scripts/validate_vex.py --code-file temp\snippet.vfl --node-type attribwrangle --run-over points
```

验证通过后，才可以把代码表述为“已验证可运行”。

如果验证失败：

- 优先根据错误继续修代码，不要直接把未通过的版本交给用户
- 明确指出是“编译失败”还是“cook 失败”
- 保留最少必要的错误上下文，便于下一轮修正

如果本机没有 `hython`：

- 明确说明“未实机校验”
- 仍可给代码草案，但不要说它已经可运行

### 5. 默认输出节点使用说明

除非用户只要纯代码，否则默认一起输出：

- 建议放在哪个 Houdini 节点里
- `Run Over` 应该设成什么
- 代码会读取哪些属性
- 代码会创建或修改哪些属性
- 需要手动新建哪些参数，以及参数名和类型
- 是否已经通过验证脚本
- 关键假设和边界条件

### 6. 调试和修正时优先检查这些点

遇到“代码不生效”或“结果不对”时，优先检查：

- `Run Over` 是否写错，导致 `@ptnum` / `@primnum` 语义变了
- 代码是否运行在 `CVEX` 上下文，而当前函数是否适用于该上下文
- 属性类型是否写错，例如把 vector 当 float 用
- 其他输入读取时是否忘了显式类型
- 只是改了局部变量，没有真正回写属性
- `Volume Wrangle` 是否误以为写 `@foo` 就能创建新 volume
- POP/DOP 场景里是否把 SOP 语义直接照搬
- `chf` / `chi` / `chv` / `chs` / `chramp` 这类参数是否真的存在于节点上

## Common Patterns

优先复用这些稳定模式：

- 逐点位移：`@P += @N * amount;`
- 随机标量：`float r = rand(@ptnum + chi("seed"));`
- 渐变映射：`float t = fit(@P.y, miny, maxy, 0.0, 1.0);`
- ramp 控制：`float mask = chramp("mask_ramp", t);`
- 噪声驱动：`vector n = noise(@P * chf("freq"));`
- 邻域查询：`int pts[] = nearpoints(1, @P, chf("radius"), chi("maxpts"));`
- 表面采样：`int prim; vector uv; float d = xyzdist(1, @P, prim, uv); vector pos = primuv(1, "P", prim, uv);`
- 显式写属性：`setpointattrib(0, "heat", pt, value, "set");`

## Resource Guide

读取 [references/official-vex-guide.md](references/official-vex-guide.md) 以获取：

- VEX / CVEX / Wrangle 语法要点
- 属性读写与跨输入读取规则
- 常用函数家族
- 官方限制与上下文注意事项

读取 [references/vex-recipes.md](references/vex-recipes.md) 以获取：

- 高度渐变、噪声位移、稳定随机、表面吸附等常用配方
- 更贴近游戏美术场景的最小可用模式
- 常见坑点

读取 [references/validation-workflow.md](references/validation-workflow.md) 以获取：

- 为什么 Wrangle snippet 要用真实节点验证
- `validate_vex.py` 的推荐用法
- 当前验证器的能力边界

调用 [scripts/validate_vex.py](scripts/validate_vex.py) 以获取：

- 本机 `hython` 自动发现
- 临时 Houdini 网络创建
- `Attribute Wrangle` / `Volume Wrangle` 的最小输入构造
- 常见 `ch*` 参数的自动补建
- 节点编译与 `cook` 结果

## Response Style

- 默认用中文。
- 默认先给可直接粘贴的 VEX 代码，再给最短必要说明。
- 默认把节点类型、`Run Over`、参数名、属性读写列表写清楚。
- 若用户只说效果，不空谈抽象语法，直接补足最小假设后给成品。
- 若用户贴报错或现有代码，优先在原思路上最小修改，不顺手重写整段。
- 没有验证结果时，不要说“能跑”或“可运行”；只能说“未实机校验”。
- 验证通过后，明确写“已通过本机 Houdini 节点 cook 验证”或等价表述。