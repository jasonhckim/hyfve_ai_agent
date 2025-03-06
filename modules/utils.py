import logging
import time
import os
import json
import re

def setup_logging(log_file="script.log"):
    """Sets up logging configuration."""
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

def wait(seconds):
    """Pauses execution for a given number of seconds."""
    print(f"⏳ Waiting {seconds} seconds...")
    time.sleep(seconds)

def get_env_variable(var_name, default=None):
    """Gets an environment variable or returns a default value."""
    value = os.getenv(var_name, default)
    if value is None:
        print(f"⚠️ WARNING: {var_name} is not set!")
    return value

def load_json(file_path):
    """Loads a JSON file and returns the data."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as e:
        print(f"❌ ERROR: Could not read {file_path}. {e}")
        return None

def save_json(file_path, data):
    """Saves data to a JSON file."""
    try:
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
        print(f"✅ Saved data to {file_path}")
    except Exception as e:
        print(f"❌ ERROR: Could not save {file_path}. {e}")

# ✅ Add This at the Bottom
def extract_keywords_from_doc(file_path):
    """Extracts keywords from a TXT file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            keywords = f.read().splitlines()
        return [kw.strip() for kw in keywords if kw.strip()]
    except Exception as e:
        print(f"❌ ERROR: Could not extract keywords from {file_path}. Debug: {e}")
        return []
