param(
  [int]$LocalPort = 18787,
  [string]$RemoteHost = "8.138.39.139",
  [int]$RemotePort = 18787,
  [string]$RemoteUser = "admin",
  [string]$IdentityFile = "C:/Users/18220/.ssh/c5_ecs_deploy_temp",
  [string]$SshPath = "",
  [string]$BrowserPath = "",
  [string]$SshWrapperScript = "",
  [string]$BrowserWrapperScript = "",
  [int]$TunnelReadyTimeoutSeconds = 10,
  [switch]$NoBrowser,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Test-TcpPortOpen {
  param(
    [string]$HostName,
    [int]$Port
  )

  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $async = $client.BeginConnect($HostName, $Port, $null, $null)
    if (-not $async.AsyncWaitHandle.WaitOne(300)) {
      return $false
    }
    $client.EndConnect($async)
    return $true
  } catch {
    return $false
  } finally {
    $client.Close()
  }
}

function Get-SshPath {
  if ($SshPath) {
    return $SshPath
  }
  $command = Get-Command ssh -ErrorAction SilentlyContinue
  if (-not $command) {
    throw "ssh was not found. Install Windows OpenSSH Client first."
  }
  return $command.Source
}

function Get-PowerShellPath {
  $command = Get-Command powershell.exe -ErrorAction SilentlyContinue
  if (-not $command) {
    throw "powershell.exe was not found."
  }
  return $command.Source
}

function Get-NodePath {
  $command = Get-Command node -ErrorAction SilentlyContinue
  if (-not $command) {
    throw "node was not found for wrapper-script execution."
  }
  return $command.Source
}

function Assert-LocalPortFree {
  param([int]$Port)

  if (Test-TcpPortOpen -HostName "127.0.0.1" -Port $Port) {
    throw "Local port $Port is already in use. Close the conflicting process or use -LocalPort."
  }
}

function Assert-IdentityFileExists {
  param([string]$PathValue)

  if (-not (Test-Path -LiteralPath $PathValue)) {
    throw "SSH identity file was not found: $PathValue"
  }
}

function Assert-PathExists {
  param(
    [string]$PathValue,
    [string]$Label
  )

  if (-not (Test-Path -LiteralPath $PathValue)) {
    throw "$Label was not found: $PathValue"
  }
}

function Wait-TcpPortOpen {
  param(
    [string]$HostName,
    [int]$Port,
    [int]$TimeoutSeconds = 10,
    [System.Diagnostics.Process]$WatchedProcess = $null
  )

  $deadline = (Get-Date).AddSeconds([Math]::Max(1, $TimeoutSeconds))
  while ((Get-Date) -lt $deadline) {
    if ($WatchedProcess) {
      try {
        $WatchedProcess.Refresh()
      } catch {
      }
      if ($WatchedProcess.HasExited) {
        return $false
      }
    }
    if (Test-TcpPortOpen -HostName $HostName -Port $Port) {
      return $true
    }
    Start-Sleep -Milliseconds 200
  }
  return $false
}

function Stop-ManagedProcess {
  param([System.Diagnostics.Process]$Process)

  if (-not $Process) {
    return
  }
  try {
    $Process.Refresh()
  } catch {
  }
  if (-not $Process.HasExited) {
    Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
  }
}

function Resolve-BrowserPath {
  if ($BrowserPath) {
    return $BrowserPath
  }

  $candidates = @(
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "$env:LocalAppData/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "$env:LocalAppData/Google/Chrome/Application/chrome.exe"
  )

  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
      return $candidate
    }
  }

  throw "No supported browser executable was found. Use -BrowserPath to set one explicitly."
}

function New-BrowserProfileDir {
  $profileDir = Join-Path ([System.IO.Path]::GetTempPath()) ("c5-program-admin-browser-" + [Guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $profileDir | Out-Null
  return $profileDir
}

function Get-SshLaunchConfig {
  param(
    [string]$ForwardSpec,
    [string]$Target
  )

  $resolvedSshPath = Get-SshPath
  $resolvedSshArgs = @(
    "-i", $IdentityFile,
    "-o", "BatchMode=yes",
    "-o", "ExitOnForwardFailure=yes",
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ServerAliveInterval=30",
    "-o", "ServerAliveCountMax=3",
    "-N",
    "-L", $ForwardSpec,
    $Target
  )

  if ($SshWrapperScript) {
    Assert-PathExists -PathValue $SshWrapperScript -Label "SSH wrapper script"
    return @{
      Path = Get-NodePath
      Args = @($SshWrapperScript) + $resolvedSshArgs
    }
  }

  return @{
    Path = $resolvedSshPath
    Args = $resolvedSshArgs
  }
}

function Get-BrowserLaunchConfig {
  param(
    [string]$AdminUrl,
    [switch]$ForDryRun
  )

  if ($NoBrowser) {
    return $null
  }

  if ($BrowserWrapperScript) {
    Assert-PathExists -PathValue $BrowserWrapperScript -Label "Browser wrapper script"
    return @{
      Path = Get-NodePath
      Args = @(
        $BrowserWrapperScript,
        "-AdminUrl", $AdminUrl
      )
      ProfileDir = ""
    }
  }

  $resolvedBrowserPath = Resolve-BrowserPath
  $profileDir = if ($ForDryRun) { "<temp-browser-profile>" } else { New-BrowserProfileDir }
  return @{
    Path = $resolvedBrowserPath
    Args = @(
      "--new-window",
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-sync",
      "--user-data-dir=$profileDir",
      "--app=$AdminUrl"
    )
    ProfileDir = $profileDir
  }
}

Assert-IdentityFileExists -PathValue $IdentityFile
Assert-LocalPortFree -Port $LocalPort

$forwardSpec = "{0}:127.0.0.1:{1}" -f $LocalPort, $RemotePort
$target = "{0}@{1}" -f $RemoteUser, $RemoteHost
$adminUrl = "http://127.0.0.1:{0}/admin" -f $LocalPort

$sshLaunch = Get-SshLaunchConfig -ForwardSpec $forwardSpec -Target $target
$browserLaunch = Get-BrowserLaunchConfig -AdminUrl $adminUrl -ForDryRun:$DryRun

if ($DryRun) {
  Write-Output "SSH_PATH=$($sshLaunch.Path)"
  Write-Output "SSH_ARGS=$($sshLaunch.Args -join ' ')"
  if ($browserLaunch) {
    Write-Output "BROWSER_PATH=$($browserLaunch.Path)"
    Write-Output "BROWSER_ARGS=$($browserLaunch.Args -join ' ')"
  }
  Write-Output "ADMIN_URL=$adminUrl"
  exit 0
}

$sshProcess = $null
$browserProcess = $null
$browserProfileDir = ""
$scriptExitCode = 0

try {
  $sshProcess = Start-Process -FilePath $sshLaunch.Path -ArgumentList $sshLaunch.Args -PassThru -NoNewWindow
  if (-not (Wait-TcpPortOpen -HostName "127.0.0.1" -Port $LocalPort -TimeoutSeconds $TunnelReadyTimeoutSeconds -WatchedProcess $sshProcess)) {
    throw "SSH tunnel did not become ready on local port $LocalPort."
  }

  if ($NoBrowser) {
    Write-Output "Tunnel ready: $adminUrl"
    Write-Output "Press Ctrl+C to stop the tunnel."
    $sshProcess.WaitForExit()
    $sshProcess.Refresh()
    $scriptExitCode = $sshProcess.ExitCode
  } else {
    $browserProfileDir = $browserLaunch.ProfileDir
    $browserProcess = Start-Process -FilePath $browserLaunch.Path -ArgumentList $browserLaunch.Args -PassThru
    $browserProcess.WaitForExit()
    $browserProcess.Refresh()
    if ($browserProcess.ExitCode -ne 0) {
      $scriptExitCode = $browserProcess.ExitCode
      throw "Browser process exited with code $($browserProcess.ExitCode)."
    }
    Write-Output "Browser closed. Tunnel stopped."
  }
} catch {
  if ($scriptExitCode -eq 0) {
    $scriptExitCode = 1
  }
  Write-Error $_
} finally {
  Stop-ManagedProcess -Process $browserProcess
  Stop-ManagedProcess -Process $sshProcess
  if ($browserProfileDir -and $browserProfileDir -ne "<temp-browser-profile>" -and (Test-Path -LiteralPath $browserProfileDir)) {
    Remove-Item -LiteralPath $browserProfileDir -Recurse -Force -ErrorAction SilentlyContinue
  }
}

exit $scriptExitCode
