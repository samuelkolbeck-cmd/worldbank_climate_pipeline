"""utils.py — Shared utilities."""

import logging
import sys
from pathlib import Path
import yaml
from typing import Dict


def setup_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """Set up a logger that writes to file + stdout."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_path = f"{log_dir}/pipeline.log"

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)

    fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def load_yaml(path: str) -> Dict:
    """Load a YAML config file."""
    with open(path, 'r') as f:
        return yaml.safe_load(f)
