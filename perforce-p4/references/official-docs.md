# Perforce 官方命令文档

当任务涉及不常用命令、复杂 flag、流分支语义差异，或者对 `merge` / `integrate` / `resolve` 行为没有把握时，先查官方文档，不要靠记忆猜。

## 官方入口

- 命令总索引: [Command reference](https://help.perforce.com/helix-core/server-apps/cmdref/current/Content/CmdRef/commands.html)
- 当前页标题验证: `Command reference`

## 推荐查找顺序

1. 先跑本地帮助: `p4 help <command>`
2. 再开官方总索引页，确认命令是否存在、是否有 graph 变体或相关命令
3. 进入具体命令页，重点看 `Syntax`、`Description`、`Options`、`Usage notes`、`Examples`
4. 若命令会改动 workspace 或 depot，先回到本地用 `-n` 或只读命令验证上下文

## 具体命令页规律

Perforce 官方命令页通常遵循这个命名：

```text
https://help.perforce.com/helix-core/server-apps/cmdref/current/Content/CmdRef/p4_<command>.html
```

例如：

- `p4 resolve`: [p4_resolve.html](https://help.perforce.com/helix-core/server-apps/cmdref/current/Content/CmdRef/p4_resolve.html)
- `p4 merge`: [p4_merge.html](https://help.perforce.com/helix-core/server-apps/cmdref/current/Content/CmdRef/p4_merge.html)
- `p4 integrate`: [p4_integrate.html](https://help.perforce.com/helix-core/server-apps/cmdref/current/Content/CmdRef/p4_integrate.html)
- `p4 interchanges`: [p4_interchanges.html](https://help.perforce.com/helix-core/server-apps/cmdref/current/Content/CmdRef/p4_interchanges.html)
- `p4 client`: [p4_client.html](https://help.perforce.com/helix-core/server-apps/cmdref/current/Content/CmdRef/p4_client.html)
- `p4 stream`: [p4_stream.html](https://help.perforce.com/helix-core/server-apps/cmdref/current/Content/CmdRef/p4_stream.html)
- `p4 branch`: [p4_branch.html](https://help.perforce.com/helix-core/server-apps/cmdref/current/Content/CmdRef/p4_branch.html)
- `p4 submit`: [p4_submit.html](https://help.perforce.com/helix-core/server-apps/cmdref/current/Content/CmdRef/p4_submit.html)
- `p4 revert`: [p4_revert.html](https://help.perforce.com/helix-core/server-apps/cmdref/current/Content/CmdRef/p4_revert.html)
- `p4 unshelve`: [p4_unshelve.html](https://help.perforce.com/helix-core/server-apps/cmdref/current/Content/CmdRef/p4_unshelve.html)

## 何时必须查官方页

这些场景不要只凭经验：

- 不确定 `merge` 和 `integrate` 在当前服务器版本下的语义差异
- 不确定某个 resolve flag 的含义和适用范围
- 需要处理 stream、branch spec、shelve、unshelve、copy 这类容易误用的命令
- 命令选项很多，而且错误参数可能放大影响范围
- 输出结果与预期不符，需要核对官方说明中的限制条件或前置条件

## 使用原则

- 本地 help 用来快速看语法；官方页用来确认语义和边界
- 不确认 flag 含义时，不要在真实 depot 上尝试写操作
- 复杂写操作前，优先使用 `-n`、`info`、`client -o`、`opened`、`interchanges` 之类的只读或预演命令
- 如果官方页和记忆冲突，以官方页为准