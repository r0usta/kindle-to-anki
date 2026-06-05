import requests
from bs4 import BeautifulSoup

class LingeaScraper:
    BASE_URL = "https://slovniky.lingea.cz/anglicko-cesky/"

    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/118.0.5993.90 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Connection": "keep-alive",
        }

    def try_get_audio(self, audio_url):
        return requests.get(audio_url, headers=self.headers, stream=True)

    def get_word_data(self, word):
        url = f"{self.BASE_URL}{word}"

        try:
            response = requests.get(url, headers=self.headers)
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error: {e}")
            return None

        if response.status_code != 200:
            print(f"❌ Failed to fetch {word} (Status: {response.status_code})")
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        wrapper = soup.find(id="entry-wrapper")

        if not wrapper or not wrapper.table:
            print(f"❌ No data found for {word}")
            return None  # ! No valid data found

        return LingeaParser.parse_entry(wrapper.table)

    @staticmethod
    def extract_translation(tr):
        translation_td = tr.select_one("td span.lex_ful_tran.w.l2")
        description_td = tr.select_one("td span.lex_ful_desc2.w.l2")

        translation = translation_td.get_text(" ", strip=True) if translation_td else None
        description = description_td.get_text(" ", strip=True) if description_td else None

        return translation or description  # Prefer translation, fallback to description

class LingeaParser:
    @staticmethod
    def parse_entry(soup):
        word = LingeaParser.get_word(soup)
        pronunciation = LingeaParser.get_pronunciation(soup)
        pronunciation_audio = LingeaParser.get_pronunciation_audio(soup)  # New function
        definitions = LingeaParser.get_definitions(soup)
        phrases = LingeaParser.get_phrases(soup)

        return {
            "word": word,
            "pronunciation": pronunciation,
            "audio_url": pronunciation_audio,  # Include audio URL
            "definitions": definitions,
            "phrases": phrases
        }

    @staticmethod
    def get_pronunciation_audio(soup):
        audio_element = soup.select_one("span.lex_ful_wsnd")

        sid = audio_element.get_text(strip=True) if audio_element else None

        if sid :
            return f"https://slovniky.lingea.cz/audio/en/{sid}"  # Construct URL
        else:
            return None

    @staticmethod
    def get_word(soup):
        word = soup.select_one("h1.lex_ful_entr")
        return word.get_text(strip=True) if word else None

    @staticmethod
    def get_pronunciation(soup):
        pronunciation = soup.select_one("span.lex_ful_pron")
        return pronunciation.get_text(strip=True) if pronunciation else None

    @staticmethod
    def get_definitions(soup):
        definitions = []
        seen_translations = set()  # Track unique translations

        for pos_section in soup.select("span.lex_ful_morf"):
            tr_blocks = pos_section.find_parent("tr").find_next_siblings("tr")

            for tr in tr_blocks:
                final_translation = LingeaScraper.extract_translation(tr)
                if final_translation and final_translation not in seen_translations:
                    seen_translations.add(final_translation)
                    definitions.append(final_translation)

        return definitions

    @staticmethod
    def get_phrases(soup):
        phrases = []
        phrase_rows = soup.select("tr")

        for tr in phrase_rows:
            phrase_en = tr.select_one("span.lex_ful_phrs.w.l1")
            phrase_cz = tr.select_one("span.lex_ful_tran.w.l2")

            if phrase_en and phrase_cz:
                phrases.append({
                    "english": phrase_en.get_text(strip=True),
                    "czech": phrase_cz.get_text(" ", strip=True)
                })

        return phrases
