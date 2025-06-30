import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

CONFIG_PATH = os.path.join(BASE_DIR, "config", "settings.yaml")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
DATA_DIR = os.path.join(BASE_DIR, "data")

# Ensure these exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
