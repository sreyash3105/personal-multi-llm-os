import sys
import time
from pathlib import Path

from faster_whisper import WhisperModel


# ---------- CONFIG ----------
# Default folder if none is passed as argument
DEFAULT_AUDIO_DIR = r"C:\Users\user\Documents\test"

# Allowed extensions to scan
ALLOWED_EXTS = {".wav", ".m4a", ".mp3", ".webm", ".ogg"}
# -----------------------------


def main():
    # 1) Decide which folder to use
    if len(sys.argv) >= 2:
        audio_dir = Path(sys.argv[1])
    else:
        audio_dir = Path(DEFAULT_AUDIO_DIR)

    if not audio_dir.is_dir():
        print(f"[!] Not a directory: {audio_dir}")
        sys.exit(1)

    # 2) Collect files
    files = sorted(
        f for f in audio_dir.iterdir()
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTS
    )

    if not files:
        print(f"[!] No audio files found in {audio_dir}")
        sys.exit(0)

    print(f"[+] Found {len(files)} audio files in {audio_dir}")

    # 3) Load model ONCE
    print("[+] Loading model 'small' on CUDA...")
    t0 = time.time()
    model = WhisperModel("small", device="cuda", compute_type="float16")
    print(f"[+] Model loaded in {time.time() - t0:.2f}s")

    # 4) Transcribe each file
    for f in files:
        print("\n=============================")
        print(f"▶ {f.name}")
        print("=============================")

        start = time.time()
        segments, info = model.transcribe(str(f), language="en")  # or language=None
        text = " ".join(seg.text for seg in segments)
        dt = time.time() - start

        print(f"Text: {text}")
        print(f"Language: {info.language} (p={info.language_probability:.2f})")
        print(f"Time: {dt:.2f}s")

    print("\n=== DONE ===")


if __name__ == "__main__":
    main()
