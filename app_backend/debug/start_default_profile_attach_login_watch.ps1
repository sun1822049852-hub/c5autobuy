[CmdletBinding()]
param(
    [int]$Port = 9222,
    [string]$ProfileDirectory = "Default",
    [string]$UserDataDir = "$env:LOCALAPPDATA\Microsoft\Edge\User Data",
    [string]$RemarkName = "登录验真-attach",
    [double]$TimeoutSeconds = 900
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$edgeCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
    (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe")
)
$edgePath = $edgeCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $edgePath) {
    throw "未找到 Microsoft Edge 可执行文件。"
}

$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
    throw "未找到项目虚拟环境 Python：$pythonPath"
}

if (Get-Process msedge -ErrorAction SilentlyContinue) {
    throw "请先关闭所有 Edge 窗口，再运行本脚本。"
}

$env:C5_EDGE_DEBUGGER_ADDRESS = "127.0.0.1:$Port"
$loginUrl = "https://www.c5game.com/login?return_url=%2Fuser%2Fuser%2F"
$edgeArgs = @(
    "--remote-debugging-port=$Port",
    "--user-data-dir=$UserDataDir",
    "--profile-directory=$ProfileDirectory",
    $loginUrl
)

Start-Process -FilePath $edgePath -ArgumentList $edgeArgs | Out-Null

$deadline = (Get-Date).AddSeconds(15)
$portReady = $false
while ((Get-Date) -lt $deadline) {
    try {
        $null = Invoke-WebRequest "http://127.0.0.1:$Port/json/version" -UseBasicParsing
        $portReady = $true
        break
    } catch {
        Start-Sleep -Milliseconds 300
    }
}

if (-not $portReady) {
    throw "等待 Edge 调试端口超时：127.0.0.1:$Port"
}

Write-Host "已启动 Default profile attach 浏览器。"
Write-Host "C5_EDGE_DEBUGGER_ADDRESS=$($env:C5_EDGE_DEBUGGER_ADDRESS)"
Write-Host "项目目录: $projectRoot"
Write-Host "登录验真会在当前 PowerShell 会话中直接运行。"

Set-Location $projectRoot
& $pythonPath -m app_backend.debug.login_e2e_watch --remark-name $RemarkName --timeout $TimeoutSeconds
exit $LASTEXITCODE
