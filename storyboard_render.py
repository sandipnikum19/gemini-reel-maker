import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def get_audio_duration(audio_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    try:
        out = subprocess.check_output(cmd, text=True).strip()
        val = float(out)
        return val if val > 0 else 22.0
    except Exception:
        return 22.0


def render_cut_clip(media_path: str, out_clip: Path, duration: float, move: str = "in") -> None:
    dur = max(1.0, float(duration))
    frames = max(30, int(round(dur * 30)))
    m_path = Path(media_path)

    if not m_path.exists():
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x111827:s=1080x1920:r=30:d={dur:.3f}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "18",
            str(out_clip),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg solid clip failed:\n{res.stderr[-800:]}")
        return

    suffix = m_path.suffix.lower()
    if suffix in {".mp4", ".mov", ".mkv", ".webm"}:
        cmd = [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(m_path),
            "-t",
            f"{dur:.3f}",
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p",
            "-an",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            str(out_clip),
        ]
    else:
        if move == "out":
            zoom_expr = f"1.12-0.12*(on/{max(1, frames-1)})"
        else:
            zoom_expr = f"1.0+0.12*(on/{max(1, frames-1)})"

        vf = (
            f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"zoompan=z='{zoom_expr}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d={frames}:s=1080x1920:fps=30,"
            f"format=yuv420p"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(m_path),
            "-t",
            f"{dur:.3f}",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-crf",
            "18",
            str(out_clip),
        ]

    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg failed on {out_clip.name} ({dur:.2f}s):\n{res.stderr[-800:]}")


def render_storyboard(storyboard_path: str, media_list: list[str], audio_path: str, out_path: str) -> None:
    sb_file = Path(storyboard_path)
    if not sb_file.exists():
        raise FileNotFoundError(f"Storyboard not found: {sb_file}")

    data = json.loads(sb_file.read_text(encoding="utf-8-sig"))
    beats = data.get("beats") or data.get("shots") or data.get("scenes") or []

    audio_dur = get_audio_duration(audio_path) if audio_path and Path(audio_path).exists() else 22.0
    total_target = min(35.0, max(12.0, audio_dur))

    if not beats:
        beats = [
            {"duration": total_target / 3.0, "move": "in"},
            {"duration": total_target / 3.0, "move": "out"},
            {"duration": total_target / 3.0, "move": "in"},
        ]

    raw_durs = [float(b.get("duration", 4.0) or 4.0) for b in beats]
    sum_dur = sum(raw_durs) or 1.0
    scaled_durs = [max(1.5, (d / sum_dur) * total_target) for d in raw_durs]

    valid_media = [m for m in media_list if Path(m).exists()] or [media_list[0]]

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        clip_paths: list[Path] = []
        concat_lines: list[str] = []

        for idx, (beat, dur) in enumerate(zip(beats, scaled_durs)):
            m_choice = valid_media[idx % len(valid_media)]
            move = str(beat.get("move") or ("out" if idx % 2 else "in")).lower()
            c_path = tmp_dir / f"cut_{idx}.mp4"
            render_cut_clip(m_choice, c_path, dur, move=move)
            clip_paths.append(c_path)
            concat_lines.append(f"file '{c_path.as_posix()}'")

        concat_txt = tmp_dir / "concat.txt"
        concat_txt.write_text("\n".join(concat_lines), encoding="utf-8")

        merged_video = tmp_dir / "merged.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_txt),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "18",
                str(merged_video),
            ],
            check=True,
            capture_output=True,
            text=True,
            errors="replace",
        )

        if audio_path and Path(audio_path).exists():
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(merged_video),
                    "-i",
                    str(Path(audio_path)),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-shortest",
                    str(out_file),
                ],
                check=True,
                capture_output=True,
                text=True,
                errors="replace",
            )
        else:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(merged_video), "-c", "copy", str(out_file)],
                check=True,
                capture_output=True,
                text=True,
                errors="replace",
            )

    print("Storyboard reel ready:", out_file.resolve())


def main() -> None:
    parser = argparse.ArgumentParser(description="Render storyboard into vertical reel")
    parser.add_argument("--storyboard", default="output/storyboard.json")
    parser.add_argument("--media", nargs="+", default=["assets/sample_grid.jpg"])
    parser.add_argument("--audio", default="assets/song.mp3")
    parser.add_argument("--out", default="output/storyboard_reel.mp4")
    args = parser.parse_args()
    render_storyboard(args.storyboard, args.media, args.audio, args.out)


if __name__ == "__main__":
    main()
