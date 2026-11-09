# Build dist\WallSwap\WallSwap.exe (PyInstaller), dist\WallSwap-<version>.zip (portable) and
# dist\WallSwap-Setup.exe (Inno Setup). Run from the repo root:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$version = (Select-String -Path pyproject.toml -Pattern '^version\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value

uv run pyinstaller --noconfirm WallSwap.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$zip = "dist\WallSwap-$version.zip"
Remove-Item $zip -ErrorAction SilentlyContinue
Compress-Archive -Path dist\WallSwap -DestinationPath $zip

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found; install it with: winget install --id JRSoftware.InnoSetup -e" }
& $iscc "/DAppVersion=$version" installer\WallSwap.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }

Write-Host "Built $zip and dist\WallSwap-Setup.exe ($version)"
