import json
import sqlite3
import time
import os
import deepl

from modules.lingea_api import LingeaScraper
from dotenv import load_dotenv

load_dotenv()

vocab_default_path = "./vocab.db"
deepl_api_key = None

vocab_path = os.getenv("VOCAB_PATH", default=vocab_default_path)
deepl_api_key = os.getenv("DEEPL_API_KEY", default=deepl_api_key)

deepl_translator = deepl.Translator(deepl_api_key)

if not os.path.exists(vocab_path):
    print(f"Vocabulary path does not exist. Using default: {vocab_default_path}")
    vocab_path = vocab_default_path


def fetch_filtered_data():
    connection = sqlite3.connect(vocab_path)
    cursor = connection.cursor()
    res = cursor.execute("SELECT word_key, usage FROM LOOKUPS;")
    data = res.fetchall()

    seen = set()
    filtered_data = []
    for word, usage in data:
        word_clean = word[3:].lower()
        if word_clean not in seen:
            seen.add(word_clean)
            filtered_data.append((word_clean, usage))

    return filtered_data


def download_audio(word, audio_url, folder="audio"):
    if not audio_url:
        print(f"❌ No audio found for {word}")
        return

    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, f"{word}.mp3")

    try:
        response = requests.get(audio_url, stream=True)
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


def fetch_translations(filtered_data, limit=None):
    scraper = LingeaScraper()
    translations = {}

    for i, (word, usage) in enumerate(filtered_data, start=1):
        print(f"[{i}/{len(filtered_data)}] Fetching: {word}...")
        word_data = scraper.get_word_data(word)

        if not word_data:
            print(f"⚠ Lingea failed, falling back to DeepL for: {word}")
            word_data = fallback_translate_with_deepl(word)

        if word_data:
            print(f"  ✔ Successfully fetched: {word}")
            audio_url = word_data.get("audio_url")
            if audio_url:
                download_audio(word, audio_url)

            translations[word] = {
                "translation": word_data,
                "usage": usage
            }
        else:
            print(f"❌ Could not fetch translation for '{word}' from either Lingea or DeepL.")

        time.sleep(3)

    return translations


def save_translations_to_file(translations):
    os.makedirs("translations", exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"translations/{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(translations, f, indent=4, ensure_ascii=False)

    print(f"📁 Translations saved to '{filename}'")


def main():
    # Fetch and filter data from database
    filtered_data = fetch_filtered_data()

    # Fetch translations for filtered words
    translations = fetch_translations(filtered_data, 5)

    # Save translations to file
    save_translations_to_file(translations)


if __name__ == '__main__':
    main()
