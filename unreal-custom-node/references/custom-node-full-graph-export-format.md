# Unreal Custom Node 完整节点组导出格式速记

这份说明基于 `custom_node_full.md` 这种 Unreal 材质编辑器整组节点复制文本整理而来。

目标不是覆盖 Unreal 全部材质表达式，而是为“围绕 Custom Node 自动生成一组常见外围节点”的脚本化提供稳定边界。

## 和单节点导出相比，多了什么

单节点导出主要只有：

- `MaterialGraphNode_Custom`
- `MaterialExpressionCustom`
- 输入 / 输出 pin

完整节点组导出则额外包含：

- 外围源节点，例如 `WorldPosition`、`CameraPositionWS`、`Time`
- 参数节点，例如 `ScalarParameter`、`Constant3Vector`
- 辅助节点，例如 `MaterialFunctionCall(MakeFloat3)`
- `LinkedTo=(...)` 连线关系

也就是说，它本质上是一个“小型材质图”，不是只有一个节点。

## 当前最值得优先脚本化的节点类型

根据样本和当前 Custom Node 工作流，最常见、最值得优先做模板化的是：

- `MaterialExpressionWorldPosition`
- `MaterialExpressionCameraPositionWS`
- `MaterialExpressionTime`
- `MaterialExpressionScalarParameter`
- `MaterialExpressionConstant3Vector`
- `MaterialExpressionMaterialFunctionCall`

这些已经能覆盖大量“世界空间程序化效果 + 少量辅助拼接”的材质结构。

## 当前脚本策略

完整节点组导出器不直接从任意材质图反向推断，而是使用“模板 + layout 配置”方式生成。

这样做的原因是：

- 更稳定
- 更容易保证 pin 名和连线一致
- 更容易和 Custom Node HLSL 生成结果保持同步

## 当前边界

当前完整节点组导出脚本的第一版重点是：

- 围绕一个 `Custom Node` 自动生成常见外围源节点
- 自动连接到指定输入 pin
- 保持 `Guid / PinId / LinkedTo` 可重复生成

当前还没有覆盖：

- 任意材质表达式的通用建模
- 复杂函数链
- 多个 Custom Node 之间的任意图结构
- 自动推导最佳布局

所以更准确地说，它是“常见 Custom Node 材质模板导出器”，不是“Unreal 任意材质图导出器”。
