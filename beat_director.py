import argparse
import json
import re
import subprocess
from pathlib import Path


def get_audio_duration(audio_path: Path) -> float:
    if not audio_path.exists():
        return 25.0
    res = subprocess.run(
        ["ffmpeg", "-i", str(audio_path)],
        capture_output=True,
        text=True,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", res.stderr)
    if not match:
        return 25.0
    h, m, s = int(match.group(1)), int(match.group(2)), float(match.group(3))
    return max(5.0, h * 3600 + m * 60 + s)


def build_storyboard(
    plan_file: str = "output/story_plan.json",
    lyrics_file: str = "assets/lyrics.txt",
    audio_file: str = "assets/song.mp3",
    style: str = "cinematic_emotional",
    out_file: str = "output/storyboard.json",
) -> None:
    plan_data = {}
    plan_p = Path(plan_file)
    if plan_p.exists():
        plan_data = json.loads(plan_p.read_text(encoding="utf-8"))

    lines = [
        ln.strip()
        for ln in (Path(lyrics_file).read_text(encoding="utf-8").splitlines() if Path(lyrics_file).exists() else [])
        if ln.strip()
    ]
    if not lines:
        lines = ["Opening mood", "Emotional build-up", "Peak moment", "Closing frame"]

    total_dur = min(35.0, get_audio_duration(Path(audio_file)))
    slot = total_dur / len(lines)

    style_lock = {
        "preset": style,
        "aspect_ratio": "9:16",
        "resolution": "1080x1920",
        "fps": 30,
        "color_grading": "Moody shadows, clean highlights, subtle film grain",
        "motion": "Smooth slow push-in / pan, beat-synced cuts",
    }

    cast_lock = {
        "primary_subject": "Consistent lead character face, hair, and outfit across all cuts",
        "environment_anchor": "Consistent lighting and location continuity",
        "reference_sheets": plan_data.get("sheets", {}),
    }

    negative_rules = [
        "NEVER change the main character's face or outfit mid-scene",
        "NEVER add random watermarks, gibberish text, or distorted extra limbs",
        "NEVER jump to jarring unrelated backgrounds without a cut",
        "NEVER clip audio or exceed target reel duration",
    ]

    cuts = []
    for idx, line in enumerate(lines):
        start_s = round(idx * slot, 2)
        end_s = round((idx + 1) * slot, 2)
        cuts.append({
            "cut_id": idx + 1,
            "start_sec": start_s,
            "end_sec": end_s,
            "duration_sec": round(end_s - start_s, 2),
            "lyric": line,
            "transition": "beat_cut" if idx > 0 else "fade_in",
            "camera_move": "slow_zoom_in" if idx % 2 == 0 else "gentle_pan",
        })

    storyboard = {
        "total_duration_sec": round(total_dur, 2),
        "style_lock": style_lock,
        "cast_lock": cast_lock,
        "negative_rules": negative_rules,
        "cuts": cuts,
    }

    out_p = Path(out_file)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(storyboard, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Storyboard saved to:", out_p.resolve())


def main() -> None:
    parser = argparse.ArgumentParser(description="Beat director for story/lyric cuts")
    parser.add_argument("--plan", default="output/story_plan.json")
    parser.add_argument("--lyrics", default="assets/lyrics.txt")
    parser.add_argument("--audio", default="assets/song.mp3")
    parser.add_argument("--style", default="cinematic_emotional")
    parser.add_argument("--out", default="output/storyboard.json")
    args = parser.parse_args()
    build_storyboard(args.plan, args.lyrics, args.audio, args.style, args.out)


if __name__ == "__main__":
    main()
