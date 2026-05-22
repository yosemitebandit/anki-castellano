#!/usr/bin/env python3
"""Generate TTS audio for the second example sentence of each word in a vocab JSON file."""

import argparse
import concurrent.futures
import random
import sys
import wave
from pathlib import Path

from _lib import load_vocab, make_client
from google.genai import types

VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]


def word_to_filename(word: str) -> str:
    return word.lower().replace(" ", "_").replace("/", "_")


def save_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm)


def generate_audio(sentence: str, client) -> bytes | None:
    voice = random.choice(VOICES)
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
        print(f"  ❌  {exc}", file=sys.stderr)
        return None


def process_entry(entry: list, audio_dir: Path, client) -> bool:
    word = entry[0]
    sentence2 = entry[5] if len(entry) > 5 else ""
    if not sentence2:
        print(f"  ⚠   No second sentence for '{word}' — regenerate vocab to get one")
        return False

    path = audio_dir / f"{word_to_filename(word)}.wav"
    if path.exists():
        print(f"  ♻   Cached: {word}")
        return True

    sentence_full2 = sentence2.replace("_______", word)
    print(f"  🔊  Generating: {word}")
    pcm = generate_audio(sentence_full2, client)
    if pcm:
        save_wav(path, pcm)
        return True
    return False


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

    client = make_client()
    print(f"Generating audio for {len(vocab)} words → {audio_dir}/")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda e: process_entry(e, audio_dir, client), vocab))

    generated = sum(results)
    print(f"\n✅  Done — {generated}/{len(vocab)} audio files in {audio_dir}/")


if __name__ == "__main__":
    main()
