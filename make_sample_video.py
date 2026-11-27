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
    vf = f"crop={w}:{h}:{x}:{y},scale=1920:1080:flags=lanczos,format=rgb24"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src_img), "-vf", vf, "-frames:v", "1", str(dst_png)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def panel_to_clip(img_path: Path, clip_path: Path, dur: float = 4.0) -> None:
    frames = max(1, int(dur * 30))
    vf = (
        "scale=2304:1296,"
        f"zoompan=z='min(zoom+0.0012,1.18)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1920x1080:fps=30,"
        "format=yuv420p"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(img_path),
            "-t", str(dur), "-vf", vf,
            "-c:v", "libx264", "-crf", "18", str(clip_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def build_video(
    grid_image: str = "assets/sample_grid.jpg",
    output_mp4: str = "output/sample_video.mp4",
) -> None:
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
        clips = []
        for idx, (x, y, pw, ph) in enumerate(boxes, start=1):
            p_img = tmp_dir / f"panel_{idx}.png"
            c_mp4 = tmp_dir / f"clip_{idx}.mp4"
            crop_panel(src, p_img, x, y, pw, ph)
            panel_to_clip(p_img, c_mp4, dur=4.0)
            clips.append(c_mp4)

        concat_txt = tmp_dir / "concat.txt"
        concat_txt.write_text(
            "\n".join(f"file '{c.as_posix()}'" for c in clips),
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

    print("Sample video ready:", out_file.resolve())


if __name__ == "__main__":
    build_video()
