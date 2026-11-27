import argparse
import re
import subprocess
import tempfile
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
    return max(8.0, h * 3600 + m * 60 + s)


def format_ass_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def make_card_clip(
    bg_color: str,
    title_text: str,
    sub_text: str,
    accent_hex: str,
    dur: float,
    out_mp4: Path,
    width: int = 1080,
    height: int = 1920,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ass_path = Path(tmp) / "card.ass"
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,Arial,72,{accent_hex},&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,5,90,90,120,1
Style: Sub,Arial,46,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,2,2,90,90,340,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        end_t = format_ass_time(dur)
        t_clean = title_text.replace("{", "").replace("}", "").replace("\n", "\\N")
        s_clean = sub_text.replace("{", "").replace("}", "").replace("\n", "\\N")
        events = (
            f"Dialogue: 0,0:00:00.00,{end_t},Title,,0,0,0,,{t_clean}\n"
            f"Dialogue: 0,0:00:00.20,{end_t},Sub,,0,0,0,,{s_clean}\n"
        )
        ass_path.write_text(header + events, encoding="utf-8")
        ass_esc = ass_path.as_posix().replace(":", "\\:")

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c={bg_color}:s={width}x{height}:r=30:d={dur:.3f}",
                "-vf", f"ass='{ass_esc}',format=yuv420p",
                "-c:v", "libx264", "-crf", "18",
                str(out_mp4),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def make_media_clip(src: Path, dur: float, idx: int, out_mp4: Path, width: int = 1080, height: int = 1920) -> None:
    frames = max(1, int(dur * 30))
    is_img = src.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    if is_img:
        vf = (
            f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
            f"crop={width * 2}:{height * 2},"
            f"zoompan=z='min(zoom+0.0010,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps=30,"
            f"eq=saturation=0.85:contrast=1.08,format=yuv420p"
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


def write_lyrics_ass(lines: list[str], start_offset: float, body_dur: float, ass_path: Path, width: int = 1080, height: int = 1920) -> None:
    clean = [ln.strip() for ln in lines if ln.strip()] or ["Dil ki baatein..."]
    slot = body_dur / len(clean)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyric,Arial,62,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,80,80,230,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for i, line in enumerate(clean):
        s = format_ass_time(start_offset + i * slot)
        e = format_ass_time(start_offset + (i + 1) * slot)
        txt = line.replace("{", "").replace("}", "").replace("\n", "\\N")
        events.append(f"Dialogue: 0,{s},{e},Lyric,,0,0,0,,{txt}")
    ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def build_heartbreak_reel(
    media_files: list[str],
    audio_file: str,
    lyrics_file: str,
    out_mp4: str,
    max_dur: float = 25.0,
    intro_msg: str = "seen 11:42 PM\n'kuch nahi, bas aise hi...'",
    neon_end: str = "THE END\nneon nights & quiet hearts",
) -> None:
    audio_p = Path(audio_file)
    if not audio_p.exists():
        raise FileNotFoundError(f"Audio not found: {audio_p.resolve()}")

    valid_media = [Path(m) for m in media_files if Path(m).exists()]
    if not valid_media:
        raise FileNotFoundError("No valid media files found.")

    lines = Path(lyrics_file).read_text(encoding="utf-8").splitlines() if Path(lyrics_file).exists() else []
    total_dur = min(max_dur, get_audio_duration(audio_p))
    intro_dur = min(3.5, total_dur * 0.16)
    end_dur = min(3.5, total_dur * 0.16)
    body_dur = max(3.0, total_dur - intro_dur - end_dur)

    out_p = Path(out_mp4)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        intro_clip = tmp_dir / "intro.mp4"
        end_clip = tmp_dir / "ending.mp4"

        # Instrumental chat intro (&H00E5E5E5 = soft light grey in ABGR)
        make_card_clip("0x121218", "CHAT LOG", intro_msg, "&H00E5E5E5", intro_dur, intro_clip)

        # Body media sequence
        per_m = body_dur / len(valid_media)
        body_clips = []
        for idx, m in enumerate(valid_media):
            mc = tmp_dir / f"body_{idx}.mp4"
            make_media_clip(m, per_m, idx, mc)
            body_clips.append(mc)

        body_concat = tmp_dir / "body_concat.txt"
        body_concat.write_text("\n".join(f"file '{c.as_posix()}'" for c in body_clips), encoding="utf-8")
        body_merged = tmp_dir / "body_merged.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(body_concat),
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                str(body_merged),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Pink neon ending (&H00FF1493 / &H00C715FF = vibrant pink in ABGR)
        make_card_clip("0x090512", "NEON ENDING", neon_end, "&H00B44BFF", end_dur, end_clip)

        all_concat = tmp_dir / "all_concat.txt"
        all_concat.write_text(
            "\n".join(
                f"file '{p.as_posix()}'"
                for p in [intro_clip, body_merged, end_clip]
            ),
            encoding="utf-8",
        )
        merged_all = tmp_dir / "merged_all.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(all_concat),
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                str(merged_all),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        ass_file = tmp_dir / "body_lyrics.ass"
        write_lyrics_ass(lines, intro_dur, body_dur, ass_file)
        ass_esc = ass_file.as_posix().replace(":", "\\:")

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(merged_all),
                "-i", str(audio_p),
                "-t", f"{total_dur:.3f}",
                "-vf", f"ass='{ass_esc}'",
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

    print("Heartbreak reel ready:", out_p.resolve())


def main() -> None:
    parser = argparse.ArgumentParser(description="Heartbreak chat intro + lyrics + pink neon ending reel builder")
    parser.add_argument("--media", nargs="+", default=["assets/sample_grid.jpg"])
    parser.add_argument("--audio", default="assets/song.mp3")
    parser.add_argument("--lyrics", default="assets/lyrics.txt")
    parser.add_argument("--duration", type=float, default=25.0)
    parser.add_argument("--out", default="output/heartbreak_reel.mp4")
    args = parser.parse_args()
    build_heartbreak_reel(args.media, args.audio, args.lyrics, args.out, args.duration)


if __name__ == "__main__":
    main()
