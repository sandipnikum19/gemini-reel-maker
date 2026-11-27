import argparse
import subprocess
import tempfile
from pathlib import Path
from heartbreak_reel import build_heartbreak_reel
from reel_builder import build_reel


def run_batch(
    media_files: list[str],
    audio_file: str,
    lyrics_file: str,
    count: int = 5,
    duration: float = 22.0,
    style: str = "reel",
) -> None:
    safe_count = max(1, min(5, count))
    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)

    base_lines = (
        [ln.strip() for ln in Path(lyrics_file).read_text(encoding="utf-8").splitlines() if ln.strip()]
        if Path(lyrics_file).exists()
        else ["Reel line 1", "Reel line 2", "Reel line 3"]
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for idx in range(1, safe_count + 1):
            custom_lyrics = Path(f"assets/lyrics_{idx}.txt")
            if custom_lyrics.exists():
                lines_for_run = [
                    ln.strip() for ln in custom_lyrics.read_text(encoding="utf-8").splitlines() if ln.strip()
                ]
            else:
                shifted = base_lines[(idx - 1) % len(base_lines) :] + base_lines[: (idx - 1) % len(base_lines)]
                lines_for_run = shifted[: max(2, min(4, len(shifted)))]

            temp_txt = tmp_dir / f"batch_lines_{idx}.txt"
            temp_txt.write_text("\n".join(lines_for_run), encoding="utf-8")
            out_mp4 = out_dir / f"batch_{idx}.mp4"

            if style == "heartbreak":
                build_heartbreak_reel(media_files, audio_file, str(temp_txt), str(out_mp4), duration)
            else:
                build_reel(media_files, audio_file, str(temp_txt), str(out_mp4), duration)

            print(f"[{idx}/{safe_count}] Ready: {out_mp4.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch reel builder (up to 5 videos)")
    parser.add_argument("--media", nargs="+", default=["assets/sample_grid.jpg"])
    parser.add_argument("--audio", default="assets/song.mp3")
    parser.add_argument("--lyrics", default="assets/lyrics.txt")
    parser.add_argument("--count", type=int, default=5, help="Max 5 videos")
    parser.add_argument("--duration", type=float, default=22.0)
    parser.add_argument("--style", choices=["reel", "heartbreak"], default="reel")
    args = parser.parse_args()
    run_batch(args.media, args.audio, args.lyrics, args.count, args.duration, args.style)


if __name__ == "__main__":
    main()
