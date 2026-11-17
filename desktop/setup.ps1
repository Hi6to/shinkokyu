# シン呼吸 デスクトップ：はじめての PC で1回だけ動かす
# - 部品（Electron など）を入れる（npm install）
# - デスクトップにショートカットを2つ作る：「シン呼吸」（アプリを起動）と「シン呼吸 休憩の実験」（すぐ実験の窓を開く）
param([switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$appDir = $PSScriptRoot

if (-not $SkipInstall) {
  if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host 'Node.js が入っていません。https://nodejs.org/ から入れてから、もう一度動かしてください'
    exit 1
  }
  Write-Host '部品を入れています（はじめては数分かかります）…'
  Push-Location $appDir
  try { npm install } finally { Pop-Location }
}

# Electron の本体を探す（Hi6to の PC は OneDrive の外に置いてある）
$candidates = @(
  (Join-Path $env:USERPROFILE 'apps\shinkokyu-electron\node_modules\electron\dist\electron.exe'),
  (Join-Path $appDir 'node_modules\electron\dist\electron.exe')
)
$exe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $exe) { Write-Host 'Electron が見つかりません。desktop フォルダで npm install をしてください'; exit 1 }

$desk = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell
function New-AppShortcut([string]$name, [string]$extra) {
  $path = Join-Path $desk "$name.lnk"
  $lnk = $shell.CreateShortcut($path)
  $lnk.TargetPath = $exe
  $lnk.Arguments = ('"{0}" {1}' -f $appDir, $extra).Trim()
  $lnk.WorkingDirectory = $appDir
  $lnk.Description = $name
  $lnk.Save()
  Write-Host "作った：$path"
}
New-AppShortcut 'シン呼吸' ''
New-AppShortcut 'シン呼吸 休憩の実験' '--trial'
Write-Host 'おわり。「シン呼吸 休憩の実験」をダブルクリックすると、すぐ実験の窓が開きます（アプリが動いていなければ、起動もします）'
