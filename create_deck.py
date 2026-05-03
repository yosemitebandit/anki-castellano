#!/usr/bin/env python3
"""Assemble an Anki .apkg from a vocab JSON file, using images if available."""

import argparse
import random
from pathlib import Path

import genanki
from _lib import load_vocab

CARD_CSS = """
.card        { font-family: -apple-system, sans-serif; text-align: center;
               background-color: #121212; color: #f8f9fa; padding: 20px; }
.cloze       { font-weight: bold; color: #3498db; }
.translation { font-size: 20px; color: #95a5a6; margin-top: 10px; }
img          { max-width: 320px; border-radius: 6px; margin-top: 15px; }
"""

# Fixed ID — Anki recognises the same template across all imported decks.
MODEL_ID = 2_000_000_003


def make_model() -> genanki.Model:
    return genanki.Model(
        MODEL_ID,
        "Vocab Cloze Dark",
        model_type=genanki.Model.CLOZE,
        fields=[
            {"name": "Text"},  # cloze sentence: "...{{c1::word}}..."
            {"name": "Translation"},  # shown on back
            {"name": "Image"},  # shown on back, empty string if no image
        ],
        templates=[
            {
                "name": "Cloze",
                "qfmt": '<div style="font-size:24px;line-height:1.6;">{{cloze:Text}}</div>',
                "afmt": (
                    '<div style="font-size:24px;line-height:1.6;">{{cloze:Text}}</div>'
                    "<hr>"
                    "{{#Image}}"
                    '<div style="background:#fff;padding:12px;border-radius:10px;display:inline-block;">'
                    "{{Image}}</div>"
                    "{{/Image}}"
                    '<div class="translation">{{Translation}}</div>'
                ),
            }
        ],
        css=CARD_CSS,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an Anki deck from a vocab JSON file. Uses images if they exist."
    )
    parser.add_argument("vocab", metavar="VOCAB_FILE", help="JSON vocab file, e.g. sports.json")
    parser.add_argument("--deck-name", metavar="NAME", help="Anki deck name (default: derived from filename)")
    parser.add_argument("--output", metavar="FILE", help="Output .apkg path (default: <vocab_stem>.apkg)")
    parser.add_argument(
        "--image-dir",
        default="images",
        metavar="DIR",
        help="Directory to look for card images (default: images/)",
    )
    parser.add_argument("--limit", type=int, metavar="N", help="Max cards to include (default: all)")
    args = parser.parse_args()

    vocab_path = Path(args.vocab)
    vocab = load_vocab(args.vocab)
    if args.limit:
        vocab = vocab[: args.limit]

    output = args.output or vocab_path.with_suffix(".apkg").name
    deck_name = args.deck_name or vocab_path.stem.replace("_", " ").title()
    image_dir = Path(args.image_dir)

    model = make_model()
    deck = genanki.Deck(random.randrange(1 << 30, 1 << 31), deck_name)
    media_files = []

    with_images = 0
    for entry in vocab:
        word, translation, sentence, _ = entry
        cloze_text = sentence.replace("_______", f"{{{{c1::{word}}}}}")

        img_path = image_dir / f"{word.lower().replace(' ', '_').replace('/', '_')}.png"
        if img_path.exists():
            img_field = f'<img src="{img_path.name}">'
            media_files.append(str(img_path))
            with_images += 1
        else:
            img_field = ""

        deck.add_note(genanki.Note(model=model, fields=[cloze_text, translation, img_field]))

    pkg = genanki.Package(deck)
    pkg.media_files = media_files
    pkg.write_to_file(output)

    text_only = len(vocab) - with_images
    summary = f"{with_images} with images"
    if text_only:
        summary += f", {text_only} text-only"
    print(f"✅  {output}  —  '{deck_name}'  —  {len(vocab)} cards ({summary})")


if __name__ == "__main__":
    main()
