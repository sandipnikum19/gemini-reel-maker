import argparse
import os
from pathlib import Path
from google import genai
from google.genai import types


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reel scene image via Gemini API")
    parser.add_argument("--prompt", required=True, help="Scene prompt in English or Marathi")
    parser.add_argument("--out", default="assets/ai_scene.png", help="Output image path")
    parser.add_argument("--aspect", default="9:16", help="Aspect ratio (e.g., 9:16)")
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        env_path = Path(".env")
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8-sig").splitlines():
                if line.strip().startswith(("GEMINI_API_KEY=", "GOOGLE_API_KEY=")):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY सापडला नाही. .env किंवा Environment Variable मध्ये सेट कर.")

    client = genai.Client(api_key=api_key)
    full_prompt = (
        f"Vertical 9:16 social media reel visual, high aesthetic quality, clean composition, "
        f"no text or watermarks. Scene: {args.prompt}"
    )

    resp = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=full_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=args.aspect),
        ),
    )

    out_p = Path(args.out)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    saved = False
    for part in resp.parts:
        if part.inline_data is not None:
            img = part.as_image()
            img.save(out_p)
            saved = True
            break

    if not saved:
        raise RuntimeError("Gemini कडून इमेज डेटा आला नाही.")

    print(f"AI scene generated: {out_p.resolve()}")


if __name__ == "__main__":
    main()
