"""Apply cup-handle volume-price patch to patterns.py"""
import sys
sys.path.insert(0, '.')
from backend.patterns import detect_patterns, detect_cup_handle, _detect_volume_price_patterns
