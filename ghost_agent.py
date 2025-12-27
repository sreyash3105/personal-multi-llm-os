import sys
import os
import time
import threading
import queue
import logging
import io
import subprocess
import tkinter as tk
import numpy as np
import sounddevice as sd
import soundfile as sf
from concurrent.futures import ThreadPoolExecutor
from pynput import keyboard
from pathlib import Path

# --- [START FIX] NVIDIA DLL PATHS ---
# Ensures GPU acceleration works before loading heavy AI libraries
# This block must run first.
try:
    base_nvidia_path = Path(sys.prefix) / 'Lib' / 'site-packages' / 'nvidia'
    libs_paths = [
        base_nvidia_path / 'cudnn' / 'bin',
        base_nvidia_path / 'cublas' / 'bin',
        base_nvidia_path / 'cudart' / 'bin',
    ]
    for lib_path in libs_paths:
        if lib_path.exists() and str(lib_path) not in os.environ['PATH']:
            os.add_dll_directory(str(lib_path))
            os.environ['PATH'] = str(lib_path) + os.pathsep + os.environ['PATH']
except Exception as e:
    print(f"Warning: GPU DLL linking failed: {e}")
# --- [END FIX] ----------------------

# --- Backend Setup ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import your modules (Ensure these files exist in your folder structure)
try:
    from backend.modules.stt.stt_service import STTService
    from backend.modules.planner.planner import Planner
    from backend.modules.automation.executor import plan_and_execute
    from backend.modules.chat.chat_pipeline import run_chat_smart
    from backend.modules.chat.chat_storage import get_profile
except ImportError as e:
    print(f"CRITICAL ERROR: Missing backend modules. {e}")
    sys.exit(1)

# --- Config ---
PROFILE_ID = "A"  # Default profile
HOTKEY_COMBINATION = {keyboard.Key.ctrl_l, keyboard.Key.alt_l, keyboard.Key.space}
SAMPLE_RATE = 16000

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger("GhostAgent")

# --- Global State ---
is_listening = False
_abort_flag = False
current_keys = set()

# Thread pool for voice command processing (bounded to prevent explosion)
VOICE_THREAD_POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="voice_cmd")
server_proc = None
dash_proc = None
stream = None
listener = None

# --- UI Class ---
class OverlayWindow:
    """The Futuristic HUD Overlay"""
    def __init__(self, cleanup_callback):
        self.cleanup_callback = cleanup_callback
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
        
        # Handle Close Event safely
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
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
                        self.root.after(int(duration * 1000), self.root.withdraw)
        except queue.Empty:
            pass
        self.root.after(100, self._process_queue)

    def on_close(self):
        """Called when the user wants to exit"""
        print("\n>>> EXIT COMMAND RECEIVED")
        self.cleanup_callback()
        self.root.destroy()
        sys.exit(0)

    def start(self):
        self.root.mainloop()

# --- Audio Logic ---
def audio_callback(indata, frames, time, status):
    if is_listening:
        audio_buffer.append(indata.copy())

def process_voice_command():
    """The Brain Logic: Audio -> Text -> Plan -> Action/Reply"""
    global audio_buffer
    
    # Atomic Swap to prevent race conditions
    if not audio_buffer:
        return

    local_buffer = audio_buffer
    audio_buffer = [] 
    
    overlay.show("Thinking...", color="#ffff00") # Yellow
    
    # 1. Process Audio
    try:
        recording = np.concatenate(local_buffer, axis=0)
        wav_io = io.BytesIO()
        sf.write(wav_io, recording, SAMPLE_RATE, format='WAV')
        wav_bytes = wav_io.getvalue()
    except Exception as e:
        overlay.show(f"Ear Malfunction: {e}", color="#ff0000", duration=4)
        print(f"ERROR DETAILS: {e}")
        return

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
        VOICE_THREAD_POOL.submit(process_voice_command)

# --- Bootloader Logic ---
def boot_system_services():
    """
    Auto-starts the Brain (Server) and Dashboard if they aren't running.
    """
    print(">>> 👻 GHOST OS BOOT SEQUENCE STARTED")

    # 1. Start the Brain (API Server)
    print("   [1/3] Igniting Brain (code_server.py)...")
    try:
        # Uses python from current env
        s_proc = subprocess.Popen(
            [sys.executable, "backend/code_server.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
    except Exception as e:
        print(f"   !!! Failed to start Brain: {e}")
        s_proc = None

    # 2. Start the Watchtower (Dashboard)
    print("   [2/3] Launching Watchtower (dashboard_app.py)...")
    time.sleep(2.0) # Wait for server
    try:
        d_proc = subprocess.Popen(
            [sys.executable, "dashboard_app.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
    except Exception as e:
        print(f"   !!! Failed to start Dashboard: {e}")
        d_proc = None
    
    return s_proc, d_proc

def global_cleanup():
    """Kills background processes when main app closes"""
    print("\n>>> SHUTTING DOWN...")
    if server_proc:
        print("    Killing Brain...")
        server_proc.terminate()
        try:
            server_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server_proc.kill()
            server_proc.wait()
    if dash_proc:
        print("    Killing Dashboard...")
        dash_proc.terminate()
        try:
            dash_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            dash_proc.kill()
            dash_proc.wait()

    # Shutdown voice command thread pool
    print("    Shutting down voice threads...")
    VOICE_THREAD_POOL.shutdown(wait=True)

    # Stop audio stream
    if stream:
        print("    Stopping audio stream...")
        stream.stop()
        stream.close()

    # Stop keyboard listener
    if listener:
        print("    Stopping keyboard listener...")
        listener.stop()

# --- Main Entry Point ---
if __name__ == "__main__":
    global stream, listener
    # A. Boot Backend Services
    server_proc, dash_proc = boot_system_services()

    print("   [3/3] Connecting Body (Overlay)...")
    print("\n✅ GHOST AGENT ONLINE")
    print(f"   Target: {os.getcwd()}")
    print("   Action: Hold [Ctrl + Alt + Space] to speak.")

    # B. Start Audio Stream
    try:
        stream = sd.InputStream(callback=audio_callback, channels=1, samplerate=SAMPLE_RATE)
        stream.start()
    except Exception as e:
        print(f"CRITICAL: Audio device failed. {e}")
        stream = None

    # C. Start Keyboard Listener
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

if __name__ == "__main__":
    # D. Start UI (Blocking)
    # This keeps the script running indefinitely
    try:
        overlay = OverlayWindow(cleanup_callback=global_cleanup)
        overlay.start() 
    except KeyboardInterrupt:
        # Handles Ctrl+C in terminal
        global_cleanup()
        sys.exit(0)