#!/usr/bin/env python3
"""Generate card images for a vocabulary JSON file and cache them locally."""

import argparse
import concurrent.futures
import sys
from io import BytesIO
from pathlib import Path

from _lib import load_vocab, make_client
from google.genai import types
from PIL import Image

GRID_PROMPT = (
    "A single image split evenly into a 2x2 grid containing four distinct square panels. "
    "Style for all panels: BaBaDum minimalist flat vector illustration, bold outlines, "
    "vibrant solid colors, white background. "
    "CRITICAL: NO TEXT, NO LABELS, NO LETTERS anywhere. "
    "Panel 1 (Top-Left): {p1} "
    "Panel 2 (Top-Right): {p2} "
    "Panel 3 (Bottom-Left): {p3} "
    "Panel 4 (Bottom-Right): {p4}"
)

SINGLE_PROMPT = (
    "BaBaDum minimalist flat vector illustration, bold outlines, vibrant solid colors, "
    "white background. CRITICAL: NO TEXT, NO LABELS, NO LETTERS anywhere. {description}"
)


def word_to_filename(word: str) -> str:
    return word.lower().replace(" ", "_").replace("/", "_")


def generate_image(description: str, client) -> Image.Image | None:
    prompt = SINGLE_PROMPT.format(description=description)
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=[prompt],
            config=types.GenerateContentConfig(response_modalities=["Image"]),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                return Image.open(BytesIO(part.inline_data.data))
    except Exception as exc:
        print(f"  ❌  Error generating image: {exc}", file=sys.stderr)
    return None


def process_chunk(chunk: list, client, image_dir: Path) -> list[Path]:
    paths = [image_dir / f"{word_to_filename(entry[0])}.png" for entry in chunk]

    if all(p.exists() for p in paths):
        print(f"  ♻  Cached: {', '.join(e[0] for e in chunk)}")
        return paths

    if len(chunk) == 4:
        return _process_grid(chunk, paths, client)
    else:
        return _process_individual(chunk, paths, client)


def _process_grid(chunk: list, paths: list[Path], client) -> list[Path]:
    print(f"  🎨  Drawing: {', '.join(e[0] for e in chunk)}")
    prompt = GRID_PROMPT.format(p1=chunk[0][3], p2=chunk[1][3], p3=chunk[2][3], p4=chunk[3][3])
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=[prompt],
            config=types.GenerateContentConfig(response_modalities=["Image"]),
        )
        for part in response.candidates[0].content.parts:
            if not part.inline_data:
                continue
            grid = Image.open(BytesIO(part.inline_data.data))
            w, h = grid.size
            w2, h2 = w // 2, h // 2
            boxes = [(0, 0, w2, h2), (w2, 0, w, h2), (0, h2, w2, h), (w2, h2, w, h)]
            for path, box in zip(paths, boxes):
                grid.crop(box).save(path)
            return paths
    except Exception as exc:
        print(f"  ❌  Error on '{chunk[0][0]}': {exc}", file=sys.stderr)
    return []


def _process_individual(chunk: list, paths: list[Path], client) -> list[Path]:
    saved = []
    for entry, path in zip(chunk, paths):
        if path.exists():
            print(f"  ♻  Cached: {entry[0]}")
            saved.append(path)
            continue
        print(f"  🎨  Drawing: {entry[0]}")
        img = generate_image(entry[3], client)
        if img:
            img.save(path)
            saved.append(path)
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate images for a vocab JSON file.")
    parser.add_argument(
        "vocab", metavar="VOCAB_FILE", help="JSON vocab file produced by wordlist, e.g. sports.json"
    )
    parser.add_argument(
        "--dir", default="images", metavar="DIR", help="Directory to save images (default: images/)"
    )
    parser.add_argument(
        "--workers", type=int, default=4, metavar="N", help="Concurrent API workers (default: 4)"
    )
    args = parser.parse_args()

    vocab = load_vocab(args.vocab)
    image_dir = Path(args.dir)
    image_dir.mkdir(parents=True, exist_ok=True)

    chunks = [vocab[i : i + 4] for i in range(0, len(vocab), 4)]
    client = make_client()

    grid_calls = sum(1 for c in chunks if len(c) == 4)
    single_calls = sum(len(c) for c in chunks if len(c) < 4)
    call_desc = f"{grid_calls} grid calls" + (f" + {single_calls} individual" if single_calls else "")
    print(f"Generating images for {len(vocab)} words ({call_desc}) → {image_dir}/")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(lambda c: process_chunk(c, client, image_dir), chunks))

    print(f"\n✅  Done — images saved to {image_dir}/")


if __name__ == "__main__":
    main()
