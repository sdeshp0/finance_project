import yaml
import os
from modules.core_utils.path_utils import CONFIG_PATH


def load_config(default=None):
    if default is None:
        default = {"retry_delay_seconds": 1, "max_retries": 2}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    else:
        print(f"[WARN] No config file found at {CONFIG_PATH}. Using defaults.")
        return default
