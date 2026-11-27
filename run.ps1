$script:venvDir = "venv"
$script:venvPy = Join-Path $script:venvDir "Scripts\python.exe"
$script:venvPip = Join-Path $script:venvDir "Scripts\pip.exe"

function Get-NamedArg {
    param(
        [object[]]$ArgsList,
        [string]$Name,
        [string]$DefaultValue
    )
    if (-not $ArgsList) { return $DefaultValue }
    $target = "-$Name"
    for ($i = 0; $i -lt $ArgsList.Count; $i++) {
        if ("$($ArgsList[$i])" -ieq $target -and ($i + 1) -lt $ArgsList.Count) {
            return "$($ArgsList[$i + 1])"
        }
    }
    return $DefaultValue
}

function Get-PythonExe {
    if (Test-Path $script:venvPy) {
        return $script:venvPy
    }
    $sysPy = Get-Command python -ErrorAction SilentlyContinue
    if ($sysPy) {
        return $sysPy.Source
    }
    throw "Python सापडला नाही. Python 3.11/3.12/3.13 इन्स्टॉल असल्याची खात्री कर."
}

$cmd = if ($args.Count -gt 0) { "$($args[0])" } else { "" }

if ($cmd -eq "setup") {
    if (-not (Test-Path $script:venvPy)) {
        python -m venv $script:venvDir
    }
    $py = Get-PythonExe
    & $py -m pip install --upgrade pip
    if (Test-Path "requirements.txt") {
        & $py -m pip install -r requirements.txt
    }
    exit 0
}

if ($cmd -eq "env") {
    if (-not (Test-Path ".env")) {
        "GEMINI_API_KEY=" | Out-File -FilePath ".env" -Encoding UTF8
        Write-Host ".env तयार केली. त्यात तुझी GEMINI_API_KEY टाक."
    } else {
        Write-Host ".env आधीच अस्तित्वात आहे."
    }
    exit 0
}

if ($cmd -eq "open") {
    $latest = Get-ChildItem -Path "output" -Filter "*.mp4" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    $targetFile = if ($latest) { $latest.FullName } else { $null }
    if ($targetFile) {
        Write-Host "Opening latest reel: $targetFile..."
        Start-Process -FilePath $targetFile
    } else {
        Write-Host "output/ फोल्डरमध्ये कोणताही .mp4 व्हिडिओ सापडला नाही."
    }
    exit 0
}

if ($cmd -eq "push") {
    $msg = if ($args.Count -gt 1 -and "$($args[1])") { "$($args[1])" } else { "Update reel maker pipeline" }
    git add .
    git commit -m "$msg"
    git push
    exit 0
}

if ($cmd -eq "reel") {
    $py = Get-PythonExe
    $media = Get-NamedArg -ArgsList $args -Name "Media" -DefaultValue "assets/sample_grid.jpg"
    $audio = Get-NamedArg -ArgsList $args -Name "Audio" -DefaultValue "assets/song.mp3"
    $lyrics = Get-NamedArg -ArgsList $args -Name "Lyrics" -DefaultValue "assets/lyrics.txt"
    $duration = Get-NamedArg -ArgsList $args -Name "Duration" -DefaultValue "22"
    $introTitle = Get-NamedArg -ArgsList $args -Name "IntroTitle" -DefaultValue "????? ????"
    $outroTitle = Get-NamedArg -ArgsList $args -Name "OutroTitle" -DefaultValue "?????? ??????"
    $out = Get-NamedArg -ArgsList $args -Name "Out" -DefaultValue "output/final_reel.mp4"

    & $py "reel_builder.py" --media $media --audio $audio --lyrics $lyrics --duration $duration --out $out
    exit $LASTEXITCODE
}

if ($cmd -eq "batch") {
    $py = Get-PythonExe
    $media = Get-NamedArg -ArgsList $args -Name "Media" -DefaultValue "assets/sample_grid.jpg"
    $audio = Get-NamedArg -ArgsList $args -Name "Audio" -DefaultValue "assets/song.mp3"
    $lyrics = Get-NamedArg -ArgsList $args -Name "Lyrics" -DefaultValue "assets/lyrics.txt"
    $count = Get-NamedArg -ArgsList $args -Name "Count" -DefaultValue "3"
    $duration = Get-NamedArg -ArgsList $args -Name "Duration" -DefaultValue "22"
    $style = Get-NamedArg -ArgsList $args -Name "BatchStyle" -DefaultValue "reel"
    $outDir = Get-NamedArg -ArgsList $args -Name "OutDir" -DefaultValue "output"

    & $py "batch_reel.py" --media $media --audio $audio --lyrics $lyrics --count $count --duration $duration --style $style --out-dir $outDir
    exit $LASTEXITCODE
}

if ($cmd -eq "aiscene") {
    if ($args.Count -lt 2 -or -not "$($args[1])") {
        Write-Error "Usage: .\run.ps1 aiscene 'Your scene prompt'"
        exit 1
    }
    $py = Get-PythonExe
    $prompt = "$($args[1])"
    $out = "assets/ai_scene.png"
    $audio = "assets/song.mp3"
    $lyrics = "assets/lyrics.txt"

    & $py "generate_scene.py" --prompt $prompt --out $out
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $py "batch_reel.py" --media $out --audio $audio --lyrics $lyrics --count 1 --duration 22 --style "ai_reel" --out-dir "output"
    exit $LASTEXITCODE
}

if ($cmd -eq "obsreel") {
    $py = Get-PythonExe
    $obsDir = "assets/obs"
    $latestObs = Get-ChildItem -Path $obsDir -Include "*.mp4","*.mkv" -Recurse -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $latestObs) {
        Write-Error "assets/obs फोल्डरमध्ये कोणतीही OBS रेकॉर्डिंग फाइल (.mp4 / .mkv) सापडली नाही."
        exit 1
    }
    Write-Host "Using latest OBS recording: $($latestObs.FullName)"
    & $py "batch_reel.py" --media $latestObs.FullName --audio "assets/song.mp3" --lyrics "assets/lyrics.txt" --count 1 --duration 22 --style "obs_reel" --out-dir "output"
    exit $LASTEXITCODE
}
if ($cmd -eq "lyricreel") {
    $py = Get-PythonExe
    $stylePrompt = Get-NamedArg -ArgsList $args -Name "Style" -DefaultValue "Romantic warm golden hour bokeh, soft cinema mood, clean 9:16 composition, no text"
    $duration = Get-NamedArg -ArgsList $args -Name "Duration" -DefaultValue "22"
    $count = Get-NamedArg -ArgsList $args -Name "Count" -DefaultValue "1"

    & $py "lyric_scenes.py" --lyrics "assets/lyrics.txt" --base-style $stylePrompt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $sceneFiles = Get-ChildItem -Path "assets/scenes/scene_*.png" -ErrorAction SilentlyContinue |
        Sort-Object Name |
        ForEach-Object { $_.FullName }
    if (-not $sceneFiles) {
        $sceneFiles = @("assets/sample_grid.jpg")
    }

    & $py "batch_reel.py" --media $sceneFiles --audio "assets/song.mp3" --lyrics "assets/lyrics.txt" --count $count --duration $duration --style "lyric_reel" --out-dir "output"
    exit $LASTEXITCODE
}
if ($cmd -eq "quickreel") {
    $py = Get-PythonExe
    $theme = Get-NamedArg -ArgsList $args -Name "Theme" -DefaultValue "warm_cinema"
    $fontSize = Get-NamedArg -ArgsList $args -Name "FontSize" -DefaultValue "56"
    $yRatio = Get-NamedArg -ArgsList $args -Name "YRatio" -DefaultValue "0.78"
    $duration = Get-NamedArg -ArgsList $args -Name "Duration" -DefaultValue "22"
    $noCardsFlag = $false
    foreach ($a in $args) {
        if ("$a" -ieq "-NoCards") { $noCardsFlag = $true }
    }

    $sceneFiles = Get-ChildItem -Path "assets/scenes/scene_*.png" -ErrorAction SilentlyContinue |
        Sort-Object Name |
        ForEach-Object { $_.FullName }
    if (-not $sceneFiles) {
        $sceneFiles = @("assets/sample_grid.jpg")
    }

    $cmdArgs = @(
        "batch_reel.py",
        "--media", $sceneFiles,
        "--audio", "assets/song.mp3",
        "--lyrics", "assets/lyrics.txt",
        "--count", "1",
        "--duration", $duration,
        "--style", "reel",
        "--theme", $theme,
        "--font-size", $fontSize,
        "--y-ratio", $yRatio,
        "--intro-title", $introTitle,
        "--outro-title", $outroTitle
    )
    if ($noCardsFlag) {
        $cmdArgs += "--no-cards"
    }

    & $py @cmdArgs
    exit $LASTEXITCODE
}
Write-Host "Unknown command: $cmd"
Write-Host "Commands: setup, env, reel, batch, aiscene, open, push"




