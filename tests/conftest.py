# -*- coding: utf-8 -*-
"""Đưa project root vào sys.path để test import được cleaners/validators/..."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
