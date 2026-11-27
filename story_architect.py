import argparse
import json
import os
import urllib.request
from pathlib import Path


def load_env_key(env_path: Path = Path(".env")) -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def call_gemini_plan(prompt_text: str, lines: list[str], api_key: str) -> dict | None:
    if not api_key:
        return None

    lyrics_joined = "\n".join(lines) if lines else "No lyrics provided"
    instruction = f"""
You are a short-form reel story architect.
Topic/Prompt: {prompt_text}
Lyrics/Lines:
{lyrics_joined}

Return ONLY valid JSON with keys:
- "stories": list of 3 objects, each having "title", "who", "where", "what_goes_wrong", "twist"
- "sheets": object with keys "R1", "R2", "R3", "R4" describing consistent character/room/prop/mood sheets
- "shot_list": list of objects, each having "line", "shot_type", "action", "camera"
- "grid_prompts": list of 2 strings (2x2 grid image prompts for 4 panels each)
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": instruction}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except Exception as exc:
        print(f"Gemini API fallback triggered ({exc}). Using local story architect.")
        return None


def build_fallback_plan(prompt_text: str, lines: list[str]) -> dict:
    clean_lines = [ln.strip() for ln in lines if ln.strip()] or [prompt_text]
    stories = [
        {
            "title": "Story 1: Quiet Realization",
            "who": "Young creator / protagonist",
            "where": "Dimly lit room & rainy window",
            "what_goes_wrong": "Unsent message and lingering silence",
            "twist": "Turning quiet reflection into a fresh start",
        },
        {
            "title": "Story 2: Late Night Memory",
            "who": "Two people drifting apart",
            "where": "Empty street lamp & old cafe corner",
            "what_goes_wrong": "Promises fade as time moves on",
            "twist": "A single bright light breaks the dull mood",
        },
        {
            "title": "Story 3: Echoes & Sparks",
            "who": "Solo rider / dreamer",
            "where": "Open highway at dusk",
            "what_goes_wrong": "Old doubts slow down the pace",
            "twist": "Sudden clarity and forward momentum",
        },
    ]

    sheets = {
        "R1": "Main character: expressive eyes, casual dark jacket, consistent face and hair across all shots.",
        "R2": "Secondary character / presence: subtle silhouette or warm backlight, consistent wardrobe.",
        "R3": "Primary location: moody window/room/street with soft shadows, warm lamp, and rain streaks.",
        "R4": "Visual mood & props: cinematic grain, phone screen glow, contrasting dull left vs vivid right tones.",
    }

    shot_list = []
    for idx, line in enumerate(clean_lines, start=1):
        shot_list.append({
            "line": line,
            "shot_type": f"Shot {idx}: Medium close-up",
            "action": f"Visualizing '{line}' with emotional pacing",
            "camera": "Slow push-in, 30fps, vertical 9:16 framing",
        })

    grid_prompts = [
        f"2x2 grid of 4 cinematic vertical panels for '{prompt_text}': top-left muted room, top-right window rain, bottom-left phone glow, bottom-right warm lamp light, consistent character, no text.",
        f"2x2 grid of 4 emotional reel panels: top-left quiet reflection, top-right walking away, bottom-left neon/golden spark, bottom-right hopeful wide view, consistent character, no text.",
    ]

    return {
        "stories": stories,
        "sheets": sheets,
        "shot_list": shot_list,
        "grid_prompts": grid_prompts,
    }


def generate_plan(prompt_text: str, lyrics_file: str, out_json: str) -> None:
    lines = Path(lyrics_file).read_text(encoding="utf-8").splitlines() if Path(lyrics_file).exists() else []
    api_key = load_env_key()
    plan = call_gemini_plan(prompt_text, lines, api_key) or build_fallback_plan(prompt_text, lines)

    out_p = Path(out_json)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Story plan saved to:", out_p.resolve())


def main() -> None:
    parser = argparse.ArgumentParser(description="Story architect for reel planning")
    parser.add_argument("--prompt", default="Emotional vertical reel", help="Theme or story prompt")
    parser.add_argument("--lyrics", default="assets/lyrics.txt", help="Lyrics text file")
    parser.add_argument("--out", default="output/story_plan.json", help="Output JSON file")
    args = parser.parse_args()
    generate_plan(args.prompt, args.lyrics, args.out)


if __name__ == "__main__":
    main()
