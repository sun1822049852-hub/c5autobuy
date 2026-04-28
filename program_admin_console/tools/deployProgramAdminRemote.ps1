param(
  [string]$RemoteHost = "8.138.39.139",
  [string]$RemoteUser = "admin",
  [string]$IdentityFile = "C:/Users/18220/.ssh/c5_ecs_deploy_temp",
  [string]$RemoteContainerName = "c5-program-admin",
  [string]$RemoteSourceDir = "/home/admin/c5-program-admin-src",
  [string]$RemotePrivateKeyPath = "/home/admin/c5-program-admin-runtime/keys/entitlement-private.pem",
  [string]$RemoteUploadDir = "/home/admin",
  [string]$LocalProjectDir = "",
  [string]$RuntimeDir = "",
  [string]$PythonPath = "C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe",
  [string]$BaseUrl = "https://8.138.39.139",
  [string]$CaCertPath = "",
  [string]$SshPath = "",
  [string]$ScpPath = "",
  [string]$SshWrapperScript = "",
  [string]$ScpWrapperScript = "",
  [switch]$DryRun,
  [switch]$SkipHttpsSmoke
)

$ErrorActionPreference = "Stop"

function Assert-PathExists {
  param(
    [string]$PathValue,
    [string]$Label
  )

  if (-not (Test-Path -LiteralPath $PathValue)) {
    throw "$Label was not found: $PathValue"
  }
}

function Get-NodePath {
  $command = Get-Command node -ErrorAction SilentlyContinue
  if (-not $command) {
    throw "node was not found for wrapper-script execution."
  }
  return $command.Source
}

function Resolve-CommandPath {
  param(
    [string]$ExplicitPath,
    [string]$CommandName
  )

  if ($ExplicitPath) {
    return $ExplicitPath
  }
  $command = Get-Command $CommandName -ErrorAction SilentlyContinue
  if (-not $command) {
    throw "$CommandName was not found."
  }
  return $command.Source
}

function Get-ToolLaunchConfig {
  param(
    [string]$ExplicitPath,
    [string]$CommandName,
    [string]$WrapperScript
  )

  if ($WrapperScript) {
    Assert-PathExists -PathValue $WrapperScript -Label "$CommandName wrapper script"
    return @{
      Path = Get-NodePath
      Args = @($WrapperScript)
    }
  }

  return @{
    Path = Resolve-CommandPath -ExplicitPath $ExplicitPath -CommandName $CommandName
    Args = @()
  }
}

function Invoke-Process {
  param(
    [string]$FilePath,
    [string[]]$Arguments,
    [string]$InputText = ""
  )

  $quotedArgs = @()
  foreach ($argument in $Arguments) {
    $text = [string]$argument
    if ($text -notmatch '[\s"]') {
      $quotedArgs += $text
      continue
    }
    $quotedArgs += '"' + ($text -replace '"', '\"') + '"'
  }

  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FilePath
  $psi.Arguments = [string]::Join(" ", $quotedArgs)
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.RedirectStandardInput = $InputText -ne ""
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true

  $process = New-Object System.Diagnostics.Process
  $process.StartInfo = $psi
  [void]$process.Start()
  if ($InputText -ne "") {
    $process.StandardInput.Write($InputText)
    $process.StandardInput.Close()
  }
  $stdout = $process.StandardOutput.ReadToEnd()
  $stderr = $process.StandardError.ReadToEnd()
  $process.WaitForExit()

  if ($process.ExitCode -ne 0) {
    $detail = ($stderr.Trim(), $stdout.Trim() | Where-Object { $_ }) -join [Environment]::NewLine
    if (-not $detail) {
      $detail = "command exited with code $($process.ExitCode)"
    }
    throw $detail
  }

  return $stdout
}

function Invoke-ExternalTool {
  param(
    [hashtable]$Config,
    [string[]]$Arguments,
    [string]$InputText = ""
  )

  $allArgs = @($Config.Args + $Arguments)
  return Invoke-Process -FilePath $Config.Path -Arguments $allArgs -InputText $InputText
}

function Quote-Bash {
  param([string]$Value)

  $quote = [char]39
  $escaped = $Value -replace [regex]::Escape($quote), ($quote + '"' + $quote + '"' + $quote)
  return $quote + $escaped + $quote
}

function Normalize-RemoteInspectPayload {
  param([string]$Payload)

  $parsed = $Payload | ConvertFrom-Json
  if ($parsed -is [System.Array]) {
    $parsed = $parsed[0]
  }

  if ($parsed.HostConfig) {
    return @{
      Binds = @($parsed.HostConfig.Binds)
      Env = @($parsed.Config.Env)
      PortBindings = $parsed.HostConfig.PortBindings
      Image = [string]$parsed.Config.Image
      RestartPolicy = [string]$parsed.HostConfig.RestartPolicy.Name
    }
  }

  return @{
    Binds = @($parsed.binds)
    Env = @($parsed.env)
    PortBindings = $parsed.portBindings
    Image = [string]$parsed.image
    RestartPolicy = [string]$parsed.restartPolicy
  }
}

function Get-EnvMap {
  param([string[]]$EnvList)

  $map = [ordered]@{}
  foreach ($entry in $EnvList) {
    $text = [string]$entry
    $index = $text.IndexOf("=")
    if ($index -lt 0) {
      continue
    }
    $name = $text.Substring(0, $index)
    $value = $text.Substring($index + 1)
    if ($name -match "^(PROGRAM_ADMIN_|MAIL_FROM$|MAIL_FROM_NAME$|QQ_SMTP_)") {
      $map[$name] = $value
    }
  }
  return $map
}

function Get-RemoteDerivedSigningKid {
  param(
    [hashtable]$SshConfig,
    [string]$IdentityFilePath,
    [string]$Target,
    [string]$RemoteKeyPath
  )

  $script = @'
import base64
import hashlib
import sys
from cryptography.hazmat.primitives import serialization

with open(sys.argv[1], "rb") as handle:
    pem = handle.read()

private_key = serialization.load_pem_private_key(pem, password=None)
public_der = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)
fingerprint = base64.urlsafe_b64encode(hashlib.sha256(public_der).digest()).decode("ascii").rstrip("=")
print("ed25519:" + fingerprint[:32], end="")
'@
  $remoteCommand = "python3 -c {0} {1}" -f (Quote-Bash $script), (Quote-Bash $RemoteKeyPath)
  return (Invoke-ExternalTool -Config $SshConfig -Arguments @(
    "-i", $IdentityFilePath,
    "-o", "BatchMode=yes",
    "-o", "StrictHostKeyChecking=accept-new",
    $Target,
    "bash -lc $(Quote-Bash $remoteCommand)"
  )).Trim()
}

function Get-LoopbackSmokeScript {
  param([string]$LocalAdminBaseUrl)

  return @"
set -euo pipefail
python3 - <<'PY'
import json
import urllib.error
import urllib.request
urls = [
  '$LocalAdminBaseUrl/api/health',
  '$LocalAdminBaseUrl/api/admin/session',
  '$LocalAdminBaseUrl/admin',
  '$LocalAdminBaseUrl/admin/app.js',
  '$LocalAdminBaseUrl/admin/styles.css',
  '$LocalAdminBaseUrl/api/auth/register/capability',
]
for url in urls:
  with urllib.request.urlopen(url, timeout=15) as response:
    print(url)
    print(response.status)
legacy_req = urllib.request.Request(
  '$LocalAdminBaseUrl/api/auth/email/send-code',
  data=json.dumps({'email': 'legacy-smoke@example.com'}).encode('utf-8'),
  headers={'Content-Type': 'application/json'},
  method='POST',
)
try:
  urllib.request.urlopen(legacy_req, timeout=15)
  raise SystemExit('/api/auth/email/send-code should be unavailable')
except urllib.error.HTTPError as exc:
  print('$LocalAdminBaseUrl/api/auth/email/send-code')
  print(exc.code)
  if exc.code not in (404, 405):
    raise
PY
"@
}

if (-not $LocalProjectDir) {
  $LocalProjectDir = (Resolve-Path (Join-Path (Split-Path -Parent $PSCommandPath) "..")).Path
} else {
  $LocalProjectDir = (Resolve-Path $LocalProjectDir).Path
}

$repoRoot = (Resolve-Path (Join-Path $LocalProjectDir "..")).Path

if (-not $RuntimeDir) {
  $RuntimeDir = Join-Path $repoRoot ".runtime"
}

if (-not $CaCertPath) {
  $CaCertPath = Join-Path $repoRoot "app_desktop_web/build/control_plane_ca.pem"
}

Assert-PathExists -PathValue $IdentityFile -Label "SSH identity file"
Assert-PathExists -PathValue $LocalProjectDir -Label "Local project directory"

$sshLaunch = Get-ToolLaunchConfig -ExplicitPath $SshPath -CommandName "ssh" -WrapperScript $SshWrapperScript
$target = "{0}@{1}" -f $RemoteUser, $RemoteHost

$inspectRaw = Invoke-ExternalTool -Config $sshLaunch -Arguments @(
  "-i", $IdentityFile,
  "-o", "BatchMode=yes",
  "-o", "StrictHostKeyChecking=accept-new",
  $target,
  "sudo docker inspect $RemoteContainerName"
)
$remoteState = Normalize-RemoteInspectPayload -Payload $inspectRaw

$envMap = Get-EnvMap -EnvList $remoteState.Env
$currentSigningKid = [string]$envMap["PROGRAM_ADMIN_SIGNING_KID"]
$derivedSigningKid = Get-RemoteDerivedSigningKid -SshConfig $sshLaunch -IdentityFilePath $IdentityFile -Target $target -RemoteKeyPath $RemotePrivateKeyPath
$envMap["PROGRAM_ADMIN_SIGNING_KID"] = $derivedSigningKid

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$imageTag = "c5-program-admin:deploy-$timestamp"
$localTarPath = Join-Path $RuntimeDir "program_admin_console_deploy_$timestamp.tar.gz"
$remoteTarPath = "$RemoteUploadDir/$(Split-Path $localTarPath -Leaf)"
$remoteDeployScriptPath = "$RemoteUploadDir/deploy_program_admin_remote_$timestamp.sh"
$localAdminBaseUrl = "http://127.0.0.1:18787"

if ($DryRun) {
  Write-Output "REMOTE_HOST=$RemoteHost"
  Write-Output "REMOTE_CONTAINER=$RemoteContainerName"
  Write-Output "REMOTE_SOURCE_DIR=$RemoteSourceDir"
  Write-Output "REMOTE_PRIVATE_KEY_PATH=$RemotePrivateKeyPath"
  Write-Output "CURRENT_IMAGE=$($remoteState.Image)"
  Write-Output "CURRENT_SIGNING_KID=$currentSigningKid"
  Write-Output "DERIVED_SIGNING_KID=$derivedSigningKid"
  Write-Output "BUILD_IMAGE=$imageTag"
  Write-Output "LOCAL_PROJECT_DIR=$LocalProjectDir"
  Write-Output "LOCAL_TARBALL=$localTarPath"
  Write-Output "REMOTE_TARBALL=$remoteTarPath"
  Write-Output "HTTPS_BASE_URL=$BaseUrl"
  exit 0
}

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

$scpLaunch = Get-ToolLaunchConfig -ExplicitPath $ScpPath -CommandName "scp" -WrapperScript $ScpWrapperScript

$tarCommand = Get-Command tar -ErrorAction SilentlyContinue
if (-not $tarCommand) {
  throw "tar was not found."
}

& $tarCommand.Source -czf $localTarPath --exclude=node_modules --exclude=data --exclude=.runtime -C $LocalProjectDir .
if ($LASTEXITCODE -ne 0) {
  throw "failed to create rollout tarball"
}

Invoke-ExternalTool -Config $scpLaunch -Arguments @(
  "-i", $IdentityFile,
  "-o", "BatchMode=yes",
  "-o", "StrictHostKeyChecking=accept-new",
  $localTarPath,
  "${target}:$remoteTarPath"
)

$remoteDeployScript = @"
set -euo pipefail
TS=$timestamp
TARBALL=$(Quote-Bash $remoteTarPath)
SOURCE_DIR=$(Quote-Bash $RemoteSourceDir)
BACKUP_DIR=$(Quote-Bash "${RemoteSourceDir}_backup_$timestamp")
TMPDIR=$(Quote-Bash "${RemoteSourceDir}_tmp_$timestamp")
cd /
rm -rf `$TMPDIR
mkdir -p `$TMPDIR
tar -xzf `$TARBALL -C `$TMPDIR
if [ -d `$SOURCE_DIR ]; then
  cp -a `$SOURCE_DIR `$BACKUP_DIR
  rm -rf `$SOURCE_DIR
fi
mv `$TMPDIR `$SOURCE_DIR
sudo docker build -t $(Quote-Bash $imageTag) `$SOURCE_DIR
"@ -replace "`r`n", "`n"

$remoteDeployScriptLocalPath = Join-Path $RuntimeDir "deploy_program_admin_remote_$timestamp.sh"
[System.IO.File]::WriteAllText($remoteDeployScriptLocalPath, $remoteDeployScript, (New-Object System.Text.UTF8Encoding($false)))

Invoke-ExternalTool -Config $scpLaunch -Arguments @(
  "-i", $IdentityFile,
  "-o", "BatchMode=yes",
  "-o", "StrictHostKeyChecking=accept-new",
  $remoteDeployScriptLocalPath,
  "${target}:$remoteDeployScriptPath"
)

Invoke-ExternalTool -Config $sshLaunch -Arguments @(
  "-i", $IdentityFile,
  "-o", "BatchMode=yes",
  "-o", "StrictHostKeyChecking=accept-new",
  $target,
  "bash $remoteDeployScriptPath"
)

$dockerArgs = @("sudo docker run -d --name $(Quote-Bash $RemoteContainerName)")

if ($remoteState.RestartPolicy -and $remoteState.RestartPolicy -ne "no") {
  $dockerArgs += "--restart $(Quote-Bash $remoteState.RestartPolicy)"
}

if ($remoteState.PortBindings) {
  foreach ($property in $remoteState.PortBindings.PSObject.Properties) {
    $containerPort = [string]$property.Name
    foreach ($binding in @($property.Value)) {
      $hostIp = [string]$binding.HostIp
      $hostPort = [string]$binding.HostPort
      $portSpec = if ($hostIp) { "$hostIp`:$hostPort`:$containerPort" } else { "$hostPort`:$containerPort" }
      $dockerArgs += "-p $(Quote-Bash $portSpec)"
    }
  }
}

foreach ($bind in @($remoteState.Binds)) {
  $dockerArgs += "-v $(Quote-Bash ([string]$bind))"
}

foreach ($item in $envMap.GetEnumerator()) {
  $dockerArgs += "-e $(Quote-Bash ("{0}={1}" -f $item.Key, $item.Value))"
}

$dockerArgs += Quote-Bash $imageTag
$dockerRunCommand = $dockerArgs -join " "
$replaceCommand = "set -euo pipefail; sudo docker stop $RemoteContainerName >/dev/null 2>&1 || true; sudo docker rm $RemoteContainerName >/dev/null 2>&1 || true; $dockerRunCommand"

Invoke-ExternalTool -Config $sshLaunch -Arguments @(
  "-i", $IdentityFile,
  "-o", "BatchMode=yes",
  "-o", "StrictHostKeyChecking=accept-new",
  $target,
  "bash -lc $(Quote-Bash $replaceCommand)"
)

$loopbackSmokeScript = Get-LoopbackSmokeScript -LocalAdminBaseUrl $localAdminBaseUrl
Invoke-ExternalTool -Config $sshLaunch -Arguments @(
  "-i", $IdentityFile,
  "-o", "BatchMode=yes",
  "-o", "StrictHostKeyChecking=accept-new",
  $target,
  "bash -s"
) -InputText $loopbackSmokeScript

if (-not $SkipHttpsSmoke -and (Test-Path -LiteralPath $CaCertPath)) {
  $httpsScript = @'
import json
import ssl
import sys
import urllib.request

base_url = sys.argv[1]
cafile = sys.argv[2]
expected_kid = sys.argv[3]
ctx = ssl.create_default_context(cafile=cafile)

with urllib.request.urlopen(base_url + "/api/health", context=ctx, timeout=15) as response:
    print(base_url + "/api/health")
    print(response.status)

with urllib.request.urlopen(base_url + "/api/auth/public-key", context=ctx, timeout=15) as response:
    payload = json.loads(response.read().decode("utf-8"))
    print(base_url + "/api/auth/public-key")
    print(response.status)
    if payload.get("kid") != expected_kid:
        raise SystemExit(f"unexpected public key kid: {payload.get('kid')} != {expected_kid}")

with urllib.request.urlopen(base_url + "/api/auth/register/capability", context=ctx, timeout=15) as response:
    payload = json.loads(response.read().decode("utf-8"))
    print(base_url + "/api/auth/register/capability")
    print(response.status)
    if "legacy" in payload:
        raise SystemExit("register capability should not expose legacy endpoints")

try:
    urllib.request.urlopen(base_url + "/admin", context=ctx, timeout=15)
    raise SystemExit("/admin should not be publicly reachable")
except urllib.error.HTTPError as exc:
    print(base_url + "/admin")
    print(exc.code)
    if exc.code != 404:
        raise

legacy_req = urllib.request.Request(
    base_url + "/api/auth/email/send-code",
    data=json.dumps({"email": "legacy-smoke@example.com"}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    urllib.request.urlopen(legacy_req, context=ctx, timeout=15)
    raise SystemExit("/api/auth/email/send-code should be unavailable")
except urllib.error.HTTPError as exc:
    print(base_url + "/api/auth/email/send-code")
    print(exc.code)
    if exc.code not in (404, 405):
        raise
'@
  Invoke-Process -FilePath $PythonPath -Arguments @("-c", $httpsScript, $BaseUrl, $CaCertPath, $derivedSigningKid) | Out-Null
}

Write-Output "REMOTE_CONTAINER=$RemoteContainerName"
Write-Output "DEPLOYED_IMAGE=$imageTag"
Write-Output "DERIVED_SIGNING_KID=$derivedSigningKid"
