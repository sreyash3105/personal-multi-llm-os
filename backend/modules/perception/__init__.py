"""
perception module (Phase B)

Core confidence-gating logic for STT and Vision perception inputs.
Ensures perception results are validated before action.
"""

from .confidence_gates import *
from .stt_confidence import *
from .vision_confidence import *