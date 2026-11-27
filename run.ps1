$script:venvDir = "venv"
$script:binDir = if ($IsWindows) { "Scripts" } else { "bin" }
$script:venvBin = Join-Path $script:venvDir $script:binDir
$script:pip = Join-Path $script:venvBin "pip"
$script:python = Join-Path $script:venvBin "python"
$script:ffmpeg = "ffmpeg"

# Function to ensure venv and dependencies are ready
function Ensure-Venv {
    if (-not (Test-Path $script:venvDir)) {
        Write-Host "Virtual environment not found. Creating venv..."
        python -m venv $script:venvDir
        Write-Host "Venv created."
    }
    if (-not (Test-Path $script:python)) {
        Write-Host "Python executable not found in venv. Re-creating venv..."
        python -m venv $script:venvDir
    }
}

# Basic setup and run commands
if ($args[0] -eq "setup") {
    Ensure-Venv
    Write-Host "Installing dependencies..."
    & $script:pip install --upgrade pip
    & $script:pip install -r requirements.txt
    Write-Host "Setup complete. Activate venv with: . .venv/Scripts/Activate"
    exit
}

if ($args[0] -eq "env") {
    if (-not (Test-Path ".env")) {
        Write-Host ".env file not found. Creating .env template..."
        @"
GEMINI_API_KEY=तुमची_API_KEY_इथे_टाका
"@ | Out-File -FilePath ".env" -Encoding UTF8
        Write-Host ".env created. प्लीज त्यात तुमची GEMINI_API_KEY टाका."
    } else {
        Write-Host ".env file already exists."
    }
    exit
}

# Activate Venv for subsequent commands
Ensure-Venv
if ($IsWindows) {
    # We cannot dot-source activate.bat easily here, so we set up PATH for subprocesses
    $env:Path = "$pwd;$script:venvBin;$env:Path"
}

# --- Pipeline Commands ---

if ($args[0] -eq "plan") {
    Write-Host "Generating video plan..."
    & $script:python plan_generator.py --topic $args[1]
    exit
}

if ($args[0] -eq "beat") {
    Write-Host "Generating beat alignment..."
    & $script:python beat_aligner.py --audio $args[1] --plan $args[2]
    exit
}

if ($args[0] -eq "render") {
    Write-Host "Rendering storyboard panel..."
    & $script:python storyboard_render.py --beat $args[1] --out $args[2]
    exit
}

if ($args[0] -eq "heartbreak") {
    Write-Host "Rendering heartbreak style video..."
    & $script:python heartbreak_render.py --beat $args[1] --out $args[2]
    exit
}

if ($args[0] -eq "open") {
    $candidates = @("output/ai_reel_1.mp4", "output/final_reel.mp4", "output/reel_1.mp4")
    $targetFile = $null
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            $targetFile = $c
            break
        }
    }
    if (-not $targetFile) {
        $latest = Get-ChildItem -Path "output" -Filter "*.mp4" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($latest) { $targetFile = $latest.FullName }
    }
    if ($targetFile) {
        Write-Host "Opening $targetFile..."
        Start-Process -FilePath $targetFile
    } else {
        Write-Host "Output video not found in output/ folder."
    }
    exit
}

if ($args[0] -eq "push") {
    $msg = $args[1] -or "Update reels and code"
    Write-Host "Pushing to GitHub: $msg..."
    git add .
    git commit -m "$msg"
    git push
    Write-Host "Pushed successfully."
    exit
}

# --- New Pipeline Commands (Handling + Batch) ---

if ($args[0] -eq "reel") {
    Write-Host "Building 20-25s vertical reel with captions..."
    # Capture named arguments for build_reel
    $media = Get-NamedArg -Args $args -Name "Media" -Default "assets/sample_grid.jpg"
    $audio = Get-NamedArg -Args $args -Name "Audio" -Default "assets/song.mp3"
    $lyrics = Get-NamedArg -Args $args -Name "Lyrics" -Default "assets/lyrics.txt"
    $duration = Get-NamedArg -Args $args -Name "Duration" -Default 22.0
    $out = Get-NamedArg -Args $args -Name "Out" -Default "output/final_reel.mp4"

    # Construct command list for subprocess
    $cmdList = @(
        $script:python, "reel_builder.py",
        "--media", $media,
        "--audio", $audio,
        "--lyrics", $lyrics,
        "--duration", $duration.ToString(),
        "--out", $out
    )
    & @cmdList
    exit
}

if ($args[0] -eq "batch") {
    Write-Host "Generating batch reels..."
    # Capture named arguments for batch_reel
    $media = Get-NamedArg -Args $args -Name "Media" -Default "assets/sample_grid.jpg"
    $audio = Get-NamedArg -Args $args -Name "Audio" -Default "assets/song.mp3"
    $lyrics = Get-NamedArg -Args $args -Name "Lyrics" -Default "assets/lyrics.txt"
    $count = Get-NamedArg -Args $args -Name "Count" -Default 3
    $duration = Get-NamedArg -Args $args -Name "Duration" -Default 22.0
    $style = Get-NamedArg -Args $args -Name "BatchStyle" -Default "reel"
    $out_dir = Get-NamedArg -Args $args -Name "OutDir" -Default "output"

    $cmdList = @(
        $script:python, "batch_reel.py",
        "--media", $media,
        "--audio", $audio,
        "--lyrics", $lyrics,
        "--count", $count.ToString(),
        "--duration", $duration.ToString(),
        "--style", $style,
        "--out-dir", $out_dir
    )
    & @cmdList
    exit
}

if ($args[0] -eq "aiscene") {
    $prompt = $args[1]
    $out = "assets/ai_scene.png"
    $audio = "assets/song.mp3"
    $lyrics = "assets/lyrics.txt"
    $count = 1
    $duration = 22.0

    # 1) Generate AI scene
    if (-not $prompt) {
        Write-Error "aiscene command requires a prompt. Usage: .\run.ps1 aiscene 'Your scene prompt'"
        exit
    }
    Write-Host "Generating AI scene image: $prompt"
    $genCmd = @($script:python, "generate_scene.py", "--prompt", $prompt, "--out", $out)
    & @genCmd
    if ($LASTEXITCODE -ne 0) { Write-Error "AI Scene Generation Failed."; exit }

    # 2) Generate Reel using the new AI scene
    Write-Host "Generating reel using generated AI scene..."
    $reelCmd = @(
        $script:python, "batch_reel.py",
        "--media", $out,
        "--audio", $audio,
        "--lyrics", $lyrics,
        "--count", $count.ToString(),
        "--duration", $duration.ToString(),
        "--out-dir", "output",
        "--style", "ai_reel"
    )
    & @reelCmd
    if ($LASTEXITCODE -ne 0) { Write-Error "Reel generation Failed."; exit }
    Write-Host "AI Reel ready: output/ai_reel_1.mp4"
    exit
}

# --- Helper Function ---
function Get-NamedArg {
    param($Args, $Name, $Default)
    $index = $Args.IndexOf("-$Name")
    if ($index -ge 0) {
        return $Args[$index + 1]
    } else {
        return $Default
    }
}

Write-Host "Unknown command: $($args[0])"
Write-Host "Available commands: setup, env, plan, beat, render, heartbreak, reel, batch, aiscene, open, push"

