import json
import sqlite3
import time
import os

import deepl
from dotenv import load_dotenv

from modules.lingea_api import LingeaScraper
from modules.kindle_to_apkg import build_apkg

load_dotenv()

vocab_default_path = "./vocab.db"
deepl_api_key = None

vocab_path = os.getenv("VOCAB_PATH", default=vocab_default_path)
deepl_api_key = os.getenv("DEEPL_API_KEY", default=deepl_api_key)

deepl_translator = deepl.Translator(deepl_api_key)

if not os.path.exists(vocab_path):
    print(f"Vocabulary path does not exist. Using default: {vocab_default_path}")
    vocab_path = vocab_default_path


def filter_raw_words(data, previous_translations):
    seen = set(previous_translations)
    filtered_data = []
    for word, usage, _ in data:
        word_clean = word[3:].lower()
        if word_clean not in seen:
            seen.add(word_clean)
            filtered_data.append((word_clean, usage))

    return filtered_data


def download_audio(scraper, word, audio_url, book_name):
    if not audio_url:
        print(f"❌ No audio found for {word}")
        return

    folder = f"audio/{book_name.lower().replace(" ", "_")}"
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, f"{word}.mp3")

    try:
        response = scraper.try_get_audio(audio_url)
        if response.status_code == 200:
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"🔊 Audio saved: {file_path}")
        else:
            print(f"❌ Failed to download audio for {word} (Status: {response.status_code})")
    except Exception as e:
        print(f"❌ Error downloading audio for {word}: {e}")


def fallback_translate_with_deepl(word):
    try:
        result = deepl_translator.translate_text(word, source_lang="EN", target_lang="CS")
        return {
            "word": word,
            "pronunciation": None,
            "audio_url": None,
            "definitions": [result.text],
            "phrases": []
        }
    except deepl.DeepLException as e:
        print(f"❌ DeepL API error for {word}: {e}")
        return None


def fetch_translations(filtered_data, book_name, limit=None):
    scraper = LingeaScraper()
    translations = {}

    if not limit:
        limit = len(filtered_data)

    for i, (word, usage) in enumerate(filtered_data[0:limit], start=1):
        print(f"[{i}/{limit}] Fetching: {word}...")
        word_data = scraper.get_word_data(word)

        if not word_data:
            print(f"⚠ Lingea failed, falling back to DeepL for: {word}")
            word_data = fallback_translate_with_deepl(word)

        if word_data:
            print(f"  ✔ Successfully fetched: {word}")
            audio_url = word_data.get("audio_url")
            if audio_url:
                download_audio(scraper, word, audio_url, book_name)

            translations[word] = {
                "translation": word_data,
                "usage": usage
            }
        else:
            print(f"❌ Could not fetch translation for '{word}' from either Lingea or DeepL.")

        time.sleep(3)

    return translations


def save_translations_to_file(translations, book_title):
    os.makedirs("translations", exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d")
    book_title = book_title.lower().replace(" ", "_")
    filename = f"{book_title}+{timestamp}.json"

    with open(f"translations/{filename}", "w", encoding="utf-8") as f:
        json.dump(translations, f, indent=4, ensure_ascii=False)

    print(f"📁 Translations saved to '{filename}'")

    return filename


def get_latest_export(book_title, folder = "./translations") -> str | None:
    prefix = book_title.replace(" ", "_").lower()
    matches = [f for f in os.listdir(folder) if f.startswith(prefix)]

    if not matches:
        return None

    return sorted(matches, reverse=True)[0]

def main():
    connection = sqlite3.connect(vocab_path)
    cursor = connection.cursor()

    books = cursor.execute("SELECT id, title, lang FROM BOOK_INFO;").fetchall()

    for i, book in enumerate(books):
        print(f"{i + 1}. {book[1]} ({book[2]})")

    selected_index = int(input("Select book: ")) - 1
    selected_book = books[selected_index]

    raw_words = cursor.execute("""
        SELECT word_key, usage, timestamp 
        FROM LOOKUPS 
        WHERE book_key = ? 
        ORDER BY timestamp ASC;
    """, (selected_book[0],)).fetchall()

    connection.close()

    dates = sorted(set(
        time.strftime("%Y-%m-%d", time.localtime(row[2] / 1000)) for row in raw_words
    ))
    print(f"Found {len(raw_words)} words in {selected_book[1]} from {dates[0]} to {dates[-1]}.")
    print(f"Here is last {min(7, len(dates))} dates:", dates[-7:])

    selected_date = input(f"Select date (Enter to skip) [{dates[0]} - {dates[-1]}]: ").strip()
    if not selected_date:
        selected_date = dates[0]  # oldest = include all words
    selected_timestamp = time.mktime(time.strptime(selected_date, "%Y-%m-%d")) * 1000

    # Filter by date in Python since raw_words is already loaded
    raw_words = [row for row in raw_words if row[2] >= selected_timestamp]

    if not raw_words:
        print("No words found from the selected date.")
        return

    print(f"Filtered to {len(raw_words)} words from {selected_date}.")

    latest_export = get_latest_export(selected_book[1])
    existing_vocab = {}

    if not latest_export:
        print("No previous export found.")
    else:
        with open(os.path.join("translations", latest_export), "r", encoding="utf-8") as f:
            existing_vocab = json.load(f)
        print(f"Loaded latest existing vocabulary with {len(existing_vocab)} words: {latest_export}")


    filtered_data = filter_raw_words(raw_words, list(existing_vocab.keys()))
    translations = fetch_translations(filtered_data, selected_book[1], limit=1)

    existing_vocab.update(translations)
    translations_name = save_translations_to_file(existing_vocab, book_title=selected_book[1])

    build_apkg(translations_name)


if __name__ == '__main__':
    main()
