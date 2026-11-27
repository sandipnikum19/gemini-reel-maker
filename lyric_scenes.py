import argparse
import os
from pathlib import Path
from google import genai
from google.genai import types


def get_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key:
        return key.strip()
    env_p = Path(".env")
    if env_p.exists():
        for line in env_p.read_text(encoding="utf-8-sig").splitlines():
            if line.strip().startswith(("GEMINI_API_KEY=", "GOOGLE_API_KEY=")):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("GEMINI_API_KEY सापडला नाही. .env फाइलमध्ये टाक.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate one 9:16 image per lyric line via Gemini")
    parser.add_argument("--lyrics", default="assets/lyrics.txt")
    parser.add_argument("--base-style", default="Cinematic warm lighting, aesthetic reel visual, no text, no watermark")
    parser.add_argument("--out-dir", default="assets/scenes")
    parser.add_argument("--aspect", default="9:16")
    args = parser.parse_args()

    lyrics_p = Path(args.lyrics)
    lines = [ln.strip() for ln in lyrics_p.read_text(encoding="utf-8-sig").splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError("lyrics.txt मध्ये ओळी सापडल्या नाहीत.")

    client = genai.Client(api_key=get_api_key())
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    generated: list[str] = []
    for i, line in enumerate(lines, start=1):
        prompt = (
            f"Vertical 9:16 reel frame representing the mood and imagery of this line: '{line}'. "
            f"Style: {args.base_style}."
        )
        print(f"[{i}/{len(lines)}] Generating scene for: {line}")
        resp = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=args.aspect),
            ),
        )
        saved = False
        for part in resp.parts:
            if part.inline_data is not None:
                out_file = out_dir / f"scene_{i}.png"
                part.as_image().save(out_file)
                generated.append(str(out_file))
                saved = True
                break
        if not saved:
            raise RuntimeError(f"ओळ {i} साठी इमेज जनरेट झाली नाही.")

    print("Generated scenes:")
    for g in generated:
        print(" -", g)


if __name__ == "__main__":
    main()
