import argparse
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def load_devanagari_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\Nirmala.ttf",
        r"C:\Windows\Fonts\NirmalaB.ttf",
        r"C:\Windows\Fonts\mangal.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def make_caption_png(text: str, out_png: Path, width: int = 1080, height: int = 1920) -> None:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = load_devanagari_font(54)

    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if (bbox[2] - bbox[0]) <= width - 160:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if not lines:
        lines = [text]

    line_h = 76
    block_h = len(lines) * line_h + 36
    box_top = int(height * 0.75) - block_h // 2
    box_bottom = box_top + block_h

    max_w = 0
    for ln in lines:
        b = draw.textbbox((0, 0), ln, font=font)
        max_w = max(max_w, b[2] - b[0])

    box_w = min(width - 80, max_w + 72)
    box_left = (width - box_w) // 2
    box_right = box_left + box_w

    draw.rounded_rectangle(
        [box_left, box_top, box_right, box_bottom],
        radius=26,
        fill=(10, 12, 18, 185),
    )

    y = box_top + 18
    for ln in lines:
        b = draw.textbbox((0, 0), ln, font=font)
        lw = b[2] - b[0]
        x = (width - lw) // 2
        draw.text((x + 2, y + 2), ln, font=font, fill=(0, 0, 0, 230))
        draw.text((x, y), ln, font=font, fill=(255, 248, 225, 255))
        y += line_h

    img.save(out_png)


def build_reel(
    media_files: list[str],
    audio_file: str,
    lyrics_file: str,
    out_file: str,
    duration: float = 22.0,
) -> None:
    target_dur = min(25.0, max(20.0, float(duration)))
    raw_text = Path(lyrics_file).read_text(encoding="utf-8-sig") if Path(lyrics_file).exists() else ""
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    if not lines:
        lines = ["पहिली ओळ इथे लिहा", "दुसरी ओळ इथे लिहा", "तिसरी ओळ इथे लिहा"]

    valid_media = [m for m in media_files if Path(m).exists()] or [media_files[0]]
    out_p = Path(out_file)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        n = len(lines)
        seg_dur = target_dur / n

        primary_media = valid_media[0]
        is_vid = Path(primary_media).suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}

        inputs: list[str] = []
        if is_vid:
            inputs.extend(["-stream_loop", "-1", "-i", primary_media])
        else:
            inputs.extend(["-loop", "1", "-i", primary_media])

        cap_indices: list[int] = []
        for idx, line_text in enumerate(lines):
            cap_png = tmp_dir / f"cap_{idx}.png"
            make_caption_png(line_text, cap_png)
            inputs.extend(["-loop", "1", "-i", str(cap_png)])
            cap_indices.append(1 + idx)

        has_audio = bool(audio_file and Path(audio_file).exists())
        audio_idx = 1 + len(cap_indices)
        if has_audio:
            inputs.extend(["-i", str(Path(audio_file))])

        fc_parts: list[str] = [
            f"[0:v]trim=duration={target_dur:.3f},setpts=PTS-STARTPTS,"
            f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=rgba[cur0]"
        ]

        for i, c_idx in enumerate(cap_indices):
            t_start = i * seg_dur
            t_end = (i + 1) * seg_dur if i < n - 1 else target_dur
            fc_parts.append(f"[{c_idx}:v]format=rgba[fg{i}]")
            fc_parts.append(
                f"[cur{i}][fg{i}]overlay=0:0:enable='between(t,{t_start:.3f},{t_end:.3f})':format=auto[cur{i+1}]"
            )

        fc_parts.append(f"[cur{n}]format=yuv420p[vout]")
        filter_complex = ";".join(fc_parts)

        cmd = [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
        ]
        if has_audio:
            cmd.extend(["-map", f"{audio_idx}:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"])

        cmd.extend([
            "-t",
            f"{target_dur:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "21",
            str(out_p),
        ])

        res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg build failed:\n{res.stderr[-900:]}")

    print(f"Reel ready ({target_dur:.1f}s): {out_p.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fast 20-25s reel builder with Devanagari captions")
    parser.add_argument("--media", nargs="+", default=["assets/sample_grid.jpg"])
    parser.add_argument("--audio", default="assets/song.mp3")
    parser.add_argument("--lyrics", default="assets/lyrics.txt")
    parser.add_argument("--duration", type=float, default=22.0)
    parser.add_argument("--out", default="output/final_reel.mp4")
    args = parser.parse_args()
    build_reel(args.media, args.audio, args.lyrics, args.out, args.duration)


if __name__ == "__main__":
    main()
