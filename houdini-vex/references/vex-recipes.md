# VEX Recipes

下面是更贴近游戏美术和程序化建模场景的稳定配方。优先把这些当成模式库，而不是逐次从零发明。

## 1. 按高度做颜色和缩放

适合地形、散点、碎片渐变。

```c
float miny = chf("miny");
float maxy = chf("maxy");
float t = fit(@P.y, miny, maxy, 0.0, 1.0);
t = clamp(t, 0.0, 1.0);
@Cd = chramp("color_ramp", t);
@pscale = fit01(chramp("scale_ramp", t), chf("minscale"), chf("maxscale"));
```

## 2. 用噪声推动位移

适合地表起伏、破碎边缘、风吹感。

```c
float freq = chf("freq");
float amp = chf("amp");
vector offset = chv("offset");
vector n = noise((@P + offset) * freq);
@P += (n - 0.5) * amp;
```

如果用户要求沿法线位移，改成：

```c
float n = noise(@P * chf("freq"));
@P += @N * ((n - 0.5) * chf("amp"));
```

## 3. 稳定随机化实例属性

适合 copy to points、植被、散件。

```c
int seed = chi("seed");
float r = rand(@ptnum + seed);
@pscale = fit01(r, chf("minscale"), chf("maxscale"));
@Cd = lerp(chv("color_a"), chv("color_b"), r);
```

如果几何会重排点号，优先改用稳定 id：

```c
float r = rand(i@id + chi("seed"));
```

## 4. 基于邻域做聚集或排斥

适合群集、结块、吸附趋势。

```c
float radius = chf("radius");
int maxpts = chi("maxpts");
int pts[] = nearpoints(0, @P, radius, maxpts);
vector avg = 0;
int count = 0;
foreach (int pt; pts)
{
    if (pt == @ptnum) continue;
    avg += point(0, "P", pt);
    count++;
}
if (count > 0)
{
    avg /= count;
    @P = lerp(@P, avg, chf("blend"));
}
```

## 5. 吸附到另一输入表面

适合包裹、投射、贴附。

```c
int prim;
vector uv;
float dist = xyzdist(1, @P, prim, uv);
vector hitP = primuv(1, "P", prim, uv);
vector hitN = primuv(1, "N", prim, uv);
@P = lerp(@P, hitP, chf("snap_blend"));
@N = normalize(lerp(@N, hitN, chf("normal_blend")));
f@dist = dist;
```

## 6. 生成 mask 供后续节点使用

适合把复杂效果拆成“先算 mask，再用节点链消费”。

```c
float radius = chf("radius");
vector center = chv("center");
float d = distance(@P, center);
float t = 1.0 - smooth(radius * 0.8, radius, d);
f@mask = clamp(t, 0.0, 1.0);
```

## 7. 体积采样驱动属性

适合烟雾场、SDF 驱动、贴体效果。

```c
float dens = volumesample(1, "density", @P);
@Cd = lerp(chv("cold"), chv("hot"), dens);
@pscale = fit(clamp(dens, 0.0, 1.0), 0.0, 1.0, chf("minscale"), chf("maxscale"));
```

## 常见取舍

- 只改当前元素属性：优先 `@attrib`
- 需要跨输入或随机访问：优先 `point/prim/detail` + 明确类型
- 需要艺术控制：优先 `chramp`
- 需要稳定随机：优先 `id`，其次 `ptnum`
- 需要可控分布：优先先产出 `mask` 或中间属性，再交给后续节点

## 常见坑

- 直接用 `@ptnum` 做随机种子，重拓扑后结果会跳。
- 忘了 `clamp` 或 `smooth`，导致 mask 超界。
- 在 primitive/detail 上下文里照抄 point wrangle 逻辑。
- 读了别的输入，但没说明第 2 输入应该接什么。
- 只算了局部变量，没有回写到 `@P`、`@Cd`、`f@mask` 等最终属性。