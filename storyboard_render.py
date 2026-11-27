import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def format_ass_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_cuts_ass(cuts: list[dict], ass_path: Path, width: int = 1080, height: int = 1920) -> None:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,64,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,80,80,220,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for cut in cuts:
        start_t = format_ass_time(float(cut.get("start_sec", 0.0)))
        end_t = format_ass_time(float(cut.get("end_sec", 4.0)))
        text = str(cut.get("lyric", "")).strip() or "Reel Cut"
        safe_text = text.replace("{", "").replace("}", "").replace("\n", "\\N")
        events.append(f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{safe_text}")

    ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def render_cut_clip(media: Path, out_mp4: Path, dur: float, move: str, width: int = 1080, height: int = 1920) -> None:
    frames = max(1, int(dur * 30))
    is_img = media.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}

    if is_img:
        if move == "gentle_pan":
            z_expr = "1.12"
            x_expr = f"(iw-iw/zoom)*((n)/max(1,{frames}-1))"
            y_expr = "ih/2-(ih/zoom/2)"
        else:
            z_expr = "min(zoom+0.0011,1.16)"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"

        vf = (
            f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
            f"crop={width * 2}:{height * 2},"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={width}x{height}:fps=30,"
            f"format=yuv420p"
        )
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", str(media),
            "-t", f"{dur:.3f}", "-vf", vf,
            "-c:v", "libx264", "-crf", "18", str(out_mp4),
        ]
    else:
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"fps=30,format=yuv420p"
        )
        cmd = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(media),
            "-t", f"{dur:.3f}", "-vf", vf,
            "-an", "-c:v", "libx264", "-crf", "18", str(out_mp4),
        ]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def render_storyboard(
    storyboard_file: str = "output/storyboard.json",
    media_files: list[str] | None = None,
    audio_file: str = "assets/song.mp3",
    out_mp4: str = "output/storyboard_reel.mp4",
) -> None:
    sb_p = Path(storyboard_file)
    if not sb_p.exists():
        raise FileNotFoundError(f"Storyboard not found: {sb_p.resolve()}")

    sb = json.loads(sb_p.read_text(encoding="utf-8"))
    cuts = sb.get("cuts", [])
    if not cuts:
        raise ValueError("No cuts found in storyboard.json")

    valid_media = [Path(m) for m in (media_files or ["assets/sample_grid.jpg"]) if Path(m).exists()]
    if not valid_media:
        raise FileNotFoundError("No valid media files found for rendering.")

    total_dur = float(sb.get("total_duration_sec", sum(float(c.get("duration_sec", 4.0)) for c in cuts)))
    out_p = Path(out_mp4)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        clips = []
        for idx, cut in enumerate(cuts):
            dur = max(0.5, float(cut.get("duration_sec", 4.0)))
            move = str(cut.get("camera_move", "slow_zoom_in"))
            m_path = valid_media[idx % len(valid_media)]
            c_path = tmp_dir / f"cut_{idx + 1}.mp4"
            render_cut_clip(m_path, c_path, dur, move)
            clips.append(c_path)

        concat_txt = tmp_dir / "concat.txt"
        concat_txt.write_text("\n".join(f"file '{c.as_posix()}'" for c in clips), encoding="utf-8")

        merged_v = tmp_dir / "merged_cuts.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_txt),
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                str(merged_v),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        ass_file = tmp_dir / "cuts.ass"
        write_cuts_ass(cuts, ass_file)
        ass_escaped = ass_file.as_posix().replace(":", "\\:")

        audio_p = Path(audio_file)
        if audio_p.exists():
            cmd = [
                "ffmpeg", "-y",
                "-i", str(merged_v),
                "-i", str(audio_p),
                "-t", f"{total_dur:.3f}",
                "-vf", f"ass='{ass_escaped}'",
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                str(out_p),
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-i", str(merged_v),
                "-t", f"{total_dur:.3f}",
                "-vf", f"ass='{ass_escaped}'",
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                str(out_p),
            ]

        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("Storyboard reel ready:", out_p.resolve())


def main() -> None:
    parser = argparse.ArgumentParser(description="Render video from storyboard.json")
    parser.add_argument("--storyboard", default="output/storyboard.json")
    parser.add_argument("--media", nargs="+", default=["assets/sample_grid.jpg"])
    parser.add_argument("--audio", default="assets/song.mp3")
    parser.add_argument("--out", default="output/storyboard_reel.mp4")
    args = parser.parse_args()
    render_storyboard(args.storyboard, args.media, args.audio, args.out)


if __name__ == "__main__":
    main()
