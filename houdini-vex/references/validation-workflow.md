# Validation Workflow

这份说明只回答一件事：Wrangle 里的 VEX 怎样才算“已经验证过”。

## 结论

对 `Attribute Wrangle` / `Point Wrangle` / `Primitive Wrangle` / `Volume Wrangle` 这类节点来说，最可信的验证不是纯文本 lint，也不是把片段硬包成 `.vfl` 后离线编译，而是：

1. 在真实 Houdini 会话里创建对应节点
2. 把 snippet 写进节点参数
3. 准备最小测试输入
4. 强制 `cook`
5. 读取节点错误和警告

原因很简单：Wrangle snippet 使用了节点上下文语法，例如：

- `@P`
- `@Cd`
- `@ptnum`
- `@primnum`
- `chf("freq")`
- `chramp("mask_ramp", t)`

这些写法并不等价于完整的独立 `.vfl` 文件。

## 推荐命令

默认先验证最常见的点级 Attribute Wrangle：

```powershell
python scripts/validate_vex.py --code-file temp\snippet.vfl --node-type attribwrangle --run-over points
```

如果是 primitive/detail/vertex：

```powershell
python scripts/validate_vex.py --code-file temp\snippet.vfl --node-type attribwrangle --run-over primitives
python scripts/validate_vex.py --code-file temp\snippet.vfl --node-type attribwrangle --run-over detail
python scripts/validate_vex.py --code-file temp\snippet.vfl --node-type attribwrangle --run-over vertices
```

如果是 Volume Wrangle：

```powershell
python scripts/validate_vex.py --code-file temp\snippet.vfl --node-type volumewrangle
```

## 脚本会做什么

`validate_vex.py` 会：

- 自动寻找本机 `hython`
- 创建临时 Houdini 场景和测试网络
- 给 `attribwrangle` 准备一个最小 polygon 输入
- 给 `volumewrangle` 准备一个最小 volume 输入
- 解析代码里的常见 `chf` / `chi` / `chv` / `chs` / `chramp` 引用，并自动补建常见 spare parms
- 对目标节点执行真实 `cook`
- 返回成功/失败、节点警告、节点错误和临时 `.hip` 路径

## 这层验证能证明什么

验证通过后，可以合理说：

- 这段代码在当前机器的 Houdini 节点上下文里能编译
- 最小测试网络能 `cook`
- 常见参数引用至少没有把节点直接编挂

## 这层验证不能证明什么

验证通过不等于：

- 艺术效果完全正确
- 在用户真实生产场景里一定满足预期
- 性能一定足够好
- 所有特殊输入拓扑都能工作

所以工作顺序应当是：

1. 先过验证，保证“语法对、节点能跑”
2. 再根据结果继续迭代效果

## 当前边界

当前脚本优先覆盖：

- `Attribute Wrangle`
- `Volume Wrangle`

`POP Wrangle` / 其他 DOP 场景通常还依赖更完整的仿真网络和时间步环境，必要时应在真实项目里补做二次验证，而不是假装一个极小 DOP 网络就足够。

如果本机没有 `hython`，脚本会明确失败并提示路径发现结果。这时可以继续写代码草案，但不能宣称“已验证可运行”。