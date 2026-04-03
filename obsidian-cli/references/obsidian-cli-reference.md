# Obsidian CLI Reference (Windows)

## 1. 预检

```powershell
where.exe obsidian
obsidian help
obsidian vaults verbose
```

若 `where.exe obsidian` 无结果，说明命令入口未注入 PATH。

## 2. 常用命令模板（新语法）

说明：当前 CLI 使用 `key=value` 参数格式，不是 `--flag value`。

### 查看帮助

```powershell
obsidian help
obsidian help read
```

### 读取文件

```powershell
obsidian read vault="code-dev-vault" path="fd_prototype_docs/design/input.canvas"
```

### 打开文件

```powershell
obsidian open vault="code-dev-vault" path="fd_prototype_docs/design/input.canvas"
```

### 创建文件

```powershell
obsidian create vault="code-dev-vault" path="inbox/todo.md" content="# TODO`n- item"
```

### 搜索

```powershell
obsidian search vault="code-dev-vault" query="input" path="fd_prototype_docs" format="text"
```

### 读取今日笔记

```powershell
obsidian daily:path vault="code-dev-vault"
obsidian daily:read vault="code-dev-vault"
```

## 3. 从 `obsidian://` 高效提取内容

### 3.1 解码 URI 并读取目标文件

```powershell
$uri = "obsidian://open?vault=code-dev-vault&file=fd_prototype_docs%2Fdesign%2Finput.canvas"
$u = [System.Uri]$uri
$qs = [System.Web.HttpUtility]::ParseQueryString($u.Query)
$vault = $qs["vault"]
$file = [System.Uri]::UnescapeDataString($qs["file"])
obsidian read vault="$vault" path="$file"
```

### 3.2 `.canvas` 提取文本节点与附件节点

```powershell
$json = obsidian read vault="$vault" path="$file"
$canvas = $json | ConvertFrom-Json

# 文本节点
$canvas.nodes | Where-Object { $_.type -eq "text" } |
  Select-Object id, text

# 附件节点（通常是图片）
$assetNodes = $canvas.nodes | Where-Object { $_.type -eq "file" } |
  Select-Object id, file
```

### 3.3 解析 vault 根路径并校验附件存在性

```powershell
$cfg = "$env:APPDATA\Obsidian\obsidian.json"
$vaultPath = (
  Get-Content $cfg -Raw | ConvertFrom-Json
).vaults.PSObject.Properties.Value |
  Where-Object { $_.path -like "*\code-dev-vault" } |
  Select-Object -First 1 -ExpandProperty path

$assetNodes | ForEach-Object {
  $p = Join-Path $vaultPath $_.file
  [PSCustomObject]@{
    id = $_.id
    file = $_.file
    exists = Test-Path $p
    abs = $p
  }
}
```

## 4. URI 回退模式（CLI 不可用）

```powershell
& "$env:LOCALAPPDATA\Programs\Obsidian\Obsidian.exe" "obsidian://open?vault=<vault-name>"
& "$env:LOCALAPPDATA\Programs\Obsidian\Obsidian.exe" "obsidian://open?vault=<vault-name>&file=<vault-relative-path>"
```

## 5. 常见故障

- 终端提示“不是内部或外部命令”：
  - 确认已在 Obsidian 中开启 `Installer command line support`。
  - 重开终端与 Obsidian 后重试。
- 命令执行但找不到文件：
  - 先用 `obsidian files vault="<vault>" path="<folder>"` 验证相对路径。
  - 检查 URI 的 `file` 是否已 URL Decode。
- `.canvas` 有图片节点但图片无法读取：
  - 校验 `obsidian.json` 中 vault 路径是否匹配目标 vault。
  - 校验 `type=file` 节点的 `file` 路径是否仍存在于磁盘。
