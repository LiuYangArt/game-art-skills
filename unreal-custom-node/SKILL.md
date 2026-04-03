---
name: unreal-custom-node
description: 为 Unreal Engine / 虚幻引擎材质系统生成可直接粘贴到 Custom Material Expression / Custom Node 的 HLSL 代码。Use when the user asks for UE 材质 Custom Node、Custom Material Expression、材质 HLSL 片段、可复制到材质编辑器里的 shader 代码，或希望把 blur、dissolve、UV distortion、outline、polar mapping、noise、depth/fresnel/math logic 等效果写进 Unreal 的 Custom Node。
---

<!-- Methodology sources: Epic Games official Custom Material Expressions documentation; Microsoft HLSL/DXC offline compilation guidance. -->

# Unreal Custom Node

## Overview

把用户对材质效果的自然语言描述，翻译成 Unreal Engine Material Custom Node 的完整节点规格与可复制代码。

默认输出两份彼此对应、都可直接复制的结果：

1. 能直接粘贴到 Unreal `Code` 字段的 HLSL
2. 能直接粘贴到 Unreal 材质编辑器里的 `MaterialGraphNode_Custom` 导出文本

第二份文本只包含 Custom Node 本体，以及它需要的输入/输出 pin；默认不包含前后接入的外围节点。

在条件允许时调用 [`scripts/validate_custom_node.py`](scripts/validate_custom_node.py) 做静态语法与离线编译验证。需要稳定输出双代码块时，优先调用 [`scripts/render_custom_node_dual_blocks.py`](scripts/render_custom_node_dual_blocks.py)；如果只需要生成 Unreal 粘贴块，则调用 [`scripts/generate_custom_node_paste_export.py`](scripts/generate_custom_node_paste_export.py)。

当用户明确要求“帮我验证这个 Custom Node”，并且给出了 Unreal 工程上下文时，优先调用 [`scripts/validate_custom_node_pipeline.py`](scripts/validate_custom_node_pipeline.py) 跑两层验证：

1. `dxc` 静态验证
2. `UnrealEditor-Cmd.exe` 工程内验证

需要细节或边界条件时，读取 [`references/custom-node-doc-summary.md`](references/custom-node-doc-summary.md)。

如果用户是在真实 Unreal 工程里调试编译错误，尤其是已经出现 `use of undeclared identifier`、`MaterialTemplate.ush`、`/Engine/Generated/Material.ush` 之类报错时，不要只依赖离线 `dxc`。应明确提示：这类问题经常是 Custom Node 的 Unreal 节点接口与代码正文不一致，而不是纯 HLSL 语法错误。

## Workflow

### 1. 先把需求翻译成节点规格

先把用户描述整理成下面这组信息：

- 效果目标：这个节点最终要输出什么。
- 放置位置：接到 `Base Color`、`Emissive`、`Opacity Mask`、`Normal`、`World Position Offset`，还是只做中间计算。
- 输出类型：`float`、`float2`、`float3`、`float4` 之一；除非用户明确要求，否则不要输出模糊类型描述。
- 输入列表：每个输入都给出名称、类型、含义。
- 坐标空间：明确使用 `UV`、屏幕空间、世界空间、切线空间，还是时间/深度等数据。
- 采样需求：是否需要纹理输入、法线贴图输入、SceneTexture 风格数据，或纯数学程序化逻辑。
- 假设项：如果用户没说清楚，做最小化假设并显式写出来。

只有在歧义会直接改变代码结构时才追问。其他情况下直接做最小假设并继续。

这里的“输入类型”是技能内部的期望类型和接线规范，不是 Unreal `Inputs` 面板里的可选字段。Unreal 新建 Custom Node 输入时，`Inputs` 列表里通常只有 `Input Name`；真正的类型由接到该输入 pin 的表达式推导。

默认 Unreal 世界约定：

- `Z-up`：`Z` 是高度方向，水平平面通常是 `XY`
- 长度单位默认按厘米理解

因此所有涉及世界空间距离、波长、衰减半径、偏移步长、法线重建步长的代码，都要明确说明这些参数是在“厘米世界”下工作的，避免把 ShaderToy 或其他引擎里偏抽象的无单位数值直接照搬。

### 2. 先设计节点接口，再写代码

永远先确定节点接口，再生成代码主体。

默认优先使用这些稳定约定：

- 用 `UV` 表示二维采样坐标。
- 用 `Tex` 表示 `TextureObject` 输入。
- 用 `Time`、`Radius`、`Intensity`、`Scale`、`Center`、`Speed` 这类直观名称表示标量或向量参数。
- 用 `float` / `float2` / `float3` / `float4` 风格思考输出，而不是先写代码再反推类型。

如果需要纹理采样，默认使用 Unreal Custom Node 常见写法：

- 输入里声明一个纹理对象，例如 `Tex`。
- 在代码里通过 `Texture2DSample(Tex, TexSampler, UV)` 采样。

如果需要多路结果，优先考虑：

- 主输出保持最核心结果。
- 只有当用户明确需要额外 pin 时，才规划 `Additional Outputs`。

给用户描述节点配置时，必须区分这两层：

- `Inputs` 面板里需要手动新增哪些 `Input Name`
- 每个输入 pin 外部应该接什么节点，以及该连接会把它推导成什么类型

不要把这两层混写成“在 Inputs 里选择 Float3 / Float”。那会误导用户。

### 2.5. 世界空间参数要按 Unreal 手感解释

如果节点逻辑发生在世界空间里，尤其是水面、波纹、扫描圈、溶解边界、程序化噪声、法线重建这类效果，默认把参数说明写成 Unreal 用户能直接调的口径，而不是抽象数学变量。

默认优先这样表述：

- `WaveScale`：世界空间频率。数值越大，单位距离内图案越密；在 Unreal 的厘米世界里，通常不能直接照搬 ShaderToy 原值。
- `WaveLength`：世界空间波长，按厘米理解；数值越大，波峰间距越大。
- `Speed`：动画推进速度。若代码基于世界空间相位推进，最好说明它和厘米尺度、时间缩放的关系。
- `Radius`：影响半径，按厘米理解。
- `Thickness`：边缘厚度或带宽，按厘米理解。
- `Falloff`：衰减范围，按厘米理解；值越大通常过渡越缓。
- `HeightScale` / `Amplitude`：高度振幅；如果用于 `Z` 向位移或波高，按厘米理解。
- `eps`：法线重建、差分或导数近似时的采样步长，通常是厘米级偏移。

如果用户没有要求特别学术化的解释，默认把这些参数说明写成“调参手感 + UE 世界单位”两部分，而不是只写“控制频率”“控制强度”。

### 3. 生成 Custom Node 代码时遵守这些硬规则

- 默认输出“代码体”，不是完整 shader 文件，也不是完整函数库。
- 默认显式写 `return`，不要依赖隐式表达式风格。
- 优先写自包含代码，避免依赖外部全局变量。
- 优先用局部变量把步骤拆开，保证复制后可读。
- 只有在逻辑明显需要时才写循环；循环次数尽量可控。
- 只有在必须共享逻辑时才引入更复杂的辅助结构。
- 不要把普通材质图节点更适合的简单加减乘除硬塞进 Custom Node；但如果用户明确要 Custom Node，仍然输出可用代码。

### 4. 规避 Unreal Custom Node 的已知坑

根据官方文档和实践规则，生成代码时主动避开这些问题：

- 不要把输入名称写成与现有材质参数同名的高风险名字。
- 不要用数组；需要数组语义时，优先改成固定次数循环、展开写法或 compile-time define。
- 不要忽略性能影响：Custom Node 会阻止常量折叠，简单逻辑可能比纯材质图更贵。
- 不要把 `Include File Paths` 和 `#include` 混为一谈；前者是目录，代码里再写 `#include`。
- 不要在输出里留下“TODO”“replace me”“your texture here”之类占位文本。
- 不要假设 ShaderToy 的坐标方向与 Unreal 一致。涉及地面、水面、法线、地平线时，显式声明当前代码是 `Z-up` 还是其他约定。

### 5. 用固定输出格式返回结果

默认按下面结构输出，确保用户可以直接照着填节点：

1. 先给一段一句话说明：这个节点做什么，建议接到哪里。
2. 再列出假设项。
3. 再列出节点配置：
   - `Output Type`
   - `Inputs`
   - `Pin Connections`
   - `Additional Outputs`
   - `Additional Defines`
   - `Include File Paths`
   - `Desc`
4. 默认优先生成一个 `HLSL Markdown` 文件，并返回完整绝对路径。
5. 如果用户要求单节点粘贴块，再生成一个 `Material Editor Paste Export Markdown` 文件，并返回完整绝对路径。
6. 如果用户要求完整节点组，再生成一个 `Full Graph Markdown` 文件，并返回完整绝对路径。
7. 如果做了验证，再补一段验证结果。

除非用户明确要求，不要输出冗长教程。重点是让用户复制即可用。

如果效果依赖世界空间，建议在“假设项”或“节点配置”后额外补一小段“参数手感说明”，用 3 到 6 行写清楚最关键的世界尺度参数。

默认输出策略改为分文件：

- `*_custom_node_hlsl.md`
- `*_custom_node_paste.md`
- `*_full_graph.md`

其中：

- `HLSL` 文件默认总是生成
- `custom_node_paste` 文件只在用户要求单节点粘贴块时生成
- `full_graph` 文件只在用户要求完整节点组时生成

默认先生成“单个 Custom Node 节点本体”的粘贴块，不自动生成外围参数节点与连线；只有当用户明确要求“完整节点组”“包含外围节点”“整套材质图可粘贴块”时，才切换到完整节点组导出模式。

返回路径时，必须优先给完整绝对路径，例如：

- `C:\Users\LiuYang\Desktop\ocean_all_in_one_custom_node_hlsl.md`

不要只给短链接或相对路径。

## Validation

在下面场景主动调用验证脚本 [`scripts/validate_custom_node.py`](scripts/validate_custom_node.py)：

- 用户明确要求“验证一下”。
- 代码包含循环、采样宏、`#include`、宏定义，或比单行表达式复杂得多。
- 你自己判断这段代码存在语法风险。

验证时遵守这些规则：

- 优先用离线 `dxc` 做静态编译验证。
- 把输入规格一起传给脚本，不要只校验一段裸代码。
- 把通过结果表述为“静态语法/离线编译通过”，不要夸大成“已在项目里真机编译通过”。
- 如果代码依赖 Unreal 工程专有 include 或宏，明确说明验证覆盖范围。

当用户已经在 Unreal 工程里落地该节点时，使用下面的验证分层：

1. `dxc` 静态验证：
   只验证代码体语法、采样宏、输出类型和基本包装是否成立。
2. Unreal 工程内验证：
   检查 `Saved/Logs/*.log` 和 `Saved/ShaderDebugInfo/.../Material.ush` 或导出的 shader 文件，确认：
   - 代码是否被原样注入
   - `Inputs` 名称是否真的映射成了可用变量
   - 是否存在 Unreal 特有的 `undeclared identifier`、坐标系假设错误、材质域不匹配等问题

如果出现 `use of undeclared identifier 'Foo'`，优先判断：

- Custom Node 是否真的新增了名为 `Foo` 的输入
- 名字是否逐字一致，含大小写
- 外部是否接入了表达式，导致 Unreal 推导出该输入类型
- 是否把“期望类型”误以为是在 `Inputs` 面板里手工选择

推荐命令模式：

```powershell
python scripts/validate_custom_node.py `
  --code-file temp\custom_node.hlsl `
  --output-type float3 `
  --input UV:float2 `
  --input Tex:texture2d `
  --input Radius:float
```

推荐的双层验证命令模式：

```powershell
python scripts/validate_custom_node_pipeline.py `
  --code-file temp\custom_node.hlsl `
  --output-type float3 `
  --input WorldPos:float3 `
  --input TimeSeconds:float `
  --project "D:\Path\YourProject.uproject" `
  --asset-path "/Game/Path/YourMaterial.YourMaterial"
```

这个双层验证脚本默认会把 Unreal 原始启动输出收敛掉，只保留：

- 当前执行的是哪一层
- 实际命令
- 最新日志路径
- `grep` 命中的关键日志

这样更适合快速判断“代码体语法通过了没有”和“工程内材质是否真的编译过了”。

## Resource Guide

读取 [`references/custom-node-doc-summary.md`](references/custom-node-doc-summary.md) 以获取：

- 官方文档字段解释
- 性能与限制摘要
- 生成代码时应遵守的 Unreal 约束
- Unreal `Inputs` 机制与实际调试经验

调用 [`scripts/validate_custom_node.py`](scripts/validate_custom_node.py) 以获取：

- 括号与 `return` 的基础静态检查
- HLSL 包装器生成
- 本地 `dxc` 离线编译结果
- 对采样宏、include 路径、输出类型的基本一致性检查

调用 [`scripts/validate_custom_node_pipeline.py`](scripts/validate_custom_node_pipeline.py) 以获取：

- `dxc` 静态验证
- Unreal 工程内 commandlet 验证
- 最新日志中的 `[CodexProbe]`、`MaterialEditorStats`、`error:`、`Shader debug info dumped`

调用 [`scripts/generate_custom_node_paste_export.py`](scripts/generate_custom_node_paste_export.py) 以获取：

- 可直接粘贴到 Unreal 材质编辑器的 `MaterialGraphNode_Custom` 导出文本
- 稳定的输入 pin / 输出 pin / Additional Outputs / Additional Defines 文本
- 基于 `seed` 的确定性 `Guid` / `PinId`

调用 [`scripts/render_custom_node_dual_blocks.py`](scripts/render_custom_node_dual_blocks.py) 以获取：

- 一段 `HLSL` 代码块
- 一段 `Material Editor Paste Export` 代码块
- 两段内容彼此保持输入 / 输出 pin 一致
- 可通过 `--output-file` 直接写成 `.md` 文件，供用户打开和复制

调用 [`scripts/emit_custom_node_artifacts.py`](scripts/emit_custom_node_artifacts.py) 以获取：

- 拆分后的 `HLSL Markdown`
- 按需生成的 `single-node paste markdown`
- 按需生成的 `full-graph markdown`
- 供直接返回给用户的完整绝对路径列表

读取 [`references/custom-node-paste-export-format.md`](references/custom-node-paste-export-format.md) 以获取：

- 这类 Unreal 粘贴文本到底是什么
- 单个 Custom Node 粘贴块的最小稳定字段
- 当前脚本已经覆盖和暂未覆盖的边界

调用 [`scripts/generate_custom_node_full_graph_export.py`](scripts/generate_custom_node_full_graph_export.py) 以获取：

- 包含 Custom Node 与常见外围源节点的完整材质节点组导出文本
- 基于 layout 配置的稳定 `LinkedTo` 连线
- 常见 `WorldPosition / CameraPositionWS / Time / ScalarParameter / Constant3Vector` 模板输出

读取 [`references/custom-node-full-graph-export-format.md`](references/custom-node-full-graph-export-format.md) 以获取：

- 完整节点组导出与单节点导出的区别
- 当前第一版完整节点组导出器的能力边界
- 为什么采用模板 + layout 的稳定生成方式

## Response Style

- 默认用中文说明。
- 默认优先返回拆分后的 `.md` 文件完整绝对路径，而不是在对话里直接展开超长代码块。
- 默认至少返回 `HLSL Markdown` 的完整绝对路径。
- 当用户要求单节点粘贴块时，再额外返回 `custom_node_paste.md` 的完整绝对路径。
- 当用户要求完整节点组时，再额外返回 `full_graph.md` 的完整绝对路径。
- 只有当用户明确要求“直接贴在对话里”时，才把代码块整段展开。
- 默认把输入和输出类型写完整，不要只写“接一个 UV 和一个纹理”。
- 默认同时写清楚“Input Name 列表”和“这些 pin 该接什么节点”。
- 默认保证各个输出文件里的输入 / 输出 pin 名称彼此一致。
- 默认把“类型来源”写清楚，例如：
  - `WorldPos`：在 `Inputs` 里新增这个名字，外部接 `Absolute World Position`，因此会表现为 `float3`
  - `TimeSeconds`：外部接 `Time` 或 `Game Time` 一类标量，因此会表现为 `float`
- 默认对世界空间参数给一句尺度提示，例如：
  - `WaveScale`：世界空间频率参数，手感受厘米世界影响
  - `Radius` / `Thickness` / `Falloff`：按厘米理解
- 默认把未说明的关键假设写出来，例如“假设 UV 范围为 0 到 1”“假设输出接到 Emissive”。
- 遇到世界空间效果时，默认把坐标系约定写出来，例如“此版本按 Unreal `Z-up` 编写，海面使用 `WorldPos.xy`，高度沿 `Z`”。
- 遇到依赖世界空间长度的效果时，默认补一句“Unreal 世界单位为厘米”，并据此解释 `WaveScale`、`Radius`、`Thickness`、`Falloff` 这类参数的手感。
- 对海洋、波浪、扫描圈、冲击波、世界空间噪声这类效果，默认附一段可直接复用的参数说明，优先采用下面这种风格：
  - `WaveScale`：世界空间频率，按厘米场景尺度调节
  - `Radius`：厘米
  - `Thickness`：厘米
  - `eps`：法线采样步长，厘米级偏移
- 如果用户只说“做一个某某效果”，先合理补全节点规格，再给出成品。
