import argparse
import re
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


def get_theme(
    theme_name: str | None,
    variant_idx: int,
    font_size_override: int | None,
    y_ratio_override: float | None,
) -> dict:
    chosen = None
    if theme_name:
        for t in THEMES:
            if t["name"].lower() == theme_name.strip().lower():
                chosen = dict(t)
                break
    if chosen is None:
        chosen = dict(THEMES[variant_idx % len(THEMES)])
    if font_size_override and font_size_override > 0:
        chosen["font_size"] = int(font_size_override)
    if y_ratio_override is not None and 0.20 <= y_ratio_override <= 0.90:
        chosen["y_ratio"] = float(y_ratio_override)
    return chosen


def get_motion_expr(scene_idx: int, denom: int, theme: dict) -> tuple[str, str, str]:
    mode = scene_idx % 4
    base_z0 = float(theme["zoom_start"])
    base_z1 = float(theme["zoom_end"])

    if mode == 0:
        z0, z1 = 1.00, 1.10
        x_expr = "'(iw-iw/zoom)/2'"
        y_expr = "'(ih-ih/zoom)/2'"
    elif mode == 1:
        z0, z1 = 1.10, 1.02
        x_expr = f"'(iw-iw/zoom)*({denom}-on)/{denom}'"
        y_expr = "'(ih-ih/zoom)/2'"
    elif mode == 2:
        z0, z1 = 1.02, 1.10
        x_expr = f"'(iw-iw/zoom)*(on/{denom})'"
        y_expr = "'(ih-ih/zoom)/2'"
    else:
        z0, z1 = base_z0, base_z1
        x_expr = "'(iw-iw/zoom)/2'"
        y_expr = f"'(ih-ih/zoom)*(on/{denom})'"

    z_expr = f"'{z0}+({z1}-({z0}))*(on/{denom})'"
    return z_expr, x_expr, y_expr


def parse_lyrics_with_timing(raw_text: str, body_dur: float) -> list[tuple[str, float]]:
    raw_lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    if not raw_lines:
        raw_lines = ["पहिली ओळ इथे लिहा", "दुसरी ओळ इथे लिहा", "तिसरी ओळ इथे लिहा"]

    pattern = re.compile(r"^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*\|\s*(.+)$")
    parsed: list[tuple[str, float]] = []
    all_timed = True

    for ln in raw_lines:
        m = pattern.match(ln)
        if m:
            st, en, txt = float(m.group(1)), float(m.group(2)), m.group(3).strip()
            dur = max(0.8, en - st)
            parsed.append((txt, dur))
        else:
            all_timed = False
            break

    if all_timed and parsed:
        total_given = sum(d for _, d in parsed)
        scale = body_dur / total_given if total_given > 0 else 1.0
        return [(txt, max(0.8, d * scale)) for txt, d in parsed]

    even_dur = body_dur / len(raw_lines)
    return [(ln, even_dur) for ln in raw_lines]


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
    tx = (width - (tb[2] - tb[0])) // 2
    ty = height // 2 - 110
    draw.text((tx, ty), title, font=title_font, fill=theme["text_fill"])

    sb = draw.textbbox((0, 0), subtitle, font=sub_font)
    sx = (width - (sb[2] - sb[0])) // 2
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

    max_w = max((draw.textbbox((0, 0), ln, font=font)[2] - draw.textbbox((0, 0), ln, font=font)[0]) for ln in lines)
    box_w = min(width - 80, max_w + 76)
    box_left = (width - box_w) // 2
    box_right = box_left + box_w

    draw.rounded_rectangle([box_left, box_top, box_right, box_bottom], radius=28, fill=theme["box_fill"])

    y = box_top + 18
    for ln in lines:
        b = draw.textbbox((0, 0), ln, font=font)
        x = (width - (b[2] - b[0])) // 2
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
    theme_name: str | None = None,
    font_size_override: int | None = None,
    y_ratio_override: float | None = None,
    no_cards: bool = False,
) -> None:
    theme = get_theme(theme_name, variant_idx, font_size_override, y_ratio_override)
    target_dur = min(25.0, max(20.0, float(duration)))
    raw_text = Path(lyrics_file).read_text(encoding="utf-8-sig") if Path(lyrics_file).exists() else ""

    intro_dur = 0.0 if no_cards else 2.0
    outro_dur = 0.0 if no_cards else 2.0
    body_dur = max(12.0, target_dur - intro_dur - outro_dur)
    timed_lines = parse_lyrics_with_timing(raw_text, body_dur)

    valid_media = collect_media(media_files)
    out_p = Path(out_file)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        inputs: list[str] = []
        seg_defs: list[dict] = []

        if not no_cards:
            intro_png = tmp_dir / "intro.png"
            make_card_png("अनमोल क्षण", f"भाग {variant_idx + 1}", intro_png, theme)
            intro_i = len([x for x in inputs if x == "-i"])
            inputs.extend(["-loop", "1", "-i", str(intro_png)])
            seg_defs.append({"kind": "card", "idx": intro_i, "dur": intro_dur})

        for idx, (line_text, seg_dur) in enumerate(timed_lines):
            total_frames = max(24, int(round(seg_dur * 30)))
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
                "scene_idx": idx,
                "bg_i": bg_i,
                "fg_i": fg_i,
                "is_vid": is_vid,
                "dur": seg_dur,
                "frames": total_frames,
            })

        if not no_cards:
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
            f_dur = min(0.35, d_i / 3.0)
            f_out_st = max(0.0, d_i - f_dur)
            if sd["kind"] == "card":
                fc_parts.append(
                    f"[{sd['idx']}:v]trim=duration={d_i:.3f},setpts=PTS-STARTPTS,"
                    f"scale=1080:1920,fps=30,format=yuv420p,"
                    f"fade=t=in:st=0:d={f_dur:.3f},fade=t=out:st={f_out_st:.3f}:d={f_dur:.3f}[s{s_idx}]"
                )
            else:
                bg_i = sd["bg_i"]
                fg_i = sd["fg_i"]
                f_cnt = sd["frames"]
                denom = max(1, f_cnt - 1)
                if sd["is_vid"]:
                    bg_f = (
                        f"[{bg_i}:v]trim=duration={d_i:.3f},setpts=PTS-STARTPTS,"
                        f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=rgba[bg{s_idx}]"
                    )
                else:
                    z_expr, x_expr, y_expr = get_motion_expr(sd["scene_idx"], denom, theme)
                    bg_f = (
                        f"[{bg_i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                        f"zoompan=z={z_expr}:x={x_expr}:y={y_expr}:"
                        f"d={f_cnt}:s=1080x1920:fps=30,trim=duration={d_i:.3f},setpts=PTS-STARTPTS,format=rgba[bg{s_idx}]"
                    )
                fc_parts.append(
                    f"{bg_f};"
                    f"[{fg_i}:v]trim=duration={d_i:.3f},setpts=PTS-STARTPTS,format=rgba[fg{s_idx}];"
                    f"[bg{s_idx}][fg{s_idx}]overlay=0:0:format=auto,format=yuv420p,"
                    f"fade=t=in:st=0:d={f_dur:.3f},fade=t=out:st={f_out_st:.3f}:d={f_dur:.3f}[s{s_idx}]"
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

    print(f"Positioned reel ready ({theme['name']}, y={theme['y_ratio']}): {out_p.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch reel generator with caption vertical position and card toggle")
    parser.add_argument("--media", nargs="+", default=["assets/sample_grid.jpg"])
    parser.add_argument("--audio", default="assets/song.mp3")
    parser.add_argument("--lyrics", default="assets/lyrics.txt")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--duration", type=float, default=22.0)
    parser.add_argument("--style", default="reel")
    parser.add_argument("--out-dir", default="output")
    parser.add_argument("--theme", default="", help="warm_cinema | neon_rose | clean_gold")
    parser.add_argument("--font-size", type=int, default=0, help="Override caption font size")
    parser.add_argument("--y-ratio", type=float, default=-1.0, help="Caption vertical center ratio (0.20 to 0.90)")
    parser.add_argument("--no-cards", action="store_true", help="Skip intro and outro cards")
    args = parser.parse_args()

    y_ov = args.y_ratio if args.y_ratio >= 0 else None
    out_dir = Path(args.out_dir)
    for i in range(max(1, args.count)):
        out_file = out_dir / f"{args.style}_{i + 1}.mp4"
        render_variant(
            args.media,
            args.audio,
            args.lyrics,
            str(out_file),
            args.duration,
            i,
            theme_name=args.theme or None,
            font_size_override=args.font_size or None,
            y_ratio_override=y_ov,
            no_cards=args.no_cards,
        )


if __name__ == "__main__":
    main()
