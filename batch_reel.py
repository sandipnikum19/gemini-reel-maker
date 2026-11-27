import argparse
import subprocess
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
        "y_ratio": 0.76,
        "box_fill": (12, 14, 22, 195),
        "text_fill": (255, 246, 214, 255),
        "card_bg": (15, 18, 28, 255),
        "accent": (255, 204, 92, 255),
        "zoom_start": 1.00,
        "zoom_end": 1.10,
    },
    {
        "name": "neon_rose",
        "font_size": 58,
        "y_ratio": 0.74,
        "box_fill": (26, 10, 28, 195),
        "text_fill": (255, 220, 240, 255),
        "card_bg": (24, 10, 26, 255),
        "accent": (255, 105, 180, 255),
        "zoom_start": 1.08,
        "zoom_end": 1.00,
    },
    {
        "name": "clean_gold",
        "font_size": 54,
        "y_ratio": 0.78,
        "box_fill": (10, 18, 24, 190),
        "text_fill": (255, 215, 110, 255),
        "card_bg": (12, 20, 28, 255),
        "accent": (255, 215, 110, 255),
        "zoom_start": 1.02,
        "zoom_end": 1.12,
    },
]


def make_card_png(title: str, subtitle: str, out_png: Path, theme: dict, width: int = 1080, height: int = 1920) -> None:
    img = Image.new("RGBA", (width, height), theme["card_bg"])
    draw = ImageDraw.Draw(img)

    title_font = load_font(66)
    sub_font = load_font(42)

    draw.rounded_rectangle(
        [90, height // 2 - 220, width - 90, height // 2 + 220],
        radius=36,
        fill=(255, 255, 255, 18),
        outline=theme["accent"],
        width=3,
    )

    tb = draw.textbbox((0, 0), title, font=title_font)
    tw = tb[2] - tb[0]
    tx = (width - tw) // 2
    ty = height // 2 - 110
    draw.text((tx, ty), title, font=title_font, fill=theme["text_fill"])

    sb = draw.textbbox((0, 0), subtitle, font=sub_font)
    sw = sb[2] - sb[0]
    sx = (width - sw) // 2
    sy = height // 2 + 35
    draw.text((sx, sy), subtitle, font=sub_font, fill=theme["accent"])

    img.save(out_png)


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


def collect_media(media_files: list[str]) -> list[str]:
    found: list[str] = []
    for m in media_files:
        p = Path(m)
        if p.exists():
            found.append(str(p))

    scenes_dir = Path("assets/scenes")
    if len(found) <= 1 and scenes_dir.exists():
        for f in sorted(scenes_dir.glob("scene_*.png")):
            s = str(f)
            if s not in found:
                found.append(s)

    assets_dir = Path("assets")
    if len(found) <= 1 and assets_dir.exists():
        exts = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".mkv"}
        for f in sorted(assets_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in exts and "sample_grid" not in f.name.lower():
                s = str(f)
                if s not in found:
                    found.append(s)

    return found if found else ["assets/sample_grid.jpg"]


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

    valid_media = collect_media(media_files)
    out_p = Path(out_file)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    intro_dur = 2.0
    outro_dur = 2.0
    body_dur = max(12.0, target_dur - intro_dur - outro_dur)
    seg_dur = body_dur / len(lines)
    total_frames = max(30, int(round(seg_dur * 30)))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        inputs: list[str] = []
        seg_defs: list[dict] = []

        intro_png = tmp_dir / "intro.png"
        make_card_png("अनमोल क्षण", f"भाग {variant_idx + 1}", intro_png, theme)
        intro_i = len([x for x in inputs if x == "-i"])
        inputs.extend(["-loop", "1", "-i", str(intro_png)])
        seg_defs.append({"kind": "card", "idx": intro_i, "dur": intro_dur})

        z0, z1 = theme["zoom_start"], theme["zoom_end"]
        denom = max(1, total_frames - 1)

        for idx, line_text in enumerate(lines):
            m_src = valid_media[(idx + variant_idx) % len(valid_media)]
            is_vid = Path(m_src).suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}
            bg_i = len([x for x in inputs if x == "-i"])
            if is_vid:
                inputs.extend(["-stream_loop", "-1", "-i", m_src])
            else:
                inputs.extend(["-loop", "1", "-i", m_src])

            cap_png = tmp_dir / f"cap_{idx}.png"
            make_styled_caption(line_text, cap_png, theme)
            fg_i = len([x for x in inputs if x == "-i"])
            inputs.extend(["-loop", "1", "-i", str(cap_png)])

            seg_defs.append({
                "kind": "lyric",
                "bg_i": bg_i,
                "fg_i": fg_i,
                "is_vid": is_vid,
                "dur": seg_dur,
                "frames": total_frames,
            })

        outro_png = tmp_dir / "outro.png"
        make_card_png("पुन्हा भेटूया", "लाईक आणि शेअर करा", outro_png, theme)
        outro_i = len([x for x in inputs if x == "-i"])
        inputs.extend(["-loop", "1", "-i", str(outro_png)])
        seg_defs.append({"kind": "card", "idx": outro_i, "dur": outro_dur})

        has_audio = bool(audio_file and Path(audio_file).exists())
        audio_i = -1
        if has_audio:
            audio_i = len([x for x in inputs if x == "-i"])
            inputs.extend(["-i", str(Path(audio_file))])

        fc_parts: list[str] = []
        out_labels: list[str] = []

        for s_idx, sd in enumerate(seg_defs):
            d_i = sd["dur"]
            if sd["kind"] == "card":
                fc_parts.append(
                    f"[{sd['idx']}:v]trim=duration={d_i:.3f},setpts=PTS-STARTPTS,"
                    f"scale=1080:1920,fps=30,format=yuv420p[s{s_idx}]"
                )
            else:
                bg_i = sd["bg_i"]
                fg_i = sd["fg_i"]
                f_cnt = sd["frames"]
                if sd["is_vid"]:
                    bg_f = (
                        f"[{bg_i}:v]trim=duration={d_i:.3f},setpts=PTS-STARTPTS,"
                        f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=rgba[bg{s_idx}]"
                    )
                else:
                    bg_f = (
                        f"[{bg_i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                        f"zoompan=z='{z0}+({z1}-({z0}))*(on/{denom})':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':"
                        f"d={f_cnt}:s=1080x1920:fps=30,trim=duration={d_i:.3f},setpts=PTS-STARTPTS,format=rgba[bg{s_idx}]"
                    )
                fc_parts.append(
                    f"{bg_f};"
                    f"[{fg_i}:v]trim=duration={d_i:.3f},setpts=PTS-STARTPTS,format=rgba[fg{s_idx}];"
                    f"[bg{s_idx}][fg{s_idx}]overlay=0:0:format=auto,format=yuv420p[s{s_idx}]"
                )
            out_labels.append(f"[s{s_idx}]")

        total_clips = len(seg_defs)
        fc_parts.append(f"{''.join(out_labels)}concat=n={total_clips}:v=1:a=0,format=yuv420p[vout]")

        fade_start = max(0.0, target_dur - 1.5)
        if has_audio and audio_i >= 0:
            fc_parts.append(
                f"[{audio_i}:a]atrim=0:{target_dur:.3f},asetpts=PTS-STARTPTS,"
                f"afade=t=out:st={fade_start:.3f}:d=1.5[aout]"
            )

        filter_complex = ";".join(fc_parts)

        cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex, "-map", "[vout]"]
        if has_audio and audio_i >= 0:
            cmd.extend(["-map", "[aout]", "-c:a", "aac", "-b:a", "192k", "-shortest"])

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

    print(f"Smooth reel ready ({theme['name']}): {out_p.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch reel generator with smooth audio fade-out and 20-25s timing")
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
