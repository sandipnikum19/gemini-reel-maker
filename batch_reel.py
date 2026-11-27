import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\NirmalaB.ttf",
        r"C:\Windows\Fonts\Nirmala.ttf",
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


THEMES = [
    {
        "name": "warm_cinema",
        "font_size": 56,
        "y_ratio": 0.75,
        "box_fill": (12, 14, 22, 190),
        "text_fill": (255, 246, 214, 255),
        "zoom_start": 1.00,
        "zoom_end": 1.10,
    },
    {
        "name": "neon_rose",
        "font_size": 58,
        "y_ratio": 0.72,
        "box_fill": (26, 10, 28, 190),
        "text_fill": (255, 220, 240, 255),
        "zoom_start": 1.08,
        "zoom_end": 1.00,
    },
    {
        "name": "clean_gold",
        "font_size": 54,
        "y_ratio": 0.78,
        "box_fill": (10, 18, 24, 185),
        "text_fill": (255, 215, 110, 255),
        "zoom_start": 1.02,
        "zoom_end": 1.12,
    },
]


def make_styled_caption(text: str, out_png: Path, theme: dict, width: int = 1080, height: int = 1920) -> None:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = load_font(int(theme["font_size"]))

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

    line_h = int(theme["font_size"]) + 22
    block_h = len(lines) * line_h + 36
    box_top = int(height * float(theme["y_ratio"])) - block_h // 2
    box_bottom = box_top + block_h

    max_w = 0
    for ln in lines:
        b = draw.textbbox((0, 0), ln, font=font)
        max_w = max(max_w, b[2] - b[0])

    box_w = min(width - 80, max_w + 76)
    box_left = (width - box_w) // 2
    box_right = box_left + box_w

    draw.rounded_rectangle(
        [box_left, box_top, box_right, box_bottom],
        radius=28,
        fill=theme["box_fill"],
    )

    y = box_top + 18
    for ln in lines:
        b = draw.textbbox((0, 0), ln, font=font)
        lw = b[2] - b[0]
        x = (width - lw) // 2
        draw.text((x + 2, y + 2), ln, font=font, fill=(0, 0, 0, 235))
        draw.text((x, y), ln, font=font, fill=theme["text_fill"])
        y += line_h

    img.save(out_png)


def render_variant(
    media_files: list[str],
    audio_file: str,
    lyrics_file: str,
    out_file: str,
    duration: float,
    variant_idx: int,
) -> None:
    theme = THEMES[variant_idx % len(THEMES)]
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
        total_frames = max(30, int(round(seg_dur * 30)))

        inputs: list[str] = []
        seg_specs: list[tuple[int, int, float]] = []

        for idx, line_text in enumerate(lines):
            m_src = valid_media[(idx + variant_idx) % len(valid_media)]
            is_vid = Path(m_src).suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}
            if is_vid:
                inputs.extend(["-stream_loop", "-1", "-i", m_src])
            else:
                inputs.extend(["-loop", "1", "-i", m_src])
            bg_i = len([x for x in inputs if x == "-i"]) - 1

            cap_png = tmp_dir / f"cap_{idx}.png"
            make_styled_caption(line_text, cap_png, theme)
            inputs.extend(["-loop", "1", "-i", str(cap_png)])
            fg_i = len([x for x in inputs if x == "-i"]) - 1

            t_end = (idx + 1) * seg_dur if idx < n - 1 else target_dur
            d_i = max(0.5, t_end - (idx * seg_dur))
            seg_specs.append((bg_i, fg_i, d_i))

        has_audio = bool(audio_file and Path(audio_file).exists())
        audio_i = -1
        if has_audio:
            audio_i = len([x for x in inputs if x == "-i"])
            inputs.extend(["-i", str(Path(audio_file))])

        z0 = theme["zoom_start"]
        z1 = theme["zoom_end"]
        denom = max(1, total_frames - 1)

        fc_parts: list[str] = []
        seg_labels: list[str] = []

        for idx, (bg_i, fg_i, d_i) in enumerate(seg_specs):
            m_path = Path(valid_media[(idx + variant_idx) % len(valid_media)])
            is_vid = m_path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}
            if is_vid:
                bg_filter = (
                    f"[{bg_i}:v]trim=duration={d_i:.3f},setpts=PTS-STARTPTS,"
                    f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=rgba[bg{idx}]"
                )
            else:
                bg_filter = (
                    f"[{bg_i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                    f"zoompan=z='{z0}+({z1}-({z0}))*(on/{denom})':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':"
                    f"d={total_frames}:s=1080x1920:fps=30,trim=duration={d_i:.3f},setpts=PTS-STARTPTS,format=rgba[bg{idx}]"
                )

            fc_parts.append(
                f"{bg_filter};"
                f"[{fg_i}:v]trim=duration={d_i:.3f},setpts=PTS-STARTPTS,format=rgba[fg{idx}];"
                f"[bg{idx}][fg{idx}]overlay=0:0:format=auto[seg{idx}]"
            )
            seg_labels.append(f"[seg{idx}]")

        fc_parts.append(f"{''.join(seg_labels)}concat=n={n}:v=1:a=0,format=yuv420p[vout]")
        filter_complex = ";".join(fc_parts)

        cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex, "-map", "[vout]"]
        if has_audio and audio_i >= 0:
            cmd.extend(["-map", f"{audio_i}:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"])

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
            raise RuntimeError(f"FFmpeg variant {variant_idx + 1} failed:\n{res.stderr[-900:]}")

    print(f"Batch reel ready ({theme['name']}): {out_p.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch reel generator with varied caption styles and zoom motion")
    parser.add_argument("--media", nargs="+", default=["assets/sample_grid.jpg"])
    parser.add_argument("--audio", default="assets/song.mp3")
    parser.add_argument("--lyrics", default="assets/lyrics.txt")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--duration", type=float, default=22.0)
    parser.add_argument("--style", default="reel")
    parser.add_argument("--out-dir", default="output")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    for i in range(max(1, args.count)):
        out_file = out_dir / f"{args.style}_{i + 1}.mp4"
        render_variant(args.media, args.audio, args.lyrics, str(out_file), args.duration, i)


if __name__ == "__main__":
    main()
