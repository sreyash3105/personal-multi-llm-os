# test_stt_load.py
import traceback
import sys
import time

try:
    print("Python:", sys.version)
    start = time.time()
    from faster_whisper import WhisperModel
    print("Imported faster_whisper ok.")
    MODEL = "tiny.en"  # quickest CPU-friendly model for testing
    print(f"Attempting to load model {MODEL} on CPU (this may take 10-60s)...")
    m = WhisperModel(MODEL, device="cpu", compute_type="float32")
    print("Model loaded successfully in %.1fs" % (time.time() - start))
    # quick small transcribe test: skip, we only load to see errors
except Exception as e:
    print("Exception while loading model:")
    traceback.print_exc()
    raise
