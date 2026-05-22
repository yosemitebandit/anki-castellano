#!/usr/bin/env python3
"""Assemble an Anki .apkg from a vocab JSON file, using images if available."""

import argparse
import random
from pathlib import Path

import genanki
from _lib import load_vocab

CARD_CSS = """
/* No background-color or color on .card — Anki controls the canvas and adapts to theme. */
.card        { font-family: -apple-system, sans-serif; text-align: center; padding: 20px; }

.word        { font-size: 32px; font-weight: bold; margin: 10px 0; color: #1d4ed8; }
.word-en     { font-size: 32px; font-weight: bold; margin: 10px 0; }
.translation { font-size: 18px; color: #6b7280; margin-top: 8px; }
.sentence-es { font-size: 20px; line-height: 1.6; margin-top: 10px; }
.sentence-en { font-size: 20px; line-height: 1.5; margin-top: 10px; font-style: italic; }
.img-wrap    { background: #fff; padding: 12px; border-radius: 10px;
               display: inline-block; margin-top: 15px; }
img          { max-width: 320px; border-radius: 6px; }

/* Anki desktop night mode */
.nightMode .word        { color: #60a5fa; }
.nightMode .translation { color: #9ca3af; }

/* AnkiMobile / AnkiWeb system dark mode */
@media (prefers-color-scheme: dark) {
    .word        { color: #60a5fa; }
    .translation { color: #9ca3af; }
}
"""

# Fixed ID — Anki recognises the same template across all imported decks.
# Bumped from 2_000_000_010 — added Sentence2/Audio2 fields.
MODEL_ID = 2_000_000_011


def make_model() -> genanki.Model:
    return genanki.Model(
        MODEL_ID,
        "Vocab Multi",
        fields=[
            {"name": "Spanish"},       # the target word/phrase
            {"name": "English"},       # translation, with article hint for nouns
            {"name": "Sentence"},      # first example sentence with _______
            {"name": "SentenceFull"},  # first sentence with the word filled in
            {"name": "SentenceEN"},    # English translation of first sentence
            {"name": "Sentence2"},     # second example sentence with _______
            {"name": "SentenceFull2"}, # second sentence with the word filled in
            {"name": "SentenceEN2"},   # English translation of second sentence
            {"name": "Audio2"},        # [sound:word.wav] for second sentence, or empty
            {"name": "Image"},         # <img> tag, or empty string
        ],
        templates=[
            {
                "name": "EN → ES",
                "qfmt": '<div class="word-en">{{English}}</div>',
                "afmt": (
                    '<div class="word">{{Spanish}}</div>'
                    "<hr>"
                    "{{#Image}}<div class='img-wrap'>{{Image}}</div>{{/Image}}"
                    '<div class="sentence-es">{{Sentence}}</div>'
                    '<div class="sentence-en">{{SentenceEN}}</div>'
                ),
            },
            {
                # Front is blank when Image is empty → Anki suppresses this card automatically.
                "name": "Image → ES",
                "qfmt": "{{#Image}}<div class='img-wrap'>{{Image}}</div>{{/Image}}",
                "afmt": (
                    "{{#Image}}<div class='img-wrap'>{{Image}}</div>{{/Image}}"
                    "<hr>"
                    '<div class="word">{{Spanish}}</div>'
                    '<div class="translation">{{English}}</div>'
                ),
            },
            {
                "name": "Sentence → ES",
                "qfmt": '<div class="sentence-es">{{Sentence}}</div>',
                "afmt": (
                    '<div class="sentence-es">{{Sentence}}</div>'
                    "<hr>"
                    '<div class="word">{{Spanish}}</div>'
                    "{{#Image}}<div class='img-wrap'>{{Image}}</div>{{/Image}}"
                    '<div class="sentence-en">{{SentenceEN}}</div>'
                ),
            },
            {
                # Uses second sentence so this card and Sentence→ES don't share the same text.
                # Audio2 autoplays when card is shown (Anki plays [sound:...] tags automatically).
                "name": "ES → EN (sentence)",
                "qfmt": '{{Audio2}}<div class="sentence-es">{{SentenceFull2}}</div>',
                "afmt": (
                    '<div class="sentence-es">{{SentenceFull2}}</div>'
                    "<hr>"
                    '<div class="sentence-en">{{SentenceEN2}}</div>'
                    '<div class="translation">{{Spanish}} — {{English}}</div>'
                ),
            },
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
    parser.add_argument(
        "--audio-dir",
        default="audio",
        metavar="DIR",
        help="Directory to look for TTS audio files (default: audio/)",
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
    audio_dir = Path(args.audio_dir)

    def stem(word: str) -> str:
        return word.lower().replace(" ", "_").replace("/", "_")

    model = make_model()
    deck = genanki.Deck(random.randrange(1 << 30, 1 << 31), deck_name)
    media_files = []

    with_images = with_audio = 0
    for entry in vocab:
        word, translation, sentence, _, sentence_en, sentence2, sentence_en2 = (*entry, "", "")[:7]
        sentence_full = sentence.replace("_______", word)
        sentence_full2 = sentence2.replace("_______", word) if sentence2 else ""

        img_path = image_dir / f"{stem(word)}.png"
        if img_path.exists():
            img_field = f'<img src="{img_path.name}">'
            media_files.append(str(img_path))
            with_images += 1
        else:
            img_field = ""

        audio_path = audio_dir / f"{stem(word)}.mp3"
        if audio_path.exists():
            audio_field = f"[sound:{audio_path.name}]"
            media_files.append(str(audio_path))
            with_audio += 1
        else:
            audio_field = ""

        deck.add_note(genanki.Note(
            model=model,
            fields=[word, translation, sentence, sentence_full, sentence_en,
                    sentence2, sentence_full2, sentence_en2, audio_field, img_field],
            guid=genanki.guid_for(MODEL_ID, word),
        ))

    pkg = genanki.Package(deck)
    pkg.media_files = media_files
    pkg.write_to_file(output)

    # cards per note: 3 base (EN→ES, Sentence→ES, ES→EN) + 1 if image (Image→ES)
    total_cards = len(vocab) * 3 + with_images
    print(f"✅  {output}  —  '{deck_name}'  —  {len(vocab)} notes → {total_cards} cards"
          f"  ({with_images} with images, {with_audio} with audio)")


if __name__ == "__main__":
    main()
