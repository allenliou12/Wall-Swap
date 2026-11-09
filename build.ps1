# Build dist\WallSwap\WallSwap.exe (PyInstaller), dist\WallSwap-<version>.zip (portable) and
# dist\WallSwap-Setup.exe (Inno Setup). Run from the repo root:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$version = (Select-String -Path pyproject.toml -Pattern '^version\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value

uv run pyinstaller --noconfirm WallSwap.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

# Licence texts for everything the build ships (LICENSE.txt and THIRD_PARTY_LICENSES.txt next to the exe)
uv run python tools\collect_licenses.py dist\WallSwap
if ($LASTEXITCODE -ne 0) { throw "Collecting licences failed" }

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

# Checksums for the release page, rewritten every build so a stale file never survives
$sums = Get-FileHash $zip, dist\WallSwap-Setup.exe -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower())  $(Split-Path $_.Path -Leaf)" }
Set-Content -Path dist\SHA256SUMS.txt -Value $sums -Encoding ascii

Write-Host "Built $zip and dist\WallSwap-Setup.exe ($version)"
