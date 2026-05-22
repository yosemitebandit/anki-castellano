anki-castellano

scripts for building Anki cloze deletion cards for practicing a language.


### setup

```bash
cp .env.example .env   # add your GEMINI_API_KEY
uv sync
```


### dev

```bash
uv run ruff check .   # lint
uv run ruff format .  # format
uv run pyright        # type check
```


### usage

four steps, each optional after the first:

```bash
uv run wordlist --topic "sports" --count 64 sports.json
uv run images sports.json
uv run audio sports.json
uv run create-deck sports.json --deck-name "Castellano: Sports"
```

skip step 2 and/or 3 to omit images or audio and avoid those API costs.

`create-deck` defaults the output filename and deck name from the vocab file
(`sports.json` → `sports.apkg`, deck name `Sports`).


### avoiding repeats across decks

```bash
uv run wordlist --topic "music" --count 64 music.json --exclude sports.json
uv run wordlist --count 64 batch3.json --exclude batch1.json batch2.json
uv run wordlist --topic "sports" --count 32 sports.json --append
```
