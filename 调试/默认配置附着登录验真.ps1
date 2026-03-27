[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$helperPath = Join-Path $projectRoot "app_backend\debug\start_default_profile_attach_login_watch.ps1"

if (-not (Test-Path $helperPath)) {
    throw "未找到附着登录验真脚本：$helperPath"
}

& $helperPath
