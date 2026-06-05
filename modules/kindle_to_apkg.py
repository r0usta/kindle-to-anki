"""
kindle_to_apkg.py
Converts Kindle vocabulary export JSON to an Anki .apkg file.

Structure:
    exports/book_name+YYYY-MM-DD.json  →  output/book_name+YYYY-MM-DD.apkg
    audio/book_name/word.mp3

Usage:
    python kindle_to_apkg.py
"""

import os
import re
import json
import hashlib
import genanki

# ── Paths ────────────────────────────────────────────────────────────────────
EXPORTS_DIR = "./translations"
AUDIO_DIR   = "./audio"
OUTPUT_DIR  = "./output"

# ── Card styling ─────────────────────────────────────────────────────────────
CSS = """
.card {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 18px;
    text-align: center;
    color: #1a1a2e;
    background: #f8f9fa;
    padding: 20px;
    max-width: 600px;
    margin: 0 auto;
}
.word       { font-size: 2em; font-weight: bold; color: #16213e; margin-bottom: 4px; }
.pronun     { font-size: 1em; color: #888; margin-bottom: 16px; }
.usage      { font-style: italic; color: #555; font-size: 0.9em;
              border-left: 3px solid #4a90d9; padding-left: 12px;
              text-align: left; margin: 16px auto; max-width: 500px; }
.highlight  { font-weight: bold; color: #4a90d9; }
.defs       { text-align: left; margin: 12px auto; max-width: 500px; }
.def-item   { padding: 4px 0; border-bottom: 1px solid #eee; }
.phrase-en  { font-weight: bold; color: #2c5f8a; }
.phrase-cz  { color: #555; font-size: 0.9em; }
.section    { font-size: 0.75em; text-transform: uppercase; letter-spacing: 1px;
              color: #aaa; margin: 16px 0 6px; }
hr          { border: none; border-top: 1px solid #ddd; margin: 16px 0; }
"""

# ── Templates ─────────────────────────────────────────────────────────────────
EN_CZ_FRONT = """
<div class="word">{{Word}}</div>
<div class="pronun">{{Pronunciation}}</div>
{{#Audio}}<div>{{Audio}}</div>{{/Audio}}
<hr>
<div class="usage">{{Usage}}</div>
"""

EN_CZ_BACK = """
{{FrontSide}}
<hr>
<div class="section">Definitions</div>
<div class="defs">{{Definitions}}</div>
{{#Phrases}}
<div class="section">Phrases</div>
<div class="defs">{{Phrases}}</div>
{{/Phrases}}
"""

CZ_EN_FRONT = """
<div class="typebox">
    {{type:Word}}
</div>
<hr>
<div class="section">Definitions</div>
<div class="defs">{{Definitions}}</div>
"""

CZ_EN_BACK = """
{{FrontSide}}
<hr>
<div class="word">{{Word}}</div>
<div class="pronun">{{Pronunciation}}</div>
{{#Audio}}<div>{{Audio}}</div>{{/Audio}}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────
def stable_id(seed: str) -> int:
    """Generate a stable numeric ID from a string."""
    return int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)


def book_folder_name(book_title: str) -> str:
    """Convert book title to folder name: lowercase, spaces to underscores."""
    return book_title.strip().lower().replace(" ", "_")


def highlight_word(text: str, word: str) -> str:
    """Wrap the target word in the usage sentence with a highlight span."""
    pattern = re.compile(re.escape(word), re.IGNORECASE)
    return pattern.sub(lambda m: f'<span class="highlight">{m.group()}</span>', text, count=1)


def build_definitions_html(definitions: list) -> str:
    return "".join(f'<div class="def-item">• {d}</div>' for d in definitions)


def build_phrases_html(phrases: list) -> str:
    if not phrases:
        return ""
    return "".join(
        f'<div class="def-item">'
        f'<span class="phrase-en">{p["english"]}</span><br>'
        f'<span class="phrase-cz">{p["czech"]}</span>'
        f'</div>'
        for p in phrases
    )


def make_model(book_title: str) -> genanki.Model:
    """Create a stable Anki model (card template) for this book."""
    return genanki.Model(
        stable_id(f"kindle-model-{book_title}"),
        f"Kindle - {book_title}",
        fields=[
            {"name": "Word"},
            {"name": "Pronunciation"},
            {"name": "Audio"},
            {"name": "Usage"},
            {"name": "Definitions"},
            {"name": "Phrases"},
        ],
        templates=[
            {
                "name": "EN → CZ",
                "qfmt": EN_CZ_FRONT,
                "afmt": EN_CZ_BACK,
            },
            {
                "name": "CZ → EN",
                "qfmt": CZ_EN_FRONT,
                "afmt": CZ_EN_BACK,
            },
        ],
        css=CSS,
    )


# ── Core builder ──────────────────────────────────────────────────────────────
def build_apkg(export_filename: str) -> None:
    export_path = os.path.join(EXPORTS_DIR, export_filename)

    with open(export_path, encoding="utf-8") as f:
        vocab = json.load(f)

    # Derive book title from filename: "harry_potter+2026-06-05.json" -> "Harry Potter"
    book_slug  = export_filename.split("+")[0]
    book_title = book_slug.replace("_", " ").title()

    audio_folder = os.path.join(AUDIO_DIR, book_slug)
    deck_name    = f"Kindle Vocabulary::{book_title}"

    model = make_model(book_title)
    deck  = genanki.Deck(stable_id(f"kindle-deck-{book_title}"), deck_name)
    media = []

    added   = 0
    skipped = 0

    for word_key, entry in vocab.items():
        try:
            t = entry["translation"]
            word = t.get("word", word_key) or word_key
            pronun = t.get("pronunciation") or ""
            defs = t.get("definitions") or []
            phrases = t.get("phrases") or []
            usage = entry.get("usage") or ""

            # Audio
            audio_path = os.path.join(audio_folder, f"{word_key}.mp3")
            if os.path.exists(audio_path):
                audio_tag = f"[sound:{word_key}.mp3]"
                media.append(audio_path)
            else:
                audio_tag = ""

            usage_html   = highlight_word(usage, word) if usage else "<em>(no example)</em>"
            defs_html    = build_definitions_html(defs)
            phrases_html = build_phrases_html(phrases)

            # guid encodes book + word so the same word in different books = different cards
            guid = hashlib.md5(f"{book_title}::{word_key}".encode()).hexdigest()

            note = genanki.Note(
                model=model,
                fields=[word, pronun, audio_tag, usage_html, defs_html, phrases_html],
                guid=guid,
            )
            deck.add_note(note)
            added += 1

        except Exception as e:
            print(f"  ⚠  Skipped '{word_key}': {e}")
            skipped += 1

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_filename = export_filename.replace(".json", ".apkg")
    output_path     = os.path.join(OUTPUT_DIR, output_filename)

    genanki.Package(deck, media_files=media).write_to_file(output_path)
    print(f"✓  {added} cards → '{output_path}'  ({skipped} skipped)")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    exports = sorted(
        [f for f in os.listdir(EXPORTS_DIR) if f.endswith(".json")],
        reverse=True
    )

    if not exports:
        print("No exports found in ./translations/")
        return

    # Group by book slug, show only the latest per book
    seen_books = {}
    for f in exports:
        slug = f.split("+")[0]
        if slug not in seen_books:
            seen_books[slug] = f

    latest_exports = list(seen_books.values())

    print("\nAvailable books:")
    for i, filename in enumerate(latest_exports):
        slug, date = filename.replace(".json", "").split("+")
        title = slug.replace("_", " ").title()
        print(f"  {i + 1}. {title}  ({date})")

    selected_index  = int(input("\nSelect book: ")) - 1
    selected_export = latest_exports[selected_index]

    build_apkg(selected_export)


if __name__ == "__main__":
    main()
