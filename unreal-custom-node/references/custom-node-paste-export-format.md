# Unreal Custom Node 粘贴导出格式速记

这份说明不是 Epic 官方文档原文，而是基于 Unreal 材质编辑器的复制/粘贴文本格式，以及本地样本 `custom_node_bp_node.md` 整理出来的实践说明。

目标不是描述整个材质图序列化系统，而是沉淀一条“稳定输出单个 Custom Node 粘贴块”的最小规则集。

## 这类文本到底是什么

当你在 Unreal 材质编辑器里复制一个节点，再粘贴到文本编辑器里，会得到一段对象导出文本。

对 Custom Node 来说，核心通常是两层对象：

- `MaterialGraphNode_Custom`
- 内嵌的 `MaterialExpressionCustom`

用户以后如果要求“除了 HLSL，再给我一份可以直接粘到材质编辑器里的节点代码”，默认就是指这种文本。

在当前技能的目标工作流里，这份文本已经不是“可选附加产物”，而是默认和 HLSL 同步输出的第二段代码块。

## 最小稳定字段

对单个 Custom Node 而言，最重要的是这些字段：

- `Code`
- `OutputType`
- `Inputs(n)`
- `AdditionalOutputs(n)`
- `AdditionalDefines(n)`
- `MaterialExpressionEditorX/Y`
- `MaterialExpressionGuid`
- `Outputs(n)`
- `NodePosX/Y`
- `NodeGuid`
- `CustomProperties Pin (...)`

其中：

- `Inputs(n)` 决定 Custom Node 面板里有哪些输入名
- `Outputs(n)` 与输出 pin 名称对应
- `CustomProperties Pin` 决定图里真正可连接的输入/输出 pin

这三层必须彼此一致，否则粘进去后很容易出现 pin 名不对、额外输出不显示、或节点状态异常。

## 关于类型

主输出和额外输出用的是 Unreal 的 `CMOT_*` 枚举文本，例如：

- `CMOT_Float1`
- `CMOT_Float2`
- `CMOT_Float3`
- `CMOT_Float4`
- `CMOT_MaterialAttributes`

和前面 HLSL 技能里常说的 `float / float2 / float3 / float4` 是一一对应关系。

## 关于输入

要特别记住一点：

- 这份粘贴文本里可以声明 `Inputs(n)=(InputName="WorldPos")`
- 但这并不等于“在这里直接锁定了 float3 类型”

和 Unreal 编辑器里的行为一样，输入实际类型仍然主要由外部连接表达式决定。

所以输出这类文本时，最好仍然配套说明：

- `Inputs` 列表里新增哪些名字
- 外部各 pin 应该接什么节点
- 因此 UE 会把它推导成什么类型

## 当前脚本的边界

当前脚本优先解决的是：

- 生成单个 `Custom Node` 的可粘贴导出块
- 稳定包含输入 pin、主输出 pin、额外输出 pin、宏定义、代码体和节点坐标

技能默认应保证两件事同时成立：

- HLSL 代码块里用到的输入 / 输出规格
- 粘贴导出块里声明出来的输入 / 输出 pin

必须彼此一致。不能出现“代码里用了 `WorldPos`，导出块里却没这个 pin”的情况。

当前还没有自动生成：

- `ScalarParameter`
- `VectorParameter`
- `Time`
- `AbsoluteWorldPosition`
- 这些外围节点与 Custom Node 的 `LinkedTo` 连接关系

如果未来用户明确要“整套节点图复制粘贴块”，可以在此基础上再扩展为多节点导出器。
