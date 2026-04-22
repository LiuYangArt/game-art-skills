# Official VEX Guide

这个文件把 SideFX 官方 VEX 文档里对写 Wrangle 最有用的信息压缩成可操作摘要。

## 核心定位

- VEX 是 Houdini 的高性能表达语言，常见于 shader、Wrangle、CVEX、体积和粒子处理场景。
- Wrangle 节点里写的是 `CVEX` 片段，不等于完整 `.vfl` 程序。
- 上下文会决定哪些函数、语句和全局变量可用；不能脱离上下文生搬硬套。

官方入口：

- VEX 首页: https://www.sidefx.com/docs/houdini/vex/index.html
- Language reference: https://www.sidefx.com/docs/houdini/vex/lang.html
- Using VEX expressions: https://www.sidefx.com/docs/houdini/vex/snippets.html
- Functions index: https://www.sidefx.com/docs/houdini/vex/functions/
- Contexts: https://www.sidefx.com/docs/houdini/vex/contexts/index.html

## Wrangle 中最重要的语法约定

### 当前元素属性

在 Wrangle 里，当前元素的属性通常直接用 `@name` 访问。

常见例子：

- `@P` 位置
- `@N` 法线
- `@Cd` 颜色
- `@uv` uv
- `@pscale` 标量缩放
- `@orient` 朝向四元数

Houdini 对一部分常见属性知道默认类型，所以 `@Cd` 可以直接当 vector 用。
但对于不常见属性，或你希望代码更稳时，显式写类型前缀更清楚：

- `f@heat`
- `i@id`
- `v@vel`
- `s@name`
- `p@orient`

### 跨输入读取

访问其他输入时，不要依赖 `@` 的自动类型推断。
优先显式写类型，或用带类型返回值的变量承接：

```c
vector targetP = point(1, "P", @ptnum);
float mask = point(1, "mask", @ptnum);
```

官方文档明确指出：通过 `@opinputN_name` 访问其他输入时，自动类型推断不可靠，最好显式写类型。

### 参数读取

可调项优先暴露成节点参数：

```c
float freq = chf("freq");
int seed = chi("seed");
vector offset = chv("offset");
string group = chs("group");
float w = chramp("profile", t);
```

这比把数值硬编码进代码更适合迭代调参。

## 常用函数家族

### 属性与几何读写

- `point`, `prim`, `vertex`, `detail`
- `setpointattrib`, `setprimattrib`, `setvertexattrib`, `setdetailattrib`
- `addpoint`, `addprim`, `addvertex`, `removeprim`, `removepoint`

经验规则：

- 当前元素简单改值，优先 `@attrib`
- 任意元素或跨输入写值，优先 `set*attrib`
- 真正改拓扑时，使用 `add*` / `remove*`

### 位置与邻域

- `nearpoint`, `nearpoints`
- `pcfind`, `pcopen`, `pciterate`, `pcimport`
- `xyzdist`, `primuv`, `minpos`

常见用途：

- 最近点匹配
- 邻域平均
- 吸附到目标表面
- 点云查询

### 形状控制与映射

- `fit`, `fit01`, `fit10`, `fit11`, `clamp`, `smooth`
- `lerp`, `invlerp`, `chramp`

常见用途：

- 把空间范围映射到 0 到 1
- 用 ramp 做艺术控制
- 做 soft threshold 和 falloff

### 噪声与随机

- `rand`
- `noise`, `snoise`, `anoise`
- `curlnoise`, `curlxnoise`, `curlgxnoise`

经验规则：

- 标量随机优先 `rand`
- 位移/形变优先考虑 `noise` 或 `snoise`
- 流场、方向场优先考虑 `curlnoise`

### 体积

- `volumesample`, `volumepostoindex`, `volumeindex`, `volumegradient`

Volume Wrangle 里要特别注意：写普通 `@foo` 不等于帮你创建一个新 volume。

## 官方文档里值得记住的限制

- VEX 不支持递归。
- 运算符大体接近 C，但很多数学操作支持 vector、matrix 等非标量类型。
- 某些函数只在特定上下文可用，碰到报错要先怀疑上下文，而不是先怀疑语法。
- Wrangle 节点中直接写属性时，如果属性不存在，通常会创建该属性；但 volume 场景不应想当然套用这个规则。

## 写 Wrangle 时的默认检查清单

输出代码前至少自检一次：

1. 节点类型和 `Run Over` 是否一致。
2. 当前元素属性与跨输入属性是否区分清楚。
3. 属性类型是否明确。
4. 可调参数是否外提为 `ch*`。
5. 是否把读取结果真正回写到了目标属性。
6. 是否误用了当前上下文不可用的函数。