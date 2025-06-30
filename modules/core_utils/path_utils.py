import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

CONFIG_PATH = os.path.join(BASE_DIR, "config", "settings.yaml")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
DATA_DIR = os.path.join(BASE_DIR, "data")

