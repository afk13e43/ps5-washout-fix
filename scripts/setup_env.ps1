# Setup ps5video conda environment on Windows.
#
# Creates conda env 'ps5video' with just Python, then overlays gyan.dev's
# static full ffmpeg build (which includes libplacebo). We deliberately
# skip `conda install ffmpeg` because:
#   1. conda-forge's ffmpeg pulls librsvg whose post-link script crashes on
#      Chinese-locale Windows (cp950 UnicodeDecodeError), and
#   2. gyan's static "release-full" build is self-contained, so no DLL juggling.
#
# Run from anywhere in PowerShell:
#   .\scripts\setup_env.ps1

param(
    [string]$EnvName = "ps5video",
    [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

# Force UTF-8 IO so we don't trip the cp950 bug in conda sub-processes.
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
try { chcp 65001 | Out-Null } catch { }

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

# 1. Verify conda available
Write-Step "Checking conda"
$conda = (Get-Command conda -ErrorAction SilentlyContinue)
if (-not $conda) {
    throw "conda not found in PATH. Install Miniconda/Anaconda first."
}
& conda --version

# 2. Create env if missing
Write-Step "Creating conda env '$EnvName' (python=$PythonVersion)"
$envList = & conda env list
if ($envList -match "^\s*$EnvName\s") {
    Write-Host "Env '$EnvName' already exists, skipping create."
} else {
    & conda create -n $EnvName "python=$PythonVersion" -y
    if ($LASTEXITCODE -ne 0) { throw "conda create failed" }
}

# 3. Resolve env prefix
$envPrefix = (& conda run -n $EnvName python -c "import sys; print(sys.prefix)").Trim()
if (-not $envPrefix) { throw "Could not resolve env prefix for $EnvName" }
Write-Host "Env prefix: $envPrefix"
$envBin = Join-Path $envPrefix "Library\bin"
New-Item -ItemType Directory -Force -Path $envBin | Out-Null

# 4. Download gyan.dev full STATIC build (has libplacebo, no DLL deps)
Write-Step "Downloading gyan.dev ffmpeg release-full (static, has libplacebo)"
$tmp = Join-Path $env:TEMP "ps5video_ffmpeg"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$archive = Join-Path $tmp "ffmpeg-release-full.7z"
$url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full.7z"

if (Test-Path $archive) {
    Write-Host "Archive already exists ($([math]::Round((Get-Item $archive).Length / 1MB, 1)) MB), skipping download."
} else {
    try {
        Start-BitsTransfer -Source $url -Destination $archive
    } catch {
        Write-Host "BITS failed, falling back to Invoke-WebRequest"
        $ProgressPreference = "SilentlyContinue"  # IWR's progress bar is dog-slow
        Invoke-WebRequest -Uri $url -OutFile $archive -UseBasicParsing
    }
}

# 5. Extract with 7z
Write-Step "Extracting"
$extractDir = Join-Path $tmp "extracted"
if (Test-Path $extractDir) { Remove-Item -Recurse -Force $extractDir }
New-Item -ItemType Directory -Force -Path $extractDir | Out-Null

$sevenZip = (Get-Command 7z -ErrorAction SilentlyContinue)
if (-not $sevenZip) {
    foreach ($p in @("C:\Program Files\7-Zip\7z.exe", "C:\Program Files (x86)\7-Zip\7z.exe")) {
        if (Test-Path $p) { $sevenZip = @{ Source = $p }; break }
    }
}
if (-not $sevenZip) {
    throw "7z not found. Install 7-Zip from https://www.7-zip.org/ (gyan build is .7z)."
}
& $sevenZip.Source x $archive "-o$extractDir" -y | Out-Null
if ($LASTEXITCODE -ne 0) { throw "7z extraction failed" }

# 6. Locate the extracted bin/ directory
$gyanBin = Get-ChildItem -Path $extractDir -Recurse -Directory -Filter "bin" | Select-Object -First 1
if (-not $gyanBin) { throw "Could not find bin/ inside extracted archive" }
Write-Host "Found gyan bin: $($gyanBin.FullName)"

# 7. Copy binaries into env's Library\bin
Write-Step "Copying gyan binaries into $envBin"
Copy-Item -Path (Join-Path $gyanBin.FullName "*") -Destination $envBin -Recurse -Force
Write-Host "Copy complete."

# 8. Verify libplacebo is available
Write-Step "Verifying libplacebo filter"
$ffmpegExe = Join-Path $envBin "ffmpeg.exe"
$filters = & $ffmpegExe -hide_banner -filters 2>&1
if ($filters -match "libplacebo") {
    Write-Host "libplacebo filter present. OK." -ForegroundColor Green
} else {
    Write-Warning "libplacebo NOT found in ffmpeg -filters output. to-sdr command will fail."
}

# 9. pip install -e .
Write-Step "Installing ps5video package (editable) into env"
Push-Location $RepoRoot
try {
    & conda run -n $EnvName --no-capture-output pip install -e .
    if ($LASTEXITCODE -ne 0) { throw "pip install -e . failed" }
} finally {
    Pop-Location
}

# 10. Final check
Write-Step "Final check"
& conda run -n $EnvName --no-capture-output ps5video --version

Write-Host ""
Write-Host "Done. Activate with:  conda activate $EnvName" -ForegroundColor Green
