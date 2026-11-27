import argparse
import re
import subprocess
import tempfile
from pathlib import Path


def get_media_duration(file_path: Path) -> float:
    res = subprocess.run(
        ["ffmpeg", "-i", str(file_path)],
        capture_output=True,
        text=True,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", res.stderr)
    if not match:
        raise RuntimeError(f"Could not read duration from: {file_path}")
    hours, minutes, seconds = int(match.group(1)), int(match.group(2)), float(match.group(3))
    return hours * 3600 + minutes * 60 + seconds


def format_ass_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_ass_subtitles(lines: list[str], total_dur: float, ass_path: Path, width: int = 1080, height: int = 1920) -> None:
    clean_lines = [ln.strip() for ln in lines if ln.strip()]
    if not clean_lines:
        clean_lines = ["Lyric Reel"]

    slot = total_dur / len(clean_lines)
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
    for idx, text in enumerate(clean_lines):
        start_t = format_ass_time(idx * slot)
        end_t = format_ass_time((idx + 1) * slot)
        safe_text = text.replace("{", "").replace("}", "").replace("\n", "\\N")
        events.append(f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{safe_text}")

    ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def media_to_vertical_clip(src: Path, out_mp4: Path, dur: float, idx: int, width: int = 1080, height: int = 1920) -> None:
    frames = max(1, int(dur * 30))
    zoom_expr = "min(zoom+0.0010,1.15)" if idx % 2 == 0 else "max(1.15-zoom*0.0005,1.0)"
    is_img = src.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}

    if is_img:
        vf = (
            f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
            f"crop={width * 2}:{height * 2},"
            f"zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps=30,"
            f"format=yuv420p"
        )
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", str(src),
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
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src),
            "-t", f"{dur:.3f}", "-vf", vf,
            "-an", "-c:v", "libx264", "-crf", "18", str(out_mp4),
        ]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build_reel(media_files: list[str], audio_file: str, lyrics_file: str, output_mp4: str, max_dur: float = 25.0) -> None:
    audio_p = Path(audio_file)
    if not audio_p.exists():
        raise FileNotFoundError(f"Audio not found: {audio_p.resolve()}")

    valid_media = [Path(m) for m in media_files if Path(m).exists()]
    if not valid_media:
        raise FileNotFoundError("No valid image/video media files found.")

    lyrics_p = Path(lyrics_file)
    lines = lyrics_p.read_text(encoding="utf-8").splitlines() if lyrics_p.exists() else []

    audio_dur = get_media_duration(audio_p)
    target_dur = min(audio_dur, max_dur)
    per_clip = target_dur / len(valid_media)

    out_p = Path(output_mp4)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        clips = []
        for i, m_path in enumerate(valid_media):
            c_path = tmp_dir / f"clip_{i}.mp4"
            media_to_vertical_clip(m_path, c_path, per_clip, i)
            clips.append(c_path)

        concat_txt = tmp_dir / "concat.txt"
        concat_txt.write_text("\n".join(f"file '{c.as_posix()}'" for c in clips), encoding="utf-8")

        merged_video = tmp_dir / "merged.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_txt),
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                str(merged_video),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        ass_file = tmp_dir / "captions.ass"
        write_ass_subtitles(lines, target_dur, ass_file)
        ass_escaped = ass_file.as_posix().replace(":", "\\:")

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(merged_video),
                "-i", str(audio_p),
                "-t", f"{target_dur:.3f}",
                "-vf", f"ass='{ass_escaped}'",
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                str(out_p),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    print("Final reel ready:", out_p.resolve())


def main() -> None:
    parser = argparse.ArgumentParser(description="Local FFmpeg lyric reel builder")
    parser.add_argument("--media", nargs="+", required=True, help="Image/video files")
    parser.add_argument("--audio", required=True, help="MP3/audio file")
    parser.add_argument("--lyrics", default="assets/lyrics.txt", help="Lyrics text file")
    parser.add_argument("--duration", type=float, default=25.0, help="Target duration in seconds (e.g. 20-25s)")
    parser.add_argument("--out", default="output/final_reel.mp4", help="Output mp4 path")
    args = parser.parse_args()
    build_reel(args.media, args.audio, args.lyrics, args.out, args.duration)


if __name__ == "__main__":
    main()
