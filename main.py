from dotenv import load_dotenv
import os

load_dotenv()

dict_default_path = "./dict.azw"
vocab_default_path = "./vocab.db"

dict_path = os.getenv("DICT_PATH", default=dict_default_path)
vocab_path = os.getenv("VOCAB_PATH", default=vocab_default_path)

if not os.path.exists(dict_path):
    print(f"Dictionary path does not exist. Using default: {dict_default_path}")
    dict_path = dict_default_path

if not os.path.exists(vocab_path):
    print(f"Vocabulary path does not exist. Using default: {vocab_default_path}")
    vocab_path = vocab_default_path

# ! if __name__ == '__main__':