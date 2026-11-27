import argparse
import re
import subprocess
import tempfile
from pathlib import Path


def get_image_size(img_path: Path) -> tuple[int, int]:
    res = subprocess.run(
        ["ffmpeg", "-i", str(img_path)],
        capture_output=True,
        text=True,
    )
    match = re.search(r",\s*(\d{2,5})x(\d{2,5})", res.stderr)
    if not match:
        raise RuntimeError(f"Could not read image dimensions from ffmpeg for: {img_path}")
    return int(match.group(1)), int(match.group(2))


def crop_panel(src_img: Path, dst_png: Path, x: int, y: int, w: int, h: int) -> None:
    vf = f"crop={w}:{h}:{x}:{y},scale=960:1080:force_original_aspect_ratio=increase,crop=960:1080,format=rgb24"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src_img), "-vf", vf, "-frames:v", "1", str(dst_png)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def panel_to_half_clip(img_path: Path, clip_path: Path, dur: float, mode: str, idx: int) -> None:
    frames = max(1, int(dur * 30))
    if mode == "dull":
        # Dull / muted look on the left side
        zoom_expr = "1.05"
        grade = "eq=saturation=0.35:contrast=0.88:brightness=-0.04,hue=s=0.35"
    else:
        # Vivid / vibrant look on the right side
        zoom_expr = "min(zoom+0.0012,1.16)" if idx % 2 == 0 else "max(1.16-zoom*0.0006,1.0)"
        grade = "eq=saturation=1.45:contrast=1.12:brightness=0.03"

    vf = (
        "scale=1920:2160,"
        f"zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=960x1080:fps=30,"
        f"{grade},format=yuv420p"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(img_path),
            "-t", f"{dur:.3f}", "-vf", vf,
            "-c:v", "libx264", "-crf", "18", str(clip_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def build_split_video(grid_image: str, output_mp4: str, dur_per_panel: float = 4.0) -> None:
    src = Path(grid_image)
    if not src.exists():
        raise FileNotFoundError(f"Grid image not found: {src.resolve()}")

    out_file = Path(output_mp4)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    w, h = get_image_size(src)
    mx, my = w // 2, h // 2
    pad = 4

    boxes = [
        (0, 0, max(1, mx - pad), max(1, my - pad)),
        (min(w - 1, mx + pad), 0, max(1, w - (mx + pad)), max(1, my - pad)),
        (0, min(h - 1, my + pad), max(1, mx - pad), max(1, h - (my + pad))),
        (min(w - 1, mx + pad), min(h - 1, my + pad), max(1, w - (mx + pad)), max(1, h - (my + pad))),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        split_clips = []

        for idx, (x, y, pw, ph) in enumerate(boxes, start=1):
            p_img = tmp_dir / f"panel_{idx}.png"
            left_mp4 = tmp_dir / f"left_{idx}.mp4"
            right_mp4 = tmp_dir / f"right_{idx}.mp4"
            pair_mp4 = tmp_dir / f"pair_{idx}.mp4"

            crop_panel(src, p_img, x, y, pw, ph)
            panel_to_half_clip(p_img, left_mp4, dur_per_panel, "dull", idx)
            panel_to_half_clip(p_img, right_mp4, dur_per_panel, "vivid", idx)

            # Combine left (960x1080) + thin white divider + right (960x1080) -> 1920x1080
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(left_mp4),
                    "-i", str(right_mp4),
                    "-filter_complex",
                    "[0:v]pad=964:1080:0:0:white[l];[l][1:v]hstack=inputs=2,scale=1920:1080,format=yuv420p[v]",
                    "-map", "[v]",
                    "-c:v", "libx264", "-crf", "18",
                    str(pair_mp4),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            split_clips.append(pair_mp4)

        concat_txt = tmp_dir / "concat.txt"
        concat_txt.write_text(
            "\n".join(f"file '{c.as_posix()}'" for c in split_clips),
            encoding="utf-8",
        )

        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_txt),
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                str(out_file),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    print("Split video ready:", out_file.resolve())


def main() -> None:
    parser = argparse.ArgumentParser(description="2x2 grid dull vs vivid split-screen video builder")
    parser.add_argument("--grid", default="assets/sample_grid.jpg", help="Input 2x2 grid image")
    parser.add_argument("--out", default="output/split_video.mp4", help="Output split video path")
    parser.add_argument("--dur", type=float, default=4.0, help="Seconds per grid panel")
    args = parser.parse_args()
    build_split_video(args.grid, args.out, args.dur)


if __name__ == "__main__":
    main()
