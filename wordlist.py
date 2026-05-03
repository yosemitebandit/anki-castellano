#!/usr/bin/env python3
"""Generate a vocabulary list via Gemini and save it as JSON."""

import argparse
import json
import sys
from pathlib import Path

from _lib import make_client
from google.genai import types

SYSTEM_PROMPT = """\
You are a language curriculum designer. Generate a vocabulary list for an Anki flashcard deck.

Output ONLY a valid JSON array. Each element is an array of exactly 4 strings:
  [0] The target-language word or short phrase — for nouns, omit the article (write "resiliencia" not "la resiliencia")
  [1] The English translation — for nouns, include the article to convey gender (write "la resiliencia" or "the resilience (f.)")
  [2] A cloze sentence in the target language using _______ as the blank (natural, moderately challenging)
  [3] A vivid image generation prompt in English: clear, unambiguous, single subject.
      If the word refers to a part of a larger object, add "Draw a thick red arrow pointing to [part]."

Rules:
- No duplicates.
- Practical words and concepts to help with day-to-day fluency and conversation.
- Intermediate-to-advanced vocabulary (B2–C1 level). Words like sliding, doorstop, earlobe, bookshelf
and not beach, mountain, dog, apple.
- For adjectives, pick one form (masculine OR feminine). Never use slash notation like "efímero/a".
- Varied topics unless a theme is specified.
- Raw JSON only — no markdown, no code fences, no explanation.
"""


def collect_existing_words(files: list[str]) -> list[str]:
    words = []
    for f in files:
        p = Path(f)
        if p.exists():
            words.extend(entry[0] for entry in json.loads(p.read_text()))
    return words


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a vocabulary list.")
    parser.add_argument(
        "--lang",
        default="Castellano Spanish",
        metavar="LANG",
        help="Target language (default: Castellano Spanish)",
    )
    parser.add_argument(
        "--topic", metavar="TOPIC", help="Optional theme, e.g. 'sports', 'cooking', 'architecture'"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=64,
        metavar="N",
        help="Number of words to generate — must be a multiple of 4 (default: 64)",
    )
    parser.add_argument("file", metavar="FILE", help="JSON file to write, e.g. sports.json")
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append new words to --save file instead of overwriting it",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        metavar="FILE",
        help="Vocab JSON files whose words to avoid (prevents repeats across decks)",
    )
    args = parser.parse_args()

    if args.count % 4 != 0:
        sys.exit(f"--count ({args.count}) must be a multiple of 4.")

    # Collect all words to exclude: explicit --exclude files + the save file when appending
    exclude_files = list(args.exclude or [])
    if args.append:
        exclude_files.append(args.file)
    existing_words = collect_existing_words(exclude_files)

    client = make_client()

    topic_clause = f" Focus on the theme: {args.topic}." if args.topic else ""
    avoid_clause = (
        f" Do not include any of these words which already exist: {', '.join(existing_words)}."
        if existing_words
        else ""
    )
    prompt = f"Generate exactly {args.count} {args.lang} vocabulary entries.{topic_clause}{avoid_clause}"

    desc = f"{args.count} {args.lang} words"
    if args.topic:
        desc += f" about {args.topic}"
    if existing_words:
        desc += f" (excluding {len(existing_words)} existing)"
    print(f"Generating {desc}…")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )

    if not response.text:
        sys.exit("Gemini returned an empty response.")
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    try:
        new_vocab = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"Failed to parse response as JSON: {exc}\n\nRaw output:\n{raw}")

    if args.append and Path(args.file).exists():
        existing = json.loads(Path(args.file).read_text())
        vocab = existing + new_vocab
        print(f"Appended {len(new_vocab)} words to existing {len(existing)} → {len(vocab)} total")
    else:
        vocab = new_vocab

    Path(args.file).write_text(json.dumps(vocab, ensure_ascii=False, indent=2))
    print(f"Saved to {args.file}")


if __name__ == "__main__":
    main()
