import sys
import os
import time
import threading
import queue
import logging
import io
import tkinter as tk
import numpy as np
import sounddevice as sd
import soundfile as sf
from pynput import keyboard

# --- [START FIX] NVIDIA DLL PATHS ---
# This determines if the script crashes. It must run BEFORE importing backend modules.
libs_paths = [
    os.path.join(sys.prefix, 'Lib', 'site-packages', 'nvidia', 'cudnn', 'bin'),
    os.path.join(sys.prefix, 'Lib', 'site-packages', 'nvidia', 'cublas', 'bin'),
    os.path.join(sys.prefix, 'Lib', 'site-packages', 'nvidia', 'cudart', 'bin'),
]
for lib_path in libs_paths:
    if os.path.exists(lib_path) and lib_path not in os.environ['PATH']:
        os.environ['PATH'] = lib_path + os.pathsep + os.environ['PATH']
# --- [END FIX] ----------------------

# --- Backend Setup ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.modules.stt.stt_service import STTService
from backend.modules.planner.planner import Planner
from backend.modules.automation.executor import plan_and_execute
from backend.modules.chat.chat_pipeline import run_chat_smart
from backend.modules.chat.chat_storage import get_profile

# --- Config ---
PROFILE_ID = "A"  # Default profile
HOTKEY_COMBINATION = {keyboard.Key.ctrl_l, keyboard.Key.alt_l, keyboard.Key.space}
SAMPLE_RATE = 16000

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger("GhostAgent")

class OverlayWindow:
    """The Futuristic HUD Overlay"""
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)  # No frame/borders
        self.root.attributes("-topmost", True)  # Always on top
        self.root.attributes("-alpha", 0.85)  # Glassy transparency
        self.root.configure(bg="#050505")
        
        # Position: Bottom Center
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = 800, 150
        x = (sw - w) // 2
        y = sh - h - 120 
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        # UI Elements
        self.label = tk.Label(
            self.root, 
            text="GHOST AGENT ONLINE", 
            font=("Consolas", 14, "bold"), 
            fg="#00ff00", 
            bg="#050505", 
            wraplength=780,
            justify="center"
        )
        self.label.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Message Queue for Thread Safety
        self.queue = queue.Queue()
        self.root.after(100, self._process_queue)
        
        # Hide initially
        self.root.withdraw()

    def show(self, text, color="#00ff00", duration=0):
        """Thread-safe update"""
        self.queue.put(("show", text, color, duration))

    def _process_queue(self):
        try:
            while True:
                cmd, text, color, duration = self.queue.get_nowait()
                if cmd == "show":
                    self.label.config(text=text, fg=color)
                    self.root.deiconify()
                    if duration > 0:
                        self.root.after(duration * 1000, self.root.withdraw)
        except queue.Empty:
            pass
        self.root.after(100, self._process_queue)

    def start(self):
        self.root.mainloop()

# --- Global State ---
overlay = None
is_listening = False
audio_buffer = []
current_keys = set()

# --- Audio Logic ---
def audio_callback(indata, frames, time, status):
    if is_listening:
        audio_buffer.append(indata.copy())

def process_voice_command():
    """The Brain Logic: Audio -> Text -> Plan -> Action/Reply"""
    global audio_buffer
    
    if not audio_buffer:
        return

    overlay.show("Thinking...", color="#ffff00") # Yellow
    
    # 1. Process Audio
    recording = np.concatenate(audio_buffer, axis=0)
    wav_io = io.BytesIO()
    sf.write(wav_io, recording, SAMPLE_RATE, format='WAV')
    wav_bytes = wav_io.getvalue()
    audio_buffer = [] # Clear

    try:
        stt = STTService()
        transcript = stt.transcribe_bytes(wav_bytes)
        user_text = transcript.get("text", "").strip()
    except Exception as e:
        overlay.show(f"Ear Malfunction: {e}", color="#ff0000", duration=4)
        print(f"ERROR DETAILS: {e}")
        return

    if not user_text:
        overlay.show("Heard nothing.", color="#555555", duration=2)
        return

    overlay.show(f"'{user_text}'", color="#00ffff") # Cyan

    # 2. The Planner
    try:
        planner = Planner.shared()
        context = {"profile_id": PROFILE_ID, "source": "ghost_overlay"}
        
        plan = planner.plan_request(user_text, context)
        intent = plan.get("intent", "chat")
        
        log.info(f"Intent: {intent} | Text: {user_text}")

        # 3. Execution Branch
        if intent in ["automation", "code", "vision", "file_op", "tool"]:
            # --- DOER MODE (Silent Execution) ---
            overlay.show(f"Executing ({intent})...", color="#ff00ff")
            
            res = plan_and_execute(user_text, context=context, execute=True)
            
            if res.get("ok"):
                overlay.show("✅ Done", color="#00ff00", duration=3)
            else:
                overlay.show(f"❌ Error: {res.get('error')}", color="#ff0000", duration=5)

        else:
            # --- CHATTER MODE (Overlay Answer) ---
            prof = get_profile(PROFILE_ID) or {"id": "A", "display_name": "GhostUser"}
            
            response = run_chat_smart(
                profile=prof,
                profile_id=PROFILE_ID,
                chat_meta={"id": "ghost_chat"},
                chat_id="ghost_chat",
                messages=[], 
                user_prompt=user_text
            )
            
            answer = response.get("answer", "")
            # Show answer for 15s so you can read it
            overlay.show(answer, color="#ffffff", duration=15)

    except Exception as e:
        log.exception("Ghost Error")
        overlay.show(f"System Failure: {e}", color="#ff0000", duration=5)

# --- Input Listeners ---
def on_press(key):
    global is_listening, audio_buffer
    if key in HOTKEY_COMBINATION:
        current_keys.add(key)
        if all(k in current_keys for k in HOTKEY_COMBINATION):
            if not is_listening:
                is_listening = True
                audio_buffer = []
                overlay.show("🎤 Listening...", color="#00ff00")

def on_release(key):
    global is_listening
    try:
        current_keys.remove(key)
    except KeyError:
        pass
    
    # If keys released, stop listening and process
    if is_listening and not all(k in current_keys for k in HOTKEY_COMBINATION):
        is_listening = False
        threading.Thread(target=process_voice_command).start()

# --- Entry Point ---
if __name__ == "__main__":
    print("\n👻 GHOST AGENT INITIALIZED")
    print("   Target: D:\\AIOS\\personal-multi-llm-os")
    print("   Action: Hold [Ctrl + Alt + Space] to speak.")
    
    # Start Audio Stream
    stream = sd.InputStream(callback=audio_callback, channels=1, samplerate=SAMPLE_RATE)
    stream.start()

    # Start Keyboard Listener
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    # Start UI (Main Thread)
    overlay = OverlayWindow()
    overlay.start()