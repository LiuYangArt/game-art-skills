# Unreal Custom Node 官方文档速记

来源：

- Epic Games 官方文档：<https://dev.epicgames.com/documentation/en-us/unreal-engine/custom-material-expressions-in-unreal-engine>

## 核心结论

- `Custom Material Expression` 允许在材质里直接写“纯 shader 代码”。
- 节点的核心配置不只有 `Code`，还包括 `Output Type`、`Inputs`、`Additional Outputs`、`Additional Defines`、`Include File Paths`、`Desc`。
- 官方示例展示了通过纹理对象输入和自动生成的 sampler 名称做采样的写法，这也是最稳妥的默认习惯用法。

## Unreal 世界约定

这部分不是该页官方文档的主旨，但对写 Custom Node 非常重要：

- Unreal 常见世界坐标约定是 `Z-up`
- 水平地面/海面通常落在 `XY`
- 默认世界长度单位是厘米

这对生成器的直接影响：

- ShaderToy 或其他 `Y-up` 示例迁进 Unreal 时，常常需要把“高度轴”改成 `Z`
- 使用 `Absolute World Position` 做程序化纹理时，要明确自己是在 `XY`、`XZ` 还是 `YZ` 平面上计算
- 涉及世界空间尺度的参数必须按厘米解释，不要把数值说明写得过于抽象

## 节点字段含义

### Code

- 填写实际 HLSL 代码内容。
- 对这个技能来说，默认输出可直接粘贴进 Unreal `Code` 字段的代码体。

### Output Type

- 明确节点主输出的数据类型。
- 生成时必须提前定死，而不是让用户自己猜。

### Inputs

- 官方概念上每个输入都有名称和类型。
- 但在 Unreal 编辑器里，Custom Node 的 `Inputs` 面板常见可编辑项主要是 `Input Name`。
- 实际类型往往由外部连进该 pin 的表达式推导，而不是在 `Inputs` 面板里像 `Output Type` 那样手选。
- 代码里直接通过输入名称访问对应值。
- 名称设计很重要，含义要稳定、直观、避免冲突。

这对生成器很关键：

- 输出给用户时，不要写成“在 Inputs 里选择 Float3 / Float”。
- 应写成“新增一个名为 `WorldPos` 的输入，并把 `Absolute World Position` 接到它，所以它会表现为 `float3`”。

### Additional Outputs

- 用于额外输出 pin。
- 只有当用户真的需要多路结果时才启用，否则优先保持单输出。

### Additional Defines

- 用于传入预处理宏。
- 对固定迭代次数、开关常量、平台分支之类逻辑很有价值。

### Include File Paths

- 这里填的是可供 `#include` 搜索的目录，而不是代码片段本身。
- 如果生成的代码里出现 `#include`，必须同时考虑这里的目录配置。

### Desc

- 这是节点说明文字。
- 适合用来写一句短描述，帮助在材质图里回忆节点职责。

## 官方文档里特别重要的两个提醒

### 性能提醒

- 官方明确指出：使用 Custom Node 会阻止常量折叠。
- 这意味着一些原本可在材质图中被提前优化掉的常量表达式，在 Custom Node 中可能保留为实际运行时代码。
- 因此，简单数学逻辑不应默认放进 Custom Node；但在用户明确要求 Custom Node 时，仍然可以输出，只需要顺手提醒性能代价。

### 已知问题

- 输入参数名如果与材质里其他参数名撞名，可能出现编译问题。
- 数组不受支持。

对这个技能的直接影响：

- 生成输入名时，优先使用语义清晰且低冲突的名字。
- 需要数组语义时，改成展开、固定循环或 define 驱动的上限。

## 本次工程内调试补充经验

这部分不是官方文档原文，而是基于 Unreal 5.5 工程内真实验证得到的经验。

### `dxc` 通过不等于 Unreal 一定通过

- 离线 `dxc` 可以证明 Custom Node 代码体在包装环境下语法成立。
- 但 Unreal 真正失败时，常见原因不是 HLSL 本身错，而是：
  - Custom Node `Inputs` 没建全
  - 输入名和代码变量名不一致
  - 外部没有接线，导致 UE 侧没有为该名字生成可用变量
  - ShaderToy/GLSL 的坐标空间或方向约定没有转成 Unreal 版本

### 识别“接口没配齐”的典型报错

如果日志里出现这种模式：

- `use of undeclared identifier 'WorldPos'`
- `use of undeclared identifier 'WaveScale'`
- `use of undeclared identifier 'SkyColor'`

而这些名字恰好都是你 Custom Node 代码里用到的输入变量，那么优先怀疑：

- 输入 pin 根本没在节点里创建
- 名字拼写不一致
- 忘了接外部节点

在给用户最终答案时，最好把这层关系写成两段，而不是一句糊过去：

- `Inputs` 面板里新增哪些名字
- 材质图外部每个 pin 实际接什么节点，所以 UE 会把它推导成什么类型

这样最能避免“代码看着对，但 UE 里还是 undeclared identifier”的回归。

### 坐标系迁移要显式写明

- 很多 ShaderToy 海面示例默认 `Y-up`，海面平面常写在 `XZ`。
- Unreal 常见世界约定是 `Z-up`。
- Unreal 默认长度单位是厘米。
- 因此把 ShaderToy 风格效果迁进 Unreal 时，常需要把：
  - `WorldPos.xz` 改成 `WorldPos.xy`
  - “高度方向”从 `Y` 改成 `Z`
  - 地平线、法线重建、视角判断里的 `v.y` 改成 `v.z`

同时要重新审视所有与距离有关的参数：

- `eps`
- `Radius`
- `Thickness`
- `WaveScale`
- `Falloff`

因为它们在 Unreal 世界里最终都会和“厘米”产生直觉绑定。

更实用一点的写法是，直接把这些参数的“UE 手感”写给用户：

- `WaveScale`：世界空间频率，数值越大代表单位距离内波形越密；在厘米世界里通常不适合照搬 ShaderToy 原值
- `WaveLength`：世界空间波长，按厘米理解；值越大波峰间距越大
- `HeightScale` / `Amplitude`：波高或位移幅度；若沿 `Z` 推高，默认按厘米理解
- `Radius` / `Thickness` / `Falloff`：直接按厘米理解
- `eps`：法线重建或导数近似时使用的采样偏移，通常也是厘米级步长

如果是给最终用户的说明，推荐不要只列参数名，最好顺手把调参直觉也写出来，例如：

- `WaveScale`：世界空间频率，按厘米场景尺度调节；值越大，波纹越密
- `Radius`：影响范围，厘米
- `Thickness`：边缘厚度，厘米
- `Falloff`：过渡带宽，厘米；值越大过渡越柔
- `eps`：法线采样步长，厘米级偏移；太大容易变钝，太小容易抖

## 对生成器最有用的实践化规则

- 先定 `Output Type`，再写代码。
- 先定 `Inputs`，再决定变量名。
- 纹理采样默认使用 `TextureObject + UV + 自动 sampler` 的模式。
- 复杂逻辑优先写成清晰的局部变量步骤，不要把所有计算塞进一行。
- 除非用户明确要求多输出，否则保持单输出 Custom Node。
- 如果代码依赖 include 或宏定义，必须同时输出对应配置，不能只给 `Code`。
