#!/usr/bin/env python3
"""Generate TTS audio for the second example sentence of each word in a vocab JSON file."""

import argparse
import concurrent.futures
import hashlib
import json
import random
import re
import sys
import time
from pathlib import Path

import lameenc

from _lib import load_vocab, make_client
from google.genai import types

VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]

MANIFEST = ".manifest.json"


def word_to_filename(word: str) -> str:
    return word.lower().replace(" ", "_").replace("/", "_")


def save_mp3(path: Path, pcm: bytes) -> None:
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(128)
    encoder.set_in_sample_rate(24000)
    encoder.set_channels(1)
    encoder.set_quality(2)
    path.write_bytes(encoder.encode(pcm) + encoder.flush())


def sentence_hash(sentence: str) -> str:
    return hashlib.sha256(sentence.encode()).hexdigest()[:16]


def generate_audio(sentence: str, client, max_retries: int = 5) -> bytes | None:
    voice = random.choice(VOICES)
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-tts-preview",
                contents=sentence,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                        )
                    ),
                ),
            )
            return response.candidates[0].content.parts[0].inline_data.data
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                match = re.search(r"retryDelay.*?(\d+)s", msg)
                delay = int(match.group(1)) + 5 if match else 65
                print(f"  ⏳  Rate limited — retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                print(f"  ❌  {exc}", file=sys.stderr)
                return None
    print(f"  ❌  Failed after {max_retries} retries", file=sys.stderr)
    return None


def process_entry(entry: list, audio_dir: Path, client, manifest: dict) -> tuple[bool, str, str | None]:
    """Returns (success, word, new_hash) — new_hash is None on a cache hit or failure."""
    word = entry[0]
    sentence2 = entry[5] if len(entry) > 5 else ""
    if not sentence2:
        print(f"  ⚠   No second sentence for '{word}' — regenerate vocab to get one")
        return False, word, None

    sentence_full2 = sentence2.replace("_______", word)
    h = sentence_hash(sentence_full2)
    path = audio_dir / f"{word_to_filename(word)}.mp3"

    if path.exists() and manifest.get(word) == h:
        print(f"  ♻   Cached: {word}")
        return True, word, None

    print(f"  🔊  Generating: {word}")
    pcm = generate_audio(sentence_full2, client)
    if pcm:
        save_mp3(path, pcm)
        return True, word, h
    return False, word, None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate TTS audio for the second example sentence of each vocab word."
    )
    parser.add_argument("vocab", metavar="VOCAB_FILE", help="JSON vocab file, e.g. sports.json")
    parser.add_argument(
        "--dir", default="audio", metavar="DIR", help="Directory to save audio files (default: audio/)"
    )
    parser.add_argument(
        "--workers", type=int, default=2, metavar="N", help="Concurrent API workers (default: 2)"
    )
    args = parser.parse_args()

    vocab = load_vocab(args.vocab)
    audio_dir = Path(args.dir)
    audio_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = audio_dir / MANIFEST
    manifest: dict = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    client = make_client()
    print(f"Generating audio for {len(vocab)} words → {audio_dir}/")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda e: process_entry(e, audio_dir, client, manifest), vocab))

    for success, word, h in results:
        if success and h is not None:
            manifest[word] = h
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

    generated = sum(1 for _, _, h in results if h is not None)
    cached = sum(1 for ok, _, h in results if ok and h is None)
    print(f"\n✅  Done — {generated} generated, {cached} cached  →  {audio_dir}/")


if __name__ == "__main__":
    main()
