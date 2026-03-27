[CmdletBinding()]
param(
    [int]$Port = 9223,
    [string]$ProfileRoot = "",
    [string]$LoginUrl = "https://www.c5game.com/user/user/",
    [switch]$KeepProfile,
    [int]$LoginTimeoutSeconds = 600,
    [int]$PollIntervalMilliseconds = 1500
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path

if (-not $ProfileRoot) {
    $ProfileRoot = Join-Path $projectRoot "data\debug-clean-edge-profile"
}

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

Get-Process msedge -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 800

if ((Test-Path $ProfileRoot) -and (-not $KeepProfile)) {
    Remove-Item -Recurse -Force $ProfileRoot
}
New-Item -ItemType Directory -Force -Path $ProfileRoot | Out-Null

$env:C5_EDGE_DEBUGGER_ADDRESS = "127.0.0.1:$Port"
$edgeArgs = @(
    "--remote-debugging-port=$Port",
    "--remote-allow-origins=*",
    "--user-data-dir=$ProfileRoot",
    "--profile-directory=Default",
    "--disable-extensions",
    "--no-first-run",
    "--no-default-browser-check",
    "--new-window",
    $LoginUrl
)

Start-Process -FilePath $edgePath -ArgumentList $edgeArgs | Out-Null

$deadline = (Get-Date).AddSeconds(20)
$portReady = $false
while ((Get-Date) -lt $deadline) {
    try {
        $null = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/json/version"
        $portReady = $true
        break
    } catch {
        Start-Sleep -Milliseconds 300
    }
}

if (-not $portReady) {
    throw "等待 Edge 调试端口超时：127.0.0.1:$Port"
}

Write-Host "已启动纯净 Edge profile。"
Write-Host "ProfileRoot: $ProfileRoot"
Write-Host "C5_EDGE_DEBUGGER_ADDRESS=$($env:C5_EDGE_DEBUGGER_ADDRESS)"
Write-Host "当前已禁用扩展。请在打开的浏览器里完成 C5 登录。"
Write-Host "吾将自动轮询当前会话，直到检测到 NC5_accessToken 或超时。"

Set-Location $projectRoot
$deadline = (Get-Date).AddSeconds($LoginTimeoutSeconds)
$lastJson = ""

while ((Get-Date) -lt $deadline) {
    try {
        $jsonOutput = & $pythonPath -m app_backend.debug.read_local_edge_session --debugger-address "127.0.0.1:$Port" 2>&1
        $jsonText = ($jsonOutput | Out-String).Trim()
        if ($jsonText) {
            $lastJson = $jsonText
            $payload = $jsonText | ConvertFrom-Json
            if ($payload.has_cookie_raw -and ($payload.cookie_raw_preview -match 'NC5_accessToken=')) {
                Write-Output $jsonText
                exit 0
            }
        }
    } catch {
        $lastJson = ($_ | Out-String).Trim()
    }
    Start-Sleep -Milliseconds $PollIntervalMilliseconds
}

if ($lastJson) {
    Write-Output $lastJson
}
throw "等待登录态超时：${LoginTimeoutSeconds}秒内未检测到 NC5_accessToken"
