param(
    [Parameter(Position = 0)]
    [ValidateSet("sample", "reel", "grid", "split", "plan", "beat", "render", "heartbreak", "batch", "open", "push")]
    [string]$Mode = "sample",

    [string[]]$Media = @(".\assets\sample_grid.jpg"),
    [string]$Grid = ".\assets\sample_grid.jpg",
    [string]$Audio = ".\assets\song.mp3",
    [string]$Lyrics = ".\assets\lyrics.txt",
    [string]$Prompt = "Emotional vertical reel",
    [string]$Style = "cinematic_emotional",
    [string]$BatchStyle = "reel",
    [int]$Count = 5,
    [double]$Duration = 22.0,
    [string]$Out = ".\output\final_reel.mp4",
    [string]$Message = "Update gemini-reel-maker"
)

if (-not (Test-Path ".\venv\Scripts\Activate.ps1")) {
    python -m venv venv
}
. .\venv\Scripts\Activate.ps1

switch ($Mode) {
    "sample" {
        if (Test-Path ".\make_sample_video.py") {
            python make_sample_video.py
        } else {
            Write-Host "make_sample_video.py not found." -ForegroundColor Yellow
        }
    }
    "reel" {
        python reel_builder.py --media @Media --audio $Audio --lyrics $Lyrics --duration $Duration --out $Out
    }
    "grid" {
        python make_sample_video.py
        if (Test-Path ".\output\sample_video.mp4") {
            python reel_builder.py --media ".\output\sample_video.mp4" --audio $Audio --lyrics $Lyrics --duration $Duration --out $Out
        }
    }
    "split" {
        python grid_and_split.py --grid $Grid --out ".\output\split_video.mp4"
    }
    "plan" {
        python story_architect.py --prompt $Prompt --lyrics $Lyrics --out ".\output\story_plan.json"
        if (Test-Path ".\output\story_plan.json") {
            Get-Content ".\output\story_plan.json" -Raw
        }
    }
    "beat" {
        python beat_director.py --plan ".\output\story_plan.json" --lyrics $Lyrics --audio $Audio --style $Style --out ".\output\storyboard.json"
        if (Test-Path ".\output\storyboard.json") {
            Get-Content ".\output\storyboard.json" -Raw
        }
    }
    "render" {
        python storyboard_render.py --storyboard ".\output\storyboard.json" --media @Media --audio $Audio --out ".\output\storyboard_reel.mp4"
    }
    "heartbreak" {
        python heartbreak_reel.py --media @Media --audio $Audio --lyrics $Lyrics --duration $Duration --out ".\output\heartbreak_reel.mp4"
    }
    "batch" {
        python batch_reel.py --media @Media --audio $Audio --lyrics $Lyrics --count $Count --duration $Duration --style $BatchStyle
    }
    "open" {
        if (Test-Path $Out) {
            Start-Process $Out
        } elseif (Test-Path ".\output\batch_1.mp4") {
            Start-Process ".\output\batch_1.mp4"
        } elseif (Test-Path ".\output\heartbreak_reel.mp4") {
            Start-Process ".\output\heartbreak_reel.mp4"
        } elseif (Test-Path ".\output\storyboard_reel.mp4") {
            Start-Process ".\output\storyboard_reel.mp4"
        } elseif (Test-Path ".\output\split_video.mp4") {
            Start-Process ".\output\split_video.mp4"
        } elseif (Test-Path ".\output\final_reel.mp4") {
            Start-Process ".\output\final_reel.mp4"
        } elseif (Test-Path ".\output\sample_video.mp4") {
            Start-Process ".\output\sample_video.mp4"
        } else {
            Write-Host "No output video found yet." -ForegroundColor Yellow
        }
    }
    "push" {
        git add .
        git commit -m $Message
        git push
    }
}
