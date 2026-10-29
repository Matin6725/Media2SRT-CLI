# ==============================================================================
# Media2SRT-CLI - AI-Powered Video/Audio to SRT Transcriber & Subtitle Translator
# Repository: https://github.com/Matin6725/Media2SRT-CLI
# License: MIT License (Copyright (c) 2026 Matin6725)
# ==============================================================================

import os
import sys
import time
import json
import shutil
import zipfile
import tarfile
import pathlib
import difflib
import platform
import threading
import subprocess
import urllib.request
from google import genai

# Cross-platform non-blocking keyboard modules (built-in)
if os.name == "nt":
    import msvcrt
else:
    import select
    import tty
    import termios

# ==========================================
# CONFIGURATION & SETTINGS
# ==========================================
# Target Gemini Model for audio transcription
GEMINI_MODEL = "gemini-3.5-transcribe"

# Target Gemini Model for subtitle translation
TRANSLATION_MODEL = "gemini-3.5-flash-lite"

# Base prompt for non-SRT (.ass, etc.) subtitle translation
BASE_TRANSLATION_PROMPT = (
    "You are a film translator. I will provide you with a subtitle file; "
    "please translate it without altering the timing structure."
)

# Optimized JSON-only prompt for .srt subtitle translation (timestamps stay in Python)
BASE_SRT_JSON_TRANSLATION_PROMPT = (
    "You are a professional subtitle translator. "
    "You will receive a JSON array of subtitle items, each containing an \"index\" and a \"text\" field. "
    "Translate ONLY the \"text\" field of each item according to the instructions and return ONLY a valid JSON array. "
    "Each returned object MUST have the exact same \"index\" value and a \"translation\" field containing the translated text. "
    "Preserve internal line breaks (\\n) within multi-line texts naturally. "
    "Strictly DO NOT add, remove, merge, split, or reorder any items, and DO NOT include any explanations or markdown formatting."
)

# Maximum translation chunk size in thousands of characters/tokens (e.g. 64 = 64,000 characters)
MAX_TRANSLATE_TOKENS_K = 64

# Memory variable to store the last generated subtitle in the current session
LAST_GENERATED_SUBTITLE = None

# API Key: Set string here (highest priority), or leave None to use config.json
GEMINI_API_KEY = None

# Config file and local bin directory stored beside the script
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
CONFIG_FILE = SCRIPT_DIR / "config.json"
LOCAL_FFMPEG_DIR = SCRIPT_DIR / "ffmpeg_bin"

# Proxy Settings (SOCKS5 support)
USE_PROXY = False
PROXY_TYPE = "socks5"
PROXY_IP = "127.0.0.1"
PROXY_PORT = "2080"

# Enable or disable two-line subtitles:
# True  = Allows up to 16 words per frame split into 2 lines (max 8 words/line).
# False = Strictly forces single-line subtitles (max 8 words per frame).
ALLOW_TWO_LINES = True

MAX_WORDS_PER_LINE = 10
MAX_CHARS_PER_LINE = 42
MIN_DURATION = 1.5          # Minimum frame display time (seconds)
MAX_DURATION = 6.0          # Maximum frame display time (seconds)
MAX_GAP = 1.0               # Pause duration (seconds) to trigger a split

# Video Splitting & Chunking Settings
# If SPLIT_DURATION_MINUTES is not None, videos longer than this value (in minutes)
# are automatically split into chunks. Each cut happens 1 minute before the limit
# (e.g. 30 -> 29 min cuts). Consecutive chunks start earlier with seamless overlap.
# Set to None to disable splitting and process the entire video at once.
SPLIT_DURATION_MINUTES = 30

# Internal optimal overlap duration (seconds) to ensure speech isn't abruptly cut at boundaries
# 12.0 seconds corresponds to 2x MAX_DURATION, allowing full sentences and reliable text alignment
CHUNK_OVERLAP_SECONDS = MAX_DURATION * 2

# Supported languages from Gemini 3.5 Transcribe documentation (ss.md)
SUPPORTED_LANGUAGES = {
    "af-ZA": "Afrikaans",
    "am-ET": "Amharic",
    "ar-EG": "Arabic (Egypt)",
    "hy-AM": "Armenian",
    "as-IN": "Assamese",
    "az-AZ": "Azerbaijani",
    "be-BY": "Belarusian",
    "bn-BD": "Bengali (Bangladesh)",
    "bn-IN": "Bengali (India)",
    "bs-BA": "Bosnian",
    "bg-BG": "Bulgarian",
    "rup-BG": "Bulgarian (Aromanian)",
    "my-MM": "Burmese",
    "yue-Hant-HK": "Cantonese (Traditional)",
    "ca-ES": "Catalan",
    "ceb": "Cebuano",
    "km-KH": "Central Khmer",
    "hr-HR": "Croatian",
    "cs-CZ": "Czech",
    "da-DK": "Danish",
    "nl-NL": "Dutch",
    "en-GB": "English (Great Britain)",
    "en-IN": "English (India)",
    "en-US": "English (United States)",
    "et-EE": "Estonian",
    "fa-IR": "Farsi",
    "fil-PH": "Filipino",
    "fi-FI": "Finnish",
    "fr-FR": "French",
    "gl-ES": "Galician",
    "ka-GE": "Georgian",
    "de-DE": "German",
    "el-GR": "Greek",
    "gu-IN": "Gujarati",
    "ha-NG": "Hausa",
    "he-IL": "Hebrew",
    "hi-IN": "Hindi",
    "hu-HU": "Hungarian",
    "is-IS": "Icelandic",
    "id-ID": "Indonesian",
    "it-IT": "Italian",
    "ja-JP": "Japanese",
    "jv-ID": "Javanese",
    "kea-CV": "Kabuverdianu",
    "kn-IN": "Kannada",
    "kk-KZ": "Kazakh",
    "ko-KR": "Korean",
    "ky-KG": "Kyrgyz",
    "lv-LV": "Latvian",
    "ln-CD": "Lingala",
    "lt-LT": "Lithuanian",
    "mk-MK": "Macedonian",
    "ms-MY": "Malay",
    "ml-IN": "Malayalam",
    "mt-MT": "Maltese",
    "cmn-Hans-CN": "Mandarin Chinese (Simplified)",
    "mr-IN": "Marathi",
    "mn-MN": "Mongolian",
    "ne-NP": "Nepali",
    "nb-NO": "Norwegian",
    "or-IN": "Oriya",
    "pl-PL": "Polish",
    "pt-BR": "Portuguese (Brazil)",
    "pt-PT": "Portuguese (Portugal)",
    "pa-IN": "Punjabi",
    "pa-Guru-IN": "Punjabi (Gurmukhi script)",
    "ro-RO": "Romanian",
    "ru-RU": "Russian",
    "sr-RS": "Serbian",
    "sd-Arab-IN": "Sindhi (Arabic script)",
    "sk-SK": "Slovak",
    "sl-SI": "Slovenian",
    "es-419": "Spanish (Latin America)",
    "es-US": "Spanish (United States)",
    "sw-KE": "Swahili (Kenya)",
    "sv-SE": "Swedish",
    "tg-TJ": "Tajik",
    "te-IN": "Telugu",
    "th-TH": "Thai",
    "tr-TR": "Turkish",
    "uk-UA": "Ukrainian",
    "uz-UZ": "Uzbek",
    "vi-VN": "Vietnamese"
}


# ==========================================
# CONTROL FLOW EXCEPTIONS
# ==========================================

class TaskCancelled(Exception):
    """Raised when the user presses 'c' to cancel the current task and return to the main menu."""
    pass


class QuitProgram(Exception):
    """Raised when the user presses 'q' to safely clean up and exit the program."""
    pass


# ==========================================
# CROSS-PLATFORM NON-BLOCKING KEY MONITOR
# ==========================================

class NonBlockingKeyMonitor:
    """
    Context manager that enables non-blocking single-key detection ('q' or 'c')
    across Windows, Linux, and macOS without requiring the user to press Enter.
    """
    def __init__(self):
        self.fd = None
        self.old_settings = None

    def __enter__(self):
        if os.name == "nt":
            while msvcrt.kbhit():
                msvcrt.getwch()
        else:
            if sys.stdin.isatty():
                try:
                    self.fd = sys.stdin.fileno()
                    self.old_settings = termios.tcgetattr(self.fd)
                    tty.setcbreak(self.fd)
                except Exception:
                    self.fd = None
                    self.old_settings = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if os.name != "nt" and self.fd is not None and self.old_settings is not None:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
            except Exception:
                pass

    def check_action_key(self) -> str | None:
        """Returns 'q' if user pressed 'q'/'Q', 'c' if user pressed 'c'/'C', else None."""
        if os.name == "nt":
            while msvcrt.kbhit():
                ch = msvcrt.getwch().lower()
                if ch in ("q", "c"):
                    return ch
            return None
        else:
            if self.fd is not None:
                try:
                    dr, _, _ = select.select([sys.stdin], [], [], 0)
                    while dr:
                        ch = sys.stdin.read(1).lower()
                        if ch in ("q", "c"):
                            return ch
                        dr, _, _ = select.select([sys.stdin], [], [], 0)
                except Exception:
                    pass
            return None


def format_elapsed_mm_ss(elapsed_seconds: float) -> str:
    """Formats elapsed seconds into 'MMm SSs'."""
    total_secs = int(max(0, elapsed_seconds))
    mins = total_secs // 60
    secs = total_secs % 60
    return f"{mins:02d}m {secs:02d}s"


def run_with_timer_and_cancel(task_fn, status_prefix: str, on_cancel=None):
    """
    Executes `task_fn()` in a background daemon thread while displaying an in-place
    single-line elapsed timer (MMm SSs) and listening for:
      - 'c': cancel the current task, run cleanup, and return to main prompt
      - 'q': cancel the current task, run cleanup, and exit the program
    """
    result_container = {"result": None, "error": None, "done": False}

    def worker():
        try:
            result_container["result"] = task_fn()
        except Exception as e:
            result_container["error"] = e
        finally:
            result_container["done"] = True

    thread = threading.Thread(target=worker, daemon=True)
    start_time = time.time()

    with NonBlockingKeyMonitor() as monitor:
        thread.start()
        while not result_container["done"]:
            elapsed_str = format_elapsed_mm_ss(time.time() - start_time)
            line = f"\r{status_prefix} | Elapsed: {elapsed_str} (Press 'c' to cancel, 'q' to quit)   "
            sys.stdout.write(line)
            sys.stdout.flush()

            action = monitor.check_action_key()
            if action in ("c", "q"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                if action == "c":
                    print("[INFO] 'c' pressed! Cancelling current operation and returning to main menu...")
                else:
                    print("[INFO] 'q' pressed! Cancelling operation and cleaning up to exit...")

                if on_cancel:
                    try:
                        on_cancel()
                    except Exception:
                        pass

                if action == "c":
                    raise TaskCancelled()
                else:
                    raise QuitProgram()

            time.sleep(0.1)

    total_elapsed_str = format_elapsed_mm_ss(time.time() - start_time)
    sys.stdout.write(f"\r{status_prefix} | Completed in {total_elapsed_str}.                                    \n")
    sys.stdout.flush()

    if result_container["error"] is not None:
        raise result_container["error"]

    return result_container["result"]


# ==========================================
# FFMPEG AUTO-DETECTION & INSTALLATION
# ==========================================

def is_ffmpeg_available() -> bool:
    """Checks if both ffmpeg and ffprobe are available in PATH or LOCAL_FFMPEG_DIR."""
    if LOCAL_FFMPEG_DIR.exists():
        local_path = str(LOCAL_FFMPEG_DIR)
        if local_path not in os.environ.get("PATH", ""):
            os.environ["PATH"] = local_path + os.pathsep + os.environ.get("PATH", "")

    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def download_and_extract_static_ffmpeg() -> bool:
    """
    Downloads the latest stable static FFmpeg + FFprobe binaries directly into
    LOCAL_FFMPEG_DIR using only Python's standard library (no admin rights required).
    """
    sys_name = platform.system().lower()
    machine = platform.machine().lower()
    LOCAL_FFMPEG_DIR.mkdir(parents=True, exist_ok=True)

    if sys_name == "windows":
        url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        archive_path = LOCAL_FFMPEG_DIR / "ffmpeg_release.zip"
        print(f"[INFO] Downloading latest stable FFmpeg for Windows from:\n  {url}")
        urllib.request.urlretrieve(url, archive_path)
        print("[INFO] Extracting ffmpeg.exe and ffprobe.exe...")
        with zipfile.ZipFile(archive_path, "r") as zf:
            for member in zf.namelist():
                filename = os.path.basename(member)
                if filename.lower() in ("ffmpeg.exe", "ffprobe.exe"):
                    target_file = LOCAL_FFMPEG_DIR / filename
                    with zf.open(member) as src, open(target_file, "wb") as dst:
                        shutil.copyfileobj(src, dst)
        archive_path.unlink(missing_ok=True)

    elif sys_name == "linux":
        arch_tag = "arm64" if ("aarch64" in machine or "arm64" in machine) else "amd64"
        url = f"https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-{arch_tag}-static.tar.xz"
        archive_path = LOCAL_FFMPEG_DIR / "ffmpeg_release.tar.xz"
        print(f"[INFO] Downloading latest stable FFmpeg for Linux ({arch_tag}) from:\n  {url}")
        urllib.request.urlretrieve(url, archive_path)
        print("[INFO] Extracting ffmpeg and ffprobe...")
        with tarfile.open(archive_path, "r:xz") as tf:
            for member in tf.getmembers():
                filename = os.path.basename(member.name)
                if filename in ("ffmpeg", "ffprobe") and member.isfile():
                    target_file = LOCAL_FFMPEG_DIR / filename
                    src = tf.extractfile(member)
                    if src:
                        with src, open(target_file, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        os.chmod(target_file, 0o755)
        archive_path.unlink(missing_ok=True)

    else:
        return False

    os.environ["PATH"] = str(LOCAL_FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")
    return is_ffmpeg_available()

# ------------------------------------------------------------------------------
# Improved Linux/Cross-Platform FFmpeg Auto-Installer
# ------------------------------------------------------------------------------
def ensure_ffmpeg_installed():
    """
    Checks if FFmpeg/FFprobe are installed. If missing, asks the user (Y/n) to
    automatically install the latest stable release for their operating system
    and verifies the installation.
    """
    if is_ffmpeg_available():
        return

    print("\n[WARNING] FFmpeg / FFprobe was not found on your system!")
    choice = custom_input("Do you want to automatically install the latest stable FFmpeg now? (Y/n): ").lower()
    if choice not in ("", "y", "yes"):
        print("[ERROR] FFmpeg is required for video transcription. Exiting...")
        sys.exit(1)

    sys_name = platform.system().lower()
    installed = False

    try:
        if sys_name == "windows":
            if shutil.which("winget"):
                print("[INFO] Installing FFmpeg via Windows Package Manager (winget)...")
                res = subprocess.run([
                    "winget", "install", "--id", "Gyan.FFmpeg", "-e",
                    "--accept-source-agreements", "--accept-package-agreements"
                ])
                if res.returncode == 0 and is_ffmpeg_available():
                    installed = True
            if not installed:
                installed = download_and_extract_static_ffmpeg()

        elif sys_name == "linux":
            # Use sudo only if not already running as root
            is_root = ( hasattr(os, "geteuid") and os.geteuid() == 0 )
            sudo_prefix = [] if is_root else (["sudo"] if shutil.which("sudo") else [])

            # Standard non-interactive commands for major Linux distributions:
            # Debian/Ubuntu (apt-get), Fedora/RHEL (dnf), Arch/Manjaro/Artix (pacman),
            # openSUSE (zypper), Alpine (apk)
            linux_installers = [
                ("apt-get", [
                    sudo_prefix + ["apt-get", "update", "-qq"],
                    sudo_prefix + ["apt-get", "install", "-y", "-qq", "ffmpeg"]
                ]),
                ("pacman", [
                    sudo_prefix + ["pacman", "-Sy", "--needed", "--noconfirm", "ffmpeg"]
                ]),
                ("dnf", [
                    sudo_prefix + ["dnf", "install", "-y", "ffmpeg"]
                ]),
                ("zypper", [
                    sudo_prefix + ["zypper", "--non-interactive", "install", "ffmpeg"]
                ]),
                ("apk", [
                    sudo_prefix + ["apk", "add", "--no-cache", "ffmpeg"]
                ]),
            ]

            for mgr_name, cmd_list in linux_installers:
                if shutil.which(mgr_name) and (is_root or sudo_prefix):
                    print(f"[INFO] Installing FFmpeg using system package manager ('{mgr_name}')...")
                    step_ok = True
                    for cmd in cmd_list:
                        res = subprocess.run(cmd)
                        if res.returncode != 0:
                            step_ok = False
                            break
                    if step_ok and is_ffmpeg_available():
                        installed = True
                    break

            # Fallback to portable static binary if package manager failed or wasn't available
            if not installed:
                print("[INFO] Falling back to portable static FFmpeg download...")
                installed = download_and_extract_static_ffmpeg()

        elif sys_name == "darwin":
            if shutil.which("brew"):
                print("[INFO] Installing FFmpeg via Homebrew...")
                res = subprocess.run(["brew", "install", "ffmpeg"])
                if res.returncode == 0 and is_ffmpeg_available():
                    installed = True
            else:
                print("[ERROR] Homebrew ('brew') not found on macOS. Please install Homebrew or FFmpeg manually.")
    except Exception as e:
        print(f"[WARNING] Package installation encountered an error: {e}")

    # Final verification that both ffmpeg and ffprobe binaries are executable in PATH
    if is_ffmpeg_available():
        print("[SUCCESS] FFmpeg is now installed and verified!\n")
    else:
        print("[CRITICAL ERROR] Could not install FFmpeg automatically. Please install FFmpeg manually and try again.")
        sys.exit(1)


# ==========================================
# CONFIG, STATE & MULTI-API KEY MANAGEMENT
# ==========================================

def load_or_create_config():
    """
    Loads config.json from beside the script, or initializes it if it does not exist.
    Supports storing multiple named API keys and tracking the selected default key.
    """
    default_config = {
        "api_keys": {},
        "selected_api_key": "",
        "recent_languages": [],
        "active_job": None
    }

    if not CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            print(f"[INFO] Initialized configuration file: {CONFIG_FILE}")
            return default_config
        except Exception as e:
            print(f"[WARNING] Could not create {CONFIG_FILE}: {e}")
            return default_config

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if not isinstance(cfg, dict):
                cfg = default_config.copy()

            if "api_keys" not in cfg or not isinstance(cfg["api_keys"], dict):
                cfg["api_keys"] = {}
            if "selected_api_key" not in cfg or not isinstance(cfg["selected_api_key"], str):
                cfg["selected_api_key"] = ""

            # Migrate legacy single gemini_api_key if present
            legacy_key = cfg.pop("gemini_api_key", None)
            if isinstance(legacy_key, str) and legacy_key.strip() and not cfg["api_keys"]:
                cfg["api_keys"]["Key 1"] = legacy_key.strip()
                cfg["selected_api_key"] = "Key 1"
                save_config(cfg)

            if "recent_languages" not in cfg or not isinstance(cfg["recent_languages"], list):
                cfg["recent_languages"] = []
            if "active_job" not in cfg:
                cfg["active_job"] = None
            return cfg
    except Exception as e:
        print(f"[WARNING] Error reading {CONFIG_FILE}: {e}. Using defaults.")
        return default_config


def save_config(config_data: dict):
    """Saves updated config to config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARNING] Could not save config.json: {e}")


def mask_api_key(key_str: str) -> str:
    """Returns a masked preview of an API key for display."""
    k = key_str.strip()
    if len(k) <= 8:
        return "***"
    return f"{k[:4]}...{k[-4:]}"


def generate_unique_key_name(existing_keys: dict, requested_name: str = "") -> str:
    """
    Generates a unique name for an API key (similar to Windows 'New Folder').
    If `requested_name` is empty, generates 'Key 1', 'Key 2', etc.
    If `requested_name` already exists, appends an incrementing number.
    """
    existing_lower = {k.lower() for k in existing_keys.keys()}
    base = requested_name.strip()

    if not base:
        idx = 1
        while True:
            candidate = f"Key {idx}"
            if candidate.lower() not in existing_lower:
                return candidate
            idx += 1

    if base.lower() not in existing_lower:
        return base

    idx = 2
    while True:
        candidate = f"{base} {idx}"
        if candidate.lower() not in existing_lower:
            return candidate
        idx += 1


def prompt_add_new_api_key(config_data: dict, allow_cancel: bool = False) -> str | None:
    """
    Prompts the user for a new Gemini API key and a name for it,
    saves it in config.json, and sets it as the default selected key.
    """
    while True:
        prompt_msg = "Please enter your Gemini API Key (or 'c' to cancel, 'q' to quit): " if allow_cancel else "Please enter your Gemini API Key (or 'q' to quit): "
        new_key = custom_input(prompt_msg, allow_cancel=allow_cancel).strip()
        if not new_key:
            print("[ERROR] API Key cannot be empty.")
            continue
        break

    raw_name = custom_input("Enter a name for this API Key (Press Enter for auto-name): ", allow_cancel=False).strip()
    api_keys = config_data.setdefault("api_keys", {})
    final_name = generate_unique_key_name(api_keys, raw_name)

    api_keys[final_name] = new_key
    config_data["selected_api_key"] = final_name
    save_config(config_data)

    print(f"[SUCCESS] API Key saved as '{final_name}' and set as the default key!\n")
    return new_key


def ensure_api_key_configured(config_data: dict) -> str:
    """
    Retrieves the active Gemini API key with priority:
      1. In-script GEMINI_API_KEY constant (highest priority)
      2. Selected key in config.json
    If config.json has no keys and GEMINI_API_KEY is not set, immediately prompts
    the user on startup to add a key and name it.
    """
    if GEMINI_API_KEY and GEMINI_API_KEY.strip():
        return GEMINI_API_KEY.strip()

    api_keys = config_data.setdefault("api_keys", {})
    selected_name = config_data.get("selected_api_key", "")

    if selected_name in api_keys and api_keys[selected_name].strip():
        return api_keys[selected_name].strip()

    # If keys exist but selected_api_key wasn't valid, pick the first available key
    for name, val in api_keys.items():
        if isinstance(val, str) and val.strip():
            config_data["selected_api_key"] = name
            save_config(config_data)
            return val.strip()

    # No API keys found in config.json -> ask user immediately on startup
    print("\n[SETUP] No Gemini API Key found in config.json.")
    return prompt_add_new_api_key(config_data, allow_cancel=False)


def get_active_api_key(config_data: dict) -> str:
    """Returns the currently active API key string."""
    return ensure_api_key_configured(config_data)


def open_api_key_manager(config_data: dict) -> str:
    """
    Interactive API Key Manager ('m' command).
    Shows the current default key, lists all saved keys (1..N),
    option N+1 to add a new key, and option N+2 (or 'c') to cancel.
    Returns the active API key when exiting the manager.
    """
    while True:
        api_keys = config_data.setdefault("api_keys", {})
        selected_name = config_data.get("selected_api_key", "")

        if selected_name not in api_keys and api_keys:
            selected_name = next(iter(api_keys.keys()))
            config_data["selected_api_key"] = selected_name
            save_config(config_data)

        print("\n" + "=" * 52)
        print("  Gemini API Key Manager")
        print("=" * 52)
        if GEMINI_API_KEY and GEMINI_API_KEY.strip():
            print(f"  [NOTE] Hardcoded GEMINI_API_KEY in script is active ({mask_api_key(GEMINI_API_KEY)}).")
        if selected_name and selected_name in api_keys:
            print(f"  Current Default Key: {selected_name} ({mask_api_key(api_keys[selected_name])})")
        else:
            print("  Current Default Key: None")
        print("-" * 52)

        key_names = list(api_keys.keys())
        for idx, k_name in enumerate(key_names, 1):
            default_badge = " [DEFAULT]" if k_name == selected_name else ""
            print(f"  [{idx}] {k_name} ({mask_api_key(api_keys[k_name])}){default_badge}")

        add_opt = len(key_names) + 1
        cancel_opt = len(key_names) + 2
        print(f"  [{add_opt}] Add a new API key")
        print(f"  [{cancel_opt}] Cancel / Back (or type 'c' to cancel, 'q' to quit)")
        print("=" * 52)

        choice = custom_input("Select an option: ", allow_cancel=False).strip()

        if choice.lower() == "c" or choice == str(cancel_opt):
            print("[INFO] Exiting API Key Manager.\n")
            return ensure_api_key_configured(config_data)

        if choice == str(add_opt):
            try:
                prompt_add_new_api_key(config_data, allow_cancel=True)
                return ensure_api_key_configured(config_data)
            except TaskCancelled:
                print("[INFO] Adding new key cancelled.")
                continue

        if choice.isdigit():
            chosen_idx = int(choice)
            if 1 <= chosen_idx <= len(key_names):
                target_name = key_names[chosen_idx - 1]
                while True:
                    action = custom_input(
                        f"Key '{target_name}': Set as Default (Y), Delete (d), Cancel (c), or Quit (q)? [Y/d/c/q]: ",
                        allow_cancel=False
                    ).strip().lower()

                    if action in ("", "y", "yes"):
                        config_data["selected_api_key"] = target_name
                        save_config(config_data)
                        print(f"[SUCCESS] '{target_name}' is now set as the default API key.\n")
                        return ensure_api_key_configured(config_data)

                    elif action in ("d", "delete"):
                        del api_keys[target_name]
                        print(f"[INFO] Key '{target_name}' deleted.")
                        if config_data.get("selected_api_key") == target_name:
                            config_data["selected_api_key"] = next(iter(api_keys.keys()), "")
                            if config_data["selected_api_key"]:
                                print(f"[INFO] Default key switched to '{config_data['selected_api_key']}'.")
                        save_config(config_data)

                        # If all keys were deleted and no hardcoded key exists, prompt for a new key immediately
                        if not api_keys and not (GEMINI_API_KEY and GEMINI_API_KEY.strip()):
                            print("\n[INFO] No API keys remaining in config.json. Please add a key:")
                            prompt_add_new_api_key(config_data, allow_cancel=False)
                            return ensure_api_key_configured(config_data)
                        break

                    elif action in ("c", "cancel"):
                        print("[INFO] Action cancelled.")
                        break

                    else:
                        print("[ERROR] Invalid choice. Please enter Y, d, c, or q.")
                continue

        print(f"[ERROR] Invalid selection '{choice}'. Please enter 1-{cancel_opt}, 'c', or 'q'.")


def set_active_job(config_data: dict, job_data: dict | None):
    """Updates or clears the active multi-part job in config.json."""
    config_data["active_job"] = job_data
    save_config(config_data)


def update_recent_language(config_data: dict, lang_code: str):
    """
    Updates the list of up to 3 recent languages in config.json.
    Moves the selected language to the front of the list.
    """
    if not lang_code:
        return
    recent = config_data.get("recent_languages", [])
    recent = [l for l in recent if l.lower() != lang_code.lower()]
    recent.insert(0, lang_code)
    config_data["recent_languages"] = recent[:3]
    save_config(config_data)


# ==========================================
# LANGUAGE SELECTION & NORMALIZATION
# ==========================================

def resolve_language_code(user_input: str) -> str | None:
    """
    Maps user input (abbreviation, country/language code, or name)
    to a valid BCP-47 language code from SUPPORTED_LANGUAGES.
    """
    raw = user_input.strip()
    if not raw:
        return None

    cleaned = raw.replace("_", "-").strip()
    cleaned_lower = cleaned.lower()

    for code in SUPPORTED_LANGUAGES:
        if code.lower() == cleaned_lower:
            return code

    aliases = {
        "fa": "fa-IR",
        "ir": "fa-IR",
        "farsi": "fa-IR",
        "persian": "fa-IR",
        "en": "en-US",
        "us": "en-US",
        "usa": "en-US",
        "uk": "en-GB",
        "gb": "en-GB",
        "ar": "ar-EG",
        "arabic": "ar-EG",
        "de": "de-DE",
        "german": "de-DE",
        "fr": "fr-FR",
        "french": "fr-FR",
        "ru": "ru-RU",
        "russian": "ru-RU",
        "tr": "tr-TR",
        "turkish": "tr-TR",
        "es": "es-US",
        "spanish": "es-US",
        "it": "it-IT",
        "italian": "it-IT",
        "zh": "cmn-Hans-CN",
        "cn": "cmn-Hans-CN",
        "chinese": "cmn-Hans-CN",
        "ja": "ja-JP",
        "jp": "ja-JP",
        "japanese": "ja-JP",
        "ko": "ko-KR",
        "kr": "ko-KR",
        "korean": "ko-KR"
    }

    if cleaned_lower in aliases:
        return aliases[cleaned_lower]

    for code, name in SUPPORTED_LANGUAGES.items():
        if name.lower() == cleaned_lower or name.lower().startswith(cleaned_lower):
            return code

    return None


def prompt_transcription_language(config_data: dict) -> str | None:
    """
    Prompts user for language selection.
    Supports 'c' to cancel back to main menu and 'q' to quit.
    """
    recent = config_data.get("recent_languages", [])[:3]

    print("\nSelect transcription language:")
    print("  [1] Auto-detect / None (Default - press Enter or 1)")

    option_map = {}
    opt_index = 2
    for r_code in recent:
        display_name = SUPPORTED_LANGUAGES.get(r_code, "")
        label = f"{r_code} ({display_name})" if display_name else r_code
        print(f"  [{opt_index}] {label}")
        option_map[str(opt_index)] = r_code
        opt_index += 1

    print("  Or type code/name directly (e.g. FA, IR, fa-IR, EN, US, en-US, AR) [or 'c' to cancel, 'q' to quit]")

    while True:
        choice = custom_input("Your choice: ", allow_cancel=True)

        if choice == "" or choice == "1":
            print("[INFO] Language set to: Auto-detect (Google Smart Detection)")
            return None

        if choice in option_map:
            selected_code = option_map[choice]
            lang_name = SUPPORTED_LANGUAGES.get(selected_code, "")
            print(f"[INFO] Selected: {selected_code} ({lang_name})")
            update_recent_language(config_data, selected_code)
            return selected_code

        resolved = resolve_language_code(choice)
        if resolved:
            lang_name = SUPPORTED_LANGUAGES.get(resolved, "")
            print(f"[INFO] Recognized language: {resolved} ({lang_name})")
            update_recent_language(config_data, resolved)
            return resolved
        else:
            print(f"[ERROR] Unknown language '{choice}'. Please enter 1-{opt_index-1} or a valid code/name (or 'c' to cancel, 'q' to quit).")


def prompt_parts_to_process(total_chunks: int, start_part: int = 1) -> int:
    """
    Prompts the user how many parts to output when a file is divided into multiple chunks.
    Pressing Enter selects all parts; entering a number N selects the first N parts.
    """
    if total_chunks <= 1:
        return total_chunks

    while True:
        if start_part <= 1:
            msg = f"\n[INFO] This file is divided into {total_chunks} parts.\nHow many parts do you want to output? (Press Enter for all {total_chunks}, or enter 1-{total_chunks} [or 'c' to cancel, 'q' to quit]): "
        else:
            msg = f"\n[INFO] Total parts: {total_chunks} (Resuming from part {start_part}).\nUp to which part do you want to output? (Press Enter for all {total_chunks}, or enter {start_part}-{total_chunks} [or 'c' to cancel, 'q' to quit]): "

        user_val = custom_input(msg, allow_cancel=True)
        if user_val == "":
            print(f"[INFO] Selected all {total_chunks} parts.")
            return total_chunks

        if user_val.isdigit():
            num = int(user_val)
            if start_part <= num <= total_chunks:
                print(f"[INFO] Selected {num} part(s) out of {total_chunks}.")
                return num

        print(f"[ERROR] Please press Enter or enter a valid number between {start_part} and {total_chunks} (or 'c' to cancel, 'q' to quit).")


def prompt_failure_action(config_data: dict, can_save_progress: bool = False) -> str:
    """
    Prompts the user when a Gemini API or connection error occurs:
      - Y (or Enter): Retry
      - m: Open API Key Manager to switch/add key, then retry
      - s: Save progress & exit (available when on part 2+ of a multi-part job)
      - c: Cancel current job and return to start of program
      - q: Quit program
    Returns one of: 'retry', 'save_exit', 'cancel', 'quit'
    """
    while True:
        if can_save_progress:
            print("\nOptions: [Y] Retry (Default) | [m] Change API Key | [s] Save progress & Quit | [c] Cancel to Menu | [q] Quit")
            prompt_str = "Choose action (Y/m/s/c/q): "
        else:
            print("\nOptions: [Y] Retry (Default) | [m] Change API Key | [c] Cancel to Menu | [q] Quit")
            prompt_str = "Choose action (Y/m/c/q): "

        val = input(prompt_str).strip().lower()

        if val in ("", "y", "yes"):
            return "retry"
        elif val == "m":
            open_api_key_manager(config_data)
            return "retry"
        elif val == "s":
            if can_save_progress:
                return "save_exit"
            print("[ERROR] 's' (Save progress) is only available for multi-part tasks from Part 2 onwards.")
        elif val == "c":
            return "cancel"
        elif val == "q":
            return "quit"
        else:
            valid_keys = "Y, m, s, c, or q" if can_save_progress else "Y, m, c, or q"
            print(f"[ERROR] Invalid choice '{val}'. Please enter {valid_keys}.")


# ==========================================
# SUBTITLE TRANSLATION ENGINE ('t' command)
# ==========================================

def clean_model_output(text: str) -> str:
    """Strips markdown code fences (e.g. ```json ... ``` or ```srt ... ```) if returned by Gemini."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def parse_srt_blocks(content: str) -> list[dict]:
    """
    Parses an .srt file into structured items so timestamps stay safely in Python:
      [{"seq": 1, "raw_id": "1", "timestamp": "00:00:01,000 --> 00:00:03,000", "text": "Hello"}]
    """
    normalized = content.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    raw_blocks = normalized.split("\n\n")
    parsed_items = []
    seq_idx = 1

    for block in raw_blocks:
        lines = [line.strip("\r") for line in block.strip().splitlines()]
        if len(lines) < 2:
            continue

        if "-->" in lines[0]:
            raw_id = str(seq_idx)
            timestamp_line = lines[0].strip()
            text_lines = lines[1:]
        elif "-->" in lines[1]:
            raw_id = lines[0].strip()
            timestamp_line = lines[1].strip()
            text_lines = lines[2:]
        else:
            continue

        subtitle_text = "\n".join(text_lines).strip()
        parsed_items.append({
            "seq": seq_idx,
            "raw_id": raw_id,
            "timestamp": timestamp_line,
            "text": subtitle_text
        })
        seq_idx += 1

    return parsed_items


def split_srt_items_into_chunks(items: list[dict]) -> list[list[dict]]:
    """
    Splits parsed .srt items into chunks based strictly on the character count of the
    subtitle text itself (ignoring timestamps and indices).
    Soft threshold: (MAX_TRANSLATE_TOKENS_K - 2) * 1000 (e.g. 62,000 text chars)
    Hard threshold: (MAX_TRANSLATE_TOKENS_K - 1) * 1000 (e.g. 63,000 text chars)
    """
    soft_limit = (MAX_TRANSLATE_TOKENS_K - 2) * 1000
    hard_limit = (MAX_TRANSLATE_TOKENS_K - 1) * 1000

    chunks = []
    current_chunk = []
    current_text_len = 0

    for item in items:
        text_len = len(item["text"])

        if current_text_len + text_len > soft_limit and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_text_len = 0

        if text_len > hard_limit:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_text_len = 0
            chunks.append([item])
            continue

        current_chunk.append(item)
        current_text_len += text_len

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def translate_srt_json_chunk(
    chunk_items: list[dict],
    user_prompt: str,
    api_key: str,
    idx: int,
    total_chunks: int
) -> str:
    """
    Translates a chunk of .srt items using JSON input/output so Gemini never touches timestamps.
    Validates that all `index` keys are returned and reconstructs the SRT blocks locally.
    """
    client = genai.Client(api_key=api_key)

    payload = [
        {"index": item["seq"], "text": item["text"]}
        for item in chunk_items
    ]
    json_input_str = json.dumps(payload, ensure_ascii=False)
    text_chars_count = sum(len(item["text"]) for item in chunk_items)

    full_prompt = (
        f"{BASE_SRT_JSON_TRANSLATION_PROMPT}\n"
        f"Translation instructions: {user_prompt}\n\n"
        f"Input JSON:\n{json_input_str}"
    )

    status_msg = (
        f"[{idx}/{total_chunks}] Translating SRT JSON "
        f"({len(chunk_items)} items, {text_chars_count} text chars) with {TRANSLATION_MODEL}"
    )

    response = run_with_timer_and_cancel(
        task_fn=lambda: client.models.generate_content(
            model=TRANSLATION_MODEL,
            contents=[full_prompt],
            config={
                "response_mime_type": "application/json",
                "thinking_config": {
                    "thinking_level": "minimal"
                }
            }
        ),
        status_prefix=status_msg
    )

    raw_text = getattr(response, "text", "") or ""
    cleaned_json_str = clean_model_output(raw_text)

    try:
        translated_list = json.loads(cleaned_json_str)
    except Exception as e:
        raise ValueError(f"Invalid JSON returned by Gemini: {e}")

    if not isinstance(translated_list, list):
        raise ValueError("Gemini output is not a JSON list.")

    translation_map = {}
    for entry in translated_list:
        if isinstance(entry, dict) and "index" in entry and "translation" in entry:
            try:
                translation_map[int(entry["index"])] = str(entry["translation"]).strip()
            except (ValueError, TypeError):
                pass

    missing_indices = [item["seq"] for item in chunk_items if item["seq"] not in translation_map]
    if missing_indices:
        raise ValueError(
            f"Incomplete JSON response: {len(missing_indices)} of {len(chunk_items)} subtitle items were missing."
        )

    reconstructed_blocks = []
    for item in chunk_items:
        translated_text = translation_map[item["seq"]]
        reconstructed_blocks.append(
            f"{item['raw_id']}\n{item['timestamp']}\n{translated_text}"
        )

    return "\n\n".join(reconstructed_blocks)


def split_subtitle_into_chunks(content: str, suffix: str) -> list[str]:
    """
    Legacy chunk splitter kept for .ass and other non-SRT subtitle formats.
    Soft threshold: (MAX_TRANSLATE_TOKENS_K - 2) * 1000 (e.g. 62,000 chars)
    Hard threshold: (MAX_TRANSLATE_TOKENS_K - 1) * 1000 (e.g. 63,000 chars)
    """
    soft_limit = (MAX_TRANSLATE_TOKENS_K - 2) * 1000
    hard_limit = (MAX_TRANSLATE_TOKENS_K - 1) * 1000

    chunks = []
    current_parts = []
    current_len = 0

    normalized_content = content.replace("\r\n", "\n")

    if suffix.lower() == ".ass":
        raw_units = [line + "\n" for line in normalized_content.splitlines()]
    else:
        blocks = normalized_content.split("\n\n")
        raw_units = [b.strip() + "\n\n" for b in blocks if b.strip()]

    for unit in raw_units:
        unit_len = len(unit)

        if current_len + unit_len > soft_limit and current_parts:
            chunks.append("".join(current_parts).strip())
            current_parts = []
            current_len = 0

        if unit_len > hard_limit:
            if current_parts:
                chunks.append("".join(current_parts).strip())
                current_parts = []
                current_len = 0

            idx = 0
            while idx < unit_len:
                slice_part = unit[idx:idx + hard_limit]
                chunks.append(slice_part.strip())
                idx += hard_limit
            continue

        current_parts.append(unit)
        current_len += unit_len

    if current_parts:
        chunks.append("".join(current_parts).strip())

    return chunks


def translate_subtitle_chunk(chunk_text: str, user_prompt: str, api_key: str, idx: int, total_chunks: int) -> str:
    """Translates a single non-SRT (.ass, etc.) subtitle chunk using gemini-3.5-flash-lite."""
    client = genai.Client(api_key=api_key)

    full_prompt = (
        f"{BASE_TRANSLATION_PROMPT} {user_prompt}\n\n"
        f"Here is the subtitle content to translate:\n\n"
        f"{chunk_text}"
    )

    status_msg = f"[{idx}/{total_chunks}] Translating chunk ({len(chunk_text)} chars) with {TRANSLATION_MODEL}"
    response = run_with_timer_and_cancel(
        task_fn=lambda: client.models.generate_content(
            model=TRANSLATION_MODEL,
            contents=[full_prompt],
            config={
                "thinking_config": {
                    "thinking_level": "minimal"
                }
            }
        ),
        status_prefix=status_msg
    )
    raw_text = getattr(response, "text", "") or ""
    return clean_model_output(raw_text)


def handle_translation_command(command_str: str, config_data: dict):
    """
    Handles translation command ('t' or 't <path>'):
      - For .srt files: Uses the JSON-only pipeline (timestamps kept in Python, chunked by pure text chars).
      - For .ass and other files: Keeps the existing full-text chunking logic.
      - Saves to '<stem>_new<suffix>' first, then asks the user (default: Yes)
        whether to replace the original subtitle file with the newly translated file.
    """
    global LAST_GENERATED_SUBTITLE

    parts = command_str.strip().split(maxsplit=1)
    if len(parts) == 1:
        if not LAST_GENERATED_SUBTITLE or not os.path.isfile(LAST_GENERATED_SUBTITLE):
            print("\n[ERROR] No subtitle was generated in this current session.")
            print("Please specify a subtitle path directly (e.g. t subtitle.srt or t subtitle.ass).\n")
            return
        target_sub = pathlib.Path(LAST_GENERATED_SUBTITLE)
        print(f"\n[INFO] Selected last generated subtitle: {target_sub}")
    else:
        raw_path = parts[1].strip().strip("'\"")
        target_sub = pathlib.Path(raw_path)
        if not target_sub.is_file():
            print(f"\n[ERROR] Subtitle file not found: {target_sub}\n")
            return
        print(f"\n[INFO] Selected subtitle file: {target_sub}")

    try:
        prompt_input = custom_input(
            "Enter translation prompt (Press Enter for 'Translate into Persian.') [or 'c' to cancel, 'q' to quit]: ",
            allow_cancel=True
        )
        if not prompt_input.strip():
            prompt_input = "Translate into Persian."
            print("[INFO] Using default prompt: 'Translate into Persian.'")

        content = None
        for enc in ["utf-8", "utf-8-sig", "cp1256", "latin-1"]:
            try:
                with open(target_sub, "r", encoding=enc) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            print(f"[ERROR] Could not decode subtitle file {target_sub}. Unsupported encoding.\n")
            return

        is_srt = (target_sub.suffix.lower() == ".srt")
        output_filename = f"{target_sub.stem}_new{target_sub.suffix}"
        output_path = target_sub.parent / output_filename

        if is_srt:
            srt_items = parse_srt_blocks(content)
            if not srt_items:
                print(f"[ERROR] No valid SRT subtitle blocks found in {target_sub}.\n")
                return

            chunks = split_srt_items_into_chunks(srt_items)
            total_chunks = len(chunks)
            total_text_chars = sum(len(item["text"]) for item in srt_items)
            print(
                f"\n[INFO] SRT parsed: {len(srt_items)} subtitle lines ({total_text_chars} pure text chars, timestamps excluded)."
            )
            print(
                f"[INFO] Divided into {total_chunks} JSON chunk(s) (Soft limit: {(MAX_TRANSLATE_TOKENS_K - 2)}K text chars)."
            )
            delimiter = "\n\n"
        else:
            chunks = split_subtitle_into_chunks(content, target_sub.suffix)
            total_chunks = len(chunks)
            print(
                f"\n[INFO] Subtitle split into {total_chunks} chunk(s) (Soft limit: {(MAX_TRANSLATE_TOKENS_K - 2)}K chars)."
            )
            delimiter = "\n" if target_sub.suffix.lower() == ".ass" else "\n\n"

        target_chunks = prompt_parts_to_process(total_chunks)

        translated_pieces = []
        for idx, chunk in enumerate(chunks[:target_chunks], 1):
            chunk_success = False
            while not chunk_success:
                try:
                    current_api_key = get_active_api_key(config_data)
                    if is_srt:
                        translated_chunk = translate_srt_json_chunk(
                            chunk, prompt_input, current_api_key, idx, target_chunks
                        )
                    else:
                        translated_chunk = translate_subtitle_chunk(
                            chunk, prompt_input, current_api_key, idx, target_chunks
                        )

                    translated_pieces.append(translated_chunk)
                    chunk_success = True

                    # Incrementally save translated chunks to _new file
                    try:
                        with open(output_path, "w", encoding="utf-8") as f:
                            f.write(delimiter.join(translated_pieces) + "\n")
                        print(f"[{idx}/{target_chunks}] -> [SAVED] Progress written to {output_path.name}")
                    except Exception as save_err:
                        print(f"[WARNING] Could not write incremental translation: {save_err}")

                except (TaskCancelled, QuitProgram):
                    raise
                except Exception as e:
                    print(f"\n[API / JSON ERROR] Translation failed for chunk {idx}/{target_chunks}: {e}")
                    can_save = (total_chunks > 1 and idx >= 2)
                    action = prompt_failure_action(config_data, can_save_progress=can_save)
                    if action == "retry":
                        print(f"[INFO] Retrying chunk {idx}...\n")
                    elif action == "save_exit":
                        print(f"[INFO] Translated progress (parts 1 to {idx - 1}) saved at: {output_path}")
                        print("[INFO] Safely exiting program...")
                        sys.exit(0)
                    elif action == "cancel":
                        raise TaskCancelled()
                    elif action == "quit":
                        raise QuitProgram()

        print(f"\n[SUCCESS] Translated subtitle saved to:\n{output_path}\n")

        # Ask user whether to replace the original subtitle file with the _new file (Default: Yes)
        replace_choice = custom_input(
            f"Do you want to replace the original subtitle ({target_sub.name}) with the translated file? (Y/n): ",
            allow_cancel=True
        ).lower()

        if replace_choice in ("", "y", "yes"):
            try:
                os.replace(output_path, target_sub)
                LAST_GENERATED_SUBTITLE = str(target_sub.resolve())
                print(f"[SUCCESS] Original subtitle replaced successfully: {target_sub}\n")
            except Exception as e:
                print(f"[ERROR] Could not replace original subtitle file: {e}\n")
        else:
            LAST_GENERATED_SUBTITLE = str(output_path.resolve())
            print(f"[INFO] Kept both files. Translated file is at: {output_path}\n")

    except TaskCancelled:
        print("[INFO] Translation cancelled. Returning to main menu...\n")
        return
    except QuitProgram:
        print("[INFO] Exiting program...")
        sys.exit(0)


# ==========================================
# HELPER DATA STRUCTURES & FUNCTIONS
# ==========================================

class NormalizedWord:
    """Wrapper to hold word annotations with absolute timestamps compatible with words_to_srt."""
    def __init__(self, text: str, start_sec: float, end_sec: float):
        self.text = text
        self.start_offset = f"{start_sec:.3f}s"
        self.end_offset = f"{end_sec:.3f}s"
        self.type = "word_info"
        self.start_sec = float(start_sec)
        self.end_sec = float(end_sec)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "start_sec": round(self.start_sec, 3),
            "end_sec": round(self.end_sec, 3)
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            text=data.get("text", ""),
            start_sec=float(data.get("start_sec", 0.0)),
            end_sec=float(data.get("end_sec", 0.0))
        )


def setup_proxy():
    """Configures system environment variables for SOCKS5 proxy routing."""
    if USE_PROXY and PROXY_IP and PROXY_PORT:
        proxy_url = f"{PROXY_TYPE}://{PROXY_IP}:{PROXY_PORT}"
        os.environ["HTTP_PROXY"] = proxy_url
        os.environ["HTTPS_PROXY"] = proxy_url
        os.environ["ALL_PROXY"] = proxy_url
        os.environ["http_proxy"] = proxy_url
        os.environ["https_proxy"] = proxy_url
        os.environ["all_proxy"] = proxy_url
        print(f"[INFO] Proxy enabled: {proxy_url}")


def custom_input(prompt_text: str, allow_cancel: bool = False) -> str:
    """
    Custom input function that listens for 'q' to safely quit,
    and optionally 'c' (when allow_cancel=True) to cancel and return to the main menu.
    """
    val = input(prompt_text).strip()
    if val.lower() == "q":
        print("\n[INFO] 'q' entered. Safely exiting program...")
        sys.exit(0)
    if allow_cancel and val.lower() == "c":
        raise TaskCancelled()
    return val


def get_media_duration(file_path) -> float:
    """Returns the duration of the media file in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            val = result.stdout.strip()
            if val:
                return float(val)
    except Exception as e:
        print(f"[WARNING] Could not get media duration with ffprobe: {e}")
    return 0.0


def remove_temp_file(file_path):
    """Removes the temporary audio file if it exists."""
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"[INFO] Temporary audio file deleted: {file_path}")
        except Exception as e:
            print(f"[WARNING] Could not delete temporary file: {e}")


def convert_video_to_ogg(video_path, temp_audio_path, start_sec=None, duration_sec=None):
    """
    Converts input video (or a time segment) into a mono-channel compressed OGG audio file using FFmpeg.
    Supports live 'c' key cancellation (stops FFmpeg, deletes temp audio file, returns to main menu)
    and live 'q' key cancellation (stops FFmpeg, deletes temp audio file, exits program).
    """
    cmd = ["ffmpeg", "-y", "-nostats", "-loglevel", "error"]
    if start_sec is not None and start_sec > 0:
        cmd.extend(["-ss", f"{start_sec:.3f}"])
    if duration_sec is not None and duration_sec > 0:
        cmd.extend(["-t", f"{duration_sec:.3f}"])

    cmd.extend([
        "-i", str(video_path),
        "-vn",
        "-ac", "1",
        "-c:a", "libvorbis",
        "-q:a", "0",
        str(temp_audio_path)
    ])

    segment_info = ""
    if start_sec is not None and duration_sec is not None:
        segment_info = f" ({start_sec:.1f}s -> {start_sec + duration_sec:.1f}s)"

    status_prefix = f"[INFO] Extracting audio with FFmpeg{segment_info}"
    start_time = time.time()

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:
        print(f"[ERROR] FFmpeg execution error: {e}")
        return False

    with NonBlockingKeyMonitor() as monitor:
        while proc.poll() is None:
            elapsed_str = format_elapsed_mm_ss(time.time() - start_time)
            sys.stdout.write(f"\r{status_prefix} | Elapsed: {elapsed_str} (Press 'c' to cancel, 'q' to quit)   ")
            sys.stdout.flush()

            action = monitor.check_action_key()
            if action in ("c", "q"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                print(f"[INFO] '{action}' pressed! Stopping FFmpeg and deleting temporary audio file...")
                try:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                except Exception:
                    pass
                time.sleep(0.1)
                remove_temp_file(temp_audio_path)
                if action == "c":
                    raise TaskCancelled()
                else:
                    raise QuitProgram()

            time.sleep(0.1)

    total_elapsed_str = format_elapsed_mm_ss(time.time() - start_time)
    sys.stdout.write(f"\r{status_prefix} | Completed in {total_elapsed_str}.                                    \n")
    sys.stdout.flush()

    _, stderr_output = proc.communicate()
    if proc.returncode != 0:
        print(f"[ERROR] FFmpeg conversion failed: {stderr_output}")
        remove_temp_file(temp_audio_path)
        return False

    print(f"[SUCCESS] Temporary audio created: {temp_audio_path}")
    return True


def parse_offset(offset_val) -> float:
    """Parses offset string (e.g. '0.100s') into float seconds."""
    if not offset_val:
        return 0.0
    if isinstance(offset_val, (int, float)):
        return float(offset_val)
    val_str = str(offset_val).rstrip("s").strip()
    try:
        return float(val_str)
    except ValueError:
        return 0.0


def format_srt_timestamp(seconds: float) -> str:
    """Formats seconds into SRT timestamp HH:MM:SS,mmm."""
    millis = int(round((seconds % 1) * 1000))
    total_seconds = int(seconds)
    if millis == 1000:
        millis = 0
        total_seconds += 1
    secs = total_seconds % 60
    mins = (total_seconds // 60) % 60
    hours = total_seconds // 3600
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def extract_word_annotations(response):
    """Extracts word_info annotations from Gemini interactions response."""
    words = []
    for step in getattr(response, "steps", []) or []:
        for content in getattr(step, "content", []) or []:
            for annotation in getattr(content, "annotations", []) or []:
                if getattr(annotation, "type", None) == "word_info":
                    words.append(annotation)
    return words


def format_chunk_to_lines(chunk_words) -> str:
    """Formats chunk words into 1 or 2 lines using global configuration settings."""
    words_text = [w[0] for w in chunk_words]
    total_words = len(words_text)
    full_str = " ".join(words_text)

    if not ALLOW_TWO_LINES or (total_words <= MAX_WORDS_PER_LINE and len(full_str) <= MAX_CHARS_PER_LINE):
        return full_str

    mid = total_words // 2
    if mid > MAX_WORDS_PER_LINE:
        mid = MAX_WORDS_PER_LINE
    elif (total_words - mid) > MAX_WORDS_PER_LINE:
        mid = total_words - MAX_WORDS_PER_LINE

    line1 = " ".join(words_text[:mid])
    line2 = " ".join(words_text[mid:])
    return f"{line1}\n{line2}"


def normalize_word_list(words, offset_sec: float = 0.0) -> list[NormalizedWord]:
    """Converts raw or normalized word objects into a uniform list of NormalizedWord objects."""
    normalized = []
    for w in words:
        if isinstance(w, NormalizedWord) and offset_sec == 0.0:
            normalized.append(w)
        else:
            w_text = getattr(w, "text", "") or ""
            start_s = getattr(w, "start_sec", None)
            if start_s is None:
                start_s = parse_offset(getattr(w, "start_offset", None))
            end_s = getattr(w, "end_sec", None)
            if end_s is None:
                end_s = parse_offset(getattr(w, "end_offset", None))
            normalized.append(NormalizedWord(w_text, start_s + offset_sec, end_s + offset_sec))
    return normalized


def group_words_into_frames(words: list[NormalizedWord]) -> list[list[NormalizedWord]]:
    """
    Groups NormalizedWord objects into subtitle frames using the exact timing, pause,
    word-count, and punctuation boundaries configured for the script.
    """
    if not words:
        return []

    frames = []
    current_frame = []
    max_words_per_frame = (MAX_WORDS_PER_LINE * 2) if ALLOW_TWO_LINES else MAX_WORDS_PER_LINE

    for w in words:
        if not current_frame:
            current_frame.append(w)
            continue

        prev_end = current_frame[-1].end_sec
        chunk_start = current_frame[0].start_sec
        time_gap = w.start_sec - prev_end
        current_duration = w.end_sec - chunk_start

        reached_max_words = len(current_frame) >= max_words_per_frame
        long_pause = time_gap > MAX_GAP
        exceeded_duration = current_duration > MAX_DURATION
        sentence_ended = current_frame[-1].text.endswith((".", "؟", "?", "!"))

        if reached_max_words or long_pause or exceeded_duration or sentence_ended:
            frames.append(current_frame)
            current_frame = [w]
        else:
            current_frame.append(w)

    if current_frame:
        frames.append(current_frame)

    return frames


def format_frames_to_srt(frames: list[list[NormalizedWord]], start_index: int = 1) -> tuple[str, int]:
    """
    Formats a list of word frames into an SRT string starting at `start_index`.
    Returns (srt_text, next_srt_index).
    """
    if not frames:
        return "", start_index

    srt_blocks = []
    chunk_index = start_index

    for frame in frames:
        tuple_words = [(w.text, w.start_sec, w.end_sec) for w in frame]
        chunk_text = format_chunk_to_lines(tuple_words)
        c_start = frame[0].start_sec
        c_end = frame[-1].end_sec

        if (c_end - c_start) < MIN_DURATION:
            c_end = c_start + MIN_DURATION

        srt_blocks.append(
            f"{chunk_index}\n"
            f"{format_srt_timestamp(c_start)} --> {format_srt_timestamp(c_end)}\n"
            f"{chunk_text}\n"
        )
        chunk_index += 1

    return "\n".join(srt_blocks), chunk_index


def words_to_srt(words, fallback_text="") -> str:
    """Converts word annotations to SRT format."""
    norm_words = normalize_word_list(words)
    if not norm_words:
        if fallback_text:
            return f"1\n00:00:00,000 --> 00:00:10,000\n{fallback_text}\n"
        return ""

    frames = group_words_into_frames(norm_words)
    srt_text, _ = format_frames_to_srt(frames, start_index=1)
    return srt_text


def split_confirmed_and_pending_words(
    accumulated_words: list[NormalizedWord],
    next_overlap_start: float
) -> tuple[list[list[NormalizedWord]], list[NormalizedWord]]:
    """
    Separates words that are 100% confirmed (strictly before `next_overlap_start` and in
    already-closed subtitle frames) from pending words (the last open frame before
    `next_overlap_start` + all words inside the overlap zone `[next_overlap_start, c_end]`).
    This guarantees that saving confirmed frames early never alters overlap merging.
    """
    safe_words = [w for w in accumulated_words if w.end_sec <= next_overlap_start]
    overlap_words = [w for w in accumulated_words if w.end_sec > next_overlap_start]

    frames = group_words_into_frames(safe_words)
    if len(frames) > 1:
        confirmed_frames = frames[:-1]
        pending_words = frames[-1] + overlap_words
    else:
        confirmed_frames = []
        pending_words = safe_words + overlap_words

    return confirmed_frames, pending_words


def append_srt_blocks_to_file(srt_path: pathlib.Path, new_srt_text: str, is_first_write: bool = False):
    """Writes or appends confirmed SRT blocks to the target .srt file on disk."""
    if is_first_write or not srt_path.exists():
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(new_srt_text)
        return

    if not new_srt_text.strip():
        return

    existing_size = srt_path.stat().st_size
    with open(srt_path, "a", encoding="utf-8") as f:
        if existing_size > 0:
            f.write("\n")
        f.write(new_srt_text)


def transcribe_single_audio_file(audio_path, api_key, model_name, language_code=None):
    """
    Uploads audio file and retrieves raw (words, output_text) from Gemini API.
    Displays an in-place elapsed timer (MMm SSs) during both upload and transcription,
    and listens for 'c' (cancel to menu) and 'q' (quit).
    Note: Does NOT delete the local `audio_path` if an API error occurs, allowing retries
    without re-running FFmpeg.
    """
    client = genai.Client(api_key=api_key)

    audio_file = run_with_timer_and_cancel(
        task_fn=lambda: client.files.upload(file=str(audio_path)),
        status_prefix="[INFO] Uploading audio file to Gemini API",
        on_cancel=lambda: remove_temp_file(audio_path)
    )

    language_codes = [language_code] if language_code else []

    generation_config = {
        "transcription_config": {
            "language_codes": language_codes,
            "mode": {
                "type": "verbatim",
                "timestamp_granularities": ["word"],
            }
        }
    }

    audio_input = {
        "type": "audio",
        "uri": audio_file.uri,
        "mime_type": audio_file.mime_type or "audio/ogg"
    }

    lang_display = language_code if language_code else "Auto-detect"

    def cleanup_on_cancel():
        remove_temp_file(audio_path)
        try:
            client.files.delete(name=audio_file.name)
        except Exception:
            pass

    try:
        response = run_with_timer_and_cancel(
            task_fn=lambda: client.interactions.create(
                model=model_name,
                input=[audio_input],
                generation_config=generation_config
            ),
            status_prefix=f"[INFO] Waiting for '{model_name}' response (Lang: {lang_display})",
            on_cancel=cleanup_on_cancel
        )
    finally:
        # Delete the remote file on Gemini servers, but keep local audio_path until full success
        try:
            client.files.delete(name=audio_file.name)
        except Exception:
            pass

    words = extract_word_annotations(response)
    output_text = getattr(response, "output_text", "") or ""
    return words, output_text


def transcribe_with_gemini_interactions(audio_path, api_key, model_name, language_code=None):
    """Single-file transcription entry point for backward compatibility."""
    words, output_text = transcribe_single_audio_file(audio_path, api_key, model_name, language_code)
    return words_to_srt(words, fallback_text=output_text)


# ==========================================
# CHUNKING & SEAMLESS MERGING
# ==========================================

def calculate_video_chunks(total_duration: float, split_minutes: int, overlap_sec: float):
    """Calculates time boundaries for consecutive video chunks."""
    cut_step = max(1.0, float(split_minutes - 1)) * 60.0
    chunks = []
    current_cut = 0.0

    while current_cut < total_duration:
        if not chunks:
            start_time = 0.0
            end_time = min(total_duration, cut_step)
            overlap_start = 0.0
        else:
            start_time = max(0.0, current_cut - overlap_sec)
            end_time = min(total_duration, current_cut + cut_step)
            overlap_start = start_time

        chunks.append({
            "index": len(chunks) + 1,
            "start": start_time,
            "end": end_time,
            "duration": end_time - start_time,
            "overlap_start": overlap_start,
            "overlap_end": current_cut
        })

        current_cut = end_time
        if current_cut >= total_duration:
            break

    return chunks


def merge_word_annotations(prev_words, new_words, overlap_start: float, overlap_end: float):
    """Merges words from previous chunk and new chunk seamlessly within the overlap window."""
    if not prev_words:
        return new_words
    if not new_words:
        return prev_words

    prefix_words = [w for w in prev_words if w.end_sec <= overlap_start]
    prev_overlap = [w for w in prev_words if w.end_sec > overlap_start]
    new_overlap = [w for w in new_words if w.start_sec < overlap_end]
    suffix_words = [w for w in new_words if w.start_sec >= overlap_end]

    def clean_word(txt):
        return txt.strip().lower().strip(".,?!:;،؟«»\"'")

    tokens_prev = [clean_word(w.text) for w in prev_overlap]
    tokens_new = [clean_word(w.text) for w in new_overlap]

    matched = False
    if tokens_prev and tokens_new:
        matcher = difflib.SequenceMatcher(None, tokens_prev, tokens_new)
        match = matcher.find_longest_match(0, len(tokens_prev), 0, len(tokens_new))

        if match.size >= 1:
            matched = True
            overlap_merged = prev_overlap[:match.a] + new_overlap[match.b:]

    if not matched:
        mid_time = (overlap_start + overlap_end) / 2.0
        overlap_merged = [w for w in prev_overlap if w.end_sec <= mid_time] + \
                         [w for w in new_overlap if w.start_sec > mid_time]

    merged = prefix_words + overlap_merged + suffix_words
    merged.sort(key=lambda w: w.start_sec)
    return merged


def handle_partial_subtitle_on_abort(
    srt_path: pathlib.Path,
    completed_idx: int,
    accumulated_words: list[NormalizedWord],
    next_srt_index: int,
    config_data: dict
):
    """
    When a multi-part video job is cancelled ('c') or quit ('q'):
      - If at least 1 part was completed (completed_idx >= 1), asks the user whether
        the subtitle generated so far should be kept or deleted.
      - If kept, flushes any remaining pending words from the completed part into `srt_path`.
      - If deleted (or if 0 parts were completed), removes the empty/partial `srt_path`.
      - Clears `active_job` from `config.json`.
    """
    global LAST_GENERATED_SUBTITLE
    set_active_job(config_data, None)

    if completed_idx < 1:
        if srt_path.exists() and srt_path.stat().st_size == 0:
            try:
                srt_path.unlink()
            except Exception:
                pass
        return

    print(f"\n[PARTIAL SUBTITLE] {completed_idx} part(s) of this video were already completed.")
    while True:
        choice = input(
            f"Do you want to KEEP or DELETE the subtitle generated so far ({srt_path.name})? (K=keep [Default] / d=delete): "
        ).strip().lower()

        if choice in ("", "k", "keep", "y", "yes"):
            # Flush remaining boundary/overlap words from the last completed part so nothing is cut off
            if accumulated_words:
                rem_frames = group_words_into_frames(accumulated_words)
                rem_srt, _ = format_frames_to_srt(rem_frames, start_index=next_srt_index)
                append_srt_blocks_to_file(
                    srt_path, rem_srt, is_first_write=(next_srt_index == 1)
                )
            LAST_GENERATED_SUBTITLE = str(srt_path.resolve())
            print(f"[INFO] Partial subtitle kept at: {srt_path}")
            break
        elif choice in ("d", "delete", "n", "no"):
            if srt_path.exists():
                try:
                    srt_path.unlink()
                    print(f"[INFO] Partial subtitle deleted: {srt_path}")
                except Exception as e:
                    print(f"[WARNING] Could not delete {srt_path}: {e}")
            break
        else:
            print("[ERROR] Please enter 'k' (or press Enter) to keep, or 'd' to delete.")


def extract_and_transcribe_with_retry(
    video_path: pathlib.Path,
    temp_audio_path: pathlib.Path,
    config_data: dict,
    language_code: str | None,
    start_sec: float | None = None,
    duration_sec: float | None = None,
    is_multipart: bool = False,
    part_index: int = 1
):
    """
    1. Extracts audio to `temp_audio_path` using FFmpeg (only if not already created).
    2. Uploads & transcribes with Gemini using the currently selected API key.
    3. Keeps `temp_audio_path` intact if Gemini/network fails so retries do not re-run FFmpeg.
    4. On Gemini failure, offers:
         - Y: Retry
         - m: Change API key in manager & retry
         - s: Save progress & exit (if multi-part and part_index >= 2)
         - c: Cancel current job and return to main menu
         - q: Quit program
    """
    # Step 1: Extract audio with FFmpeg (if not already present)
    while not (temp_audio_path.exists() and temp_audio_path.stat().st_size > 0):
        if convert_video_to_ogg(video_path, temp_audio_path, start_sec=start_sec, duration_sec=duration_sec):
            break
        print("\n[ERROR] FFmpeg audio extraction failed.")
        can_save = (is_multipart and part_index >= 2)
        action = prompt_failure_action(config_data, can_save_progress=can_save)
        if action == "retry":
            print("[INFO] Retrying FFmpeg audio extraction...\n")
        elif action == "save_exit":
            remove_temp_file(temp_audio_path)
            print(f"[INFO] Progress up to part {part_index - 1} is saved in config.json. Safely exiting...")
            sys.exit(0)
        elif action == "cancel":
            remove_temp_file(temp_audio_path)
            raise TaskCancelled()
        elif action == "quit":
            remove_temp_file(temp_audio_path)
            raise QuitProgram()

    # Step 2: Upload & Transcribe with Gemini (reusing temp_audio_path on retry)
    while True:
        try:
            active_api_key = get_active_api_key(config_data)
            words, fallback_text = transcribe_single_audio_file(
                temp_audio_path, active_api_key, GEMINI_MODEL, language_code
            )
            # Full response received from Gemini -> now safe to delete temp audio file
            remove_temp_file(temp_audio_path)
            return words, fallback_text
        except (TaskCancelled, QuitProgram):
            remove_temp_file(temp_audio_path)
            raise
        except Exception as err:
            print(f"\n[HTTP / API ERROR] Transcription failed: {err}")
            print(f"[INFO] Temporary audio file kept for fast retry: {temp_audio_path.name}")
            can_save = (is_multipart and part_index >= 2)
            action = prompt_failure_action(config_data, can_save_progress=can_save)
            if action == "retry":
                print("[INFO] Retrying Gemini transcription using existing audio file...\n")
            elif action == "save_exit":
                remove_temp_file(temp_audio_path)
                print(f"[INFO] Progress up to part {part_index - 1} is saved in config.json. Safely exiting...")
                sys.exit(0)
            elif action == "cancel":
                remove_temp_file(temp_audio_path)
                raise TaskCancelled()
            elif action == "quit":
                remove_temp_file(temp_audio_path)
                raise QuitProgram()


def run_video_transcription_job(
    video_path: pathlib.Path,
    srt_path: pathlib.Path,
    config_data: dict,
    language_code: str | None = None,
    resume_state: dict | None = None
):
    """
    Executes single-part or multi-part video transcription.
    Handles 'c' (return to main menu) and 'q' (quit program) cleanly, including
    asking whether to keep or delete partial subtitles when at least 1 part is completed.
    """
    global LAST_GENERATED_SUBTITLE

    total_duration = get_media_duration(video_path)
    total_mins = total_duration / 60.0
    print(f"[INFO] Video duration: {total_mins:.2f} minutes ({total_duration:.1f} seconds)")

    split_mins = SPLIT_DURATION_MINUTES
    if resume_state and resume_state.get("split_duration_minutes"):
        split_mins = resume_state["split_duration_minutes"]

    should_split = (
        split_mins is not None and
        isinstance(split_mins, int) and
        total_duration > (split_mins * 60.0)
    )

    # Single-part video
    if not should_split:
        temp_audio_path = video_path.parent / f"temp_{video_path.stem}.ogg"
        try:
            words, fallback_text = extract_and_transcribe_with_retry(
                video_path=video_path,
                temp_audio_path=temp_audio_path,
                config_data=config_data,
                language_code=language_code,
                is_multipart=False,
                part_index=1
            )
            srt_content = words_to_srt(words, fallback_text=fallback_text)
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            LAST_GENERATED_SUBTITLE = str(srt_path.resolve())
            print(f"[SUCCESS] Subtitle generated successfully: {srt_path}\n")
        except TaskCancelled:
            remove_temp_file(temp_audio_path)
            print("[INFO] Transcription cancelled. Returning to main menu...\n")
        except QuitProgram:
            remove_temp_file(temp_audio_path)
            print("[INFO] Exiting program...")
            sys.exit(0)
        except Exception as e:
            print(f"[ERROR] Failed to save SRT file: {e}\n")
        return

    # Multi-part video
    chunks = calculate_video_chunks(total_duration, split_mins, CHUNK_OVERLAP_SECONDS)
    total_chunks = len(chunks)

    completed_idx = 0
    next_srt_index = 1
    accumulated_words = []
    fallback_texts = []

    try:
        if resume_state:
            completed_idx = int(resume_state.get("completed_chunk_index", 0))
            next_srt_index = int(resume_state.get("next_srt_index", 1))
            accumulated_words = [
                NormalizedWord.from_dict(w) for w in resume_state.get("pending_words", [])
            ]
            fallback_texts = list(resume_state.get("fallback_texts", []))
            target_chunks = int(resume_state.get("target_chunks", total_chunks))
            start_chunk_idx = completed_idx + 1
            print(f"\n[RESUME] Resuming from part [{start_chunk_idx}/{target_chunks}] (Total video parts: {total_chunks})...")
        else:
            print(f"\n[INFO] Video exceeds {split_mins} minutes. Divided into {total_chunks} overlapping parts.")
            target_chunks = prompt_parts_to_process(total_chunks, start_part=1)
            start_chunk_idx = 1

            # Initialize empty SRT file for incremental confirmed writes
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write("")

            # Record active multi-part job in config.json
            set_active_job(config_data, {
                "video_path": str(video_path.resolve()),
                "srt_path": str(srt_path.resolve()),
                "language_code": language_code,
                "total_chunks": total_chunks,
                "target_chunks": target_chunks,
                "split_duration_minutes": split_mins,
                "completed_chunk_index": 0,
                "next_srt_index": 1,
                "pending_words": [],
                "fallback_texts": []
            })

        for chunk in chunks[start_chunk_idx - 1: target_chunks]:
            c_idx = chunk["index"]
            c_start = chunk["start"]
            c_end = chunk["end"]
            c_dur = chunk["duration"]
            overlap_start = chunk["overlap_start"]
            overlap_end = chunk["overlap_end"]

            print(f"\n{'='*60}")
            print(f"  Processing Part [{c_idx}/{target_chunks}] (of {total_chunks}): {c_start/60.0:.2f}m -> {c_end/60.0:.2f}m ({c_dur:.1f}s)")
            print(f"{'='*60}")

            temp_audio_path = video_path.parent / f"temp_{video_path.stem}_part{c_idx}.ogg"

            raw_words, fallback_text = extract_and_transcribe_with_retry(
                video_path=video_path,
                temp_audio_path=temp_audio_path,
                config_data=config_data,
                language_code=language_code,
                start_sec=c_start,
                duration_sec=c_dur,
                is_multipart=True,
                part_index=c_idx
            )

            if fallback_text:
                fallback_texts.append(fallback_text)

            chunk_words = normalize_word_list(raw_words, offset_sec=c_start)

            if c_idx == 1 and not accumulated_words:
                accumulated_words = chunk_words
            else:
                accumulated_words = merge_word_annotations(
                    accumulated_words,
                    chunk_words,
                    overlap_start=overlap_start,
                    overlap_end=overlap_end
                )

            # Step-by-step confirmation & incremental SRT writing
            if c_idx < target_chunks:
                next_overlap_start = chunks[c_idx]["overlap_start"]
                confirmed_frames, pending_words = split_confirmed_and_pending_words(
                    accumulated_words, next_overlap_start
                )
                confirmed_srt, next_srt_index = format_frames_to_srt(
                    confirmed_frames, start_index=next_srt_index
                )
                append_srt_blocks_to_file(
                    srt_path, confirmed_srt, is_first_write=(c_idx == 1 and next_srt_index == len(confirmed_frames) + 1)
                )
                accumulated_words = pending_words
                completed_idx = c_idx

                # Save progress in config.json for crash/close recovery
                set_active_job(config_data, {
                    "video_path": str(video_path.resolve()),
                    "srt_path": str(srt_path.resolve()),
                    "language_code": language_code,
                    "total_chunks": total_chunks,
                    "target_chunks": target_chunks,
                    "split_duration_minutes": split_mins,
                    "completed_chunk_index": completed_idx,
                    "next_srt_index": next_srt_index,
                    "pending_words": [w.to_dict() for w in pending_words],
                    "fallback_texts": fallback_texts
                })

                print(
                    f"[SUCCESS] Part [{c_idx}/{target_chunks}] confirmed subtitles saved to '{srt_path.name}' "
                    f"({len(confirmed_frames)} frames confirmed, {len(pending_words)} boundary/overlap words held for next merge)."
                )
            else:
                # Final requested chunk: flush all remaining words into the SRT file
                final_frames = group_words_into_frames(accumulated_words)
                final_srt, next_srt_index = format_frames_to_srt(
                    final_frames, start_index=next_srt_index
                )
                if not final_srt and next_srt_index == 1 and fallback_texts:
                    final_srt = f"1\n00:00:00,000 --> 00:00:10,000\n" + "\n".join(fallback_texts) + "\n"

                append_srt_blocks_to_file(
                    srt_path, final_srt, is_first_write=(c_idx == 1 and next_srt_index == len(final_frames) + 1)
                )
                completed_idx = c_idx
                accumulated_words = []

                # Job completed -> clear active_job from config.json
                set_active_job(config_data, None)
                LAST_GENERATED_SUBTITLE = str(srt_path.resolve())
                print(f"[SUCCESS] Final part [{c_idx}/{target_chunks}] merged and saved to: {srt_path}\n")

    except TaskCancelled:
        handle_partial_subtitle_on_abort(
            srt_path=srt_path,
            completed_idx=completed_idx,
            accumulated_words=accumulated_words,
            next_srt_index=next_srt_index,
            config_data=config_data
        )
        print("[INFO] Multi-part transcription cancelled. Returning to main menu...\n")
    except QuitProgram:
        handle_partial_subtitle_on_abort(
            srt_path=srt_path,
            completed_idx=completed_idx,
            accumulated_words=accumulated_words,
            next_srt_index=next_srt_index,
            config_data=config_data
        )
        print("[INFO] Safely exiting program...")
        sys.exit(0)


def check_and_offer_startup_resume(config_data: dict):
    """
    Checks config.json on startup to see if a multi-part job was left unfinished
    when the program was previously closed, and asks the user if they want to continue.
    """
    active_job = config_data.get("active_job")
    if not isinstance(active_job, dict):
        return

    video_path_str = active_job.get("video_path", "")
    srt_path_str = active_job.get("srt_path", "")
    if not video_path_str or not os.path.isfile(video_path_str):
        set_active_job(config_data, None)
        return

    video_path = pathlib.Path(video_path_str)
    srt_path = pathlib.Path(srt_path_str) if srt_path_str else video_path.with_suffix(".srt")
    completed_idx = int(active_job.get("completed_chunk_index", 0))
    target_chunks = int(active_job.get("target_chunks", 1))
    total_chunks = int(active_job.get("total_chunks", target_chunks))
    lang_code = active_job.get("language_code")

    if completed_idx >= target_chunks:
        set_active_job(config_data, None)
        return

    print("\n" + "=" * 60)
    print("  [RECOVERY] Unfinished Multi-Part Transcription Detected!")
    print("=" * 60)
    print(f"  Video File : {video_path}")
    print(f"  Subtitle   : {srt_path}")
    print(f"  Progress   : {completed_idx} of {target_chunks} part(s) completed (Total video parts: {total_chunks})")
    print(f"  Language   : {lang_code if lang_code else 'Auto-detect'}")
    print("=" * 60)

    choice = custom_input("Do you want to continue this unfinished job now? (Y/n): ").lower()
    if choice in ("", "y", "yes"):
        run_video_transcription_job(
            video_path=video_path,
            srt_path=srt_path,
            config_data=config_data,
            language_code=lang_code,
            resume_state=active_job
        )
        print("-" * 50 + "\n")
    else:
        clear_choice = custom_input("Do you want to keep this recovery state for later when you open the file? (Y/n): ").lower()
        if clear_choice == "n":
            set_active_job(config_data, None)
            print("[INFO] Recovery state cleared from config.json.\n")
        else:
            print("[INFO] Recovery state kept in config.json.\n")


# ==========================================
# MAIN EXECUTION LOOP
# ==========================================

def main():
    setup_proxy()
    ensure_ffmpeg_installed()
    config_data = load_or_create_config()

    # Ensure at least one API key is available right on startup (prompts for key + name if missing)
    ensure_api_key_configured(config_data)

    print("==================================================")
    print("  Gemini 3.5 Transcribe Video to SRT Generator")
    print("==================================================")
    print("Commands & Shortcuts:")
    print("  • Enter video file path : Generate SRT subtitle from video")
    print("  • 't' or 't <path>'     : Translate last or specified subtitle (.srt, .ass)")
    print("  • 'm'                   : Open Gemini API Key Manager")
    print("  • 'c'                   : Cancel active task and return to main menu")
    print("  • 'q'                   : Quit the program at any time\n")

    # Check config.json immediately on startup for any interrupted multi-part job
    check_and_offer_startup_resume(config_data)

    while True:
        video_input = custom_input("Enter video file path ('t' = translate, 'm' = API keys, 'q' = quit): ")

        if not video_input:
            continue

        # Check for API Key Manager command 'm'
        if video_input.lower() == "m":
            open_api_key_manager(config_data)
            continue

        # Check for translation command 't' or 't <path>'
        if video_input.lower() == "t" or video_input.lower().startswith("t "):
            handle_translation_command(video_input, config_data)
            print("-" * 50 + "\n")
            continue

        # Strip surrounding quotes from drag-and-drop file paths
        video_path = pathlib.Path(video_input.strip("'\""))

        if not video_path.is_file():
            print(f"[ERROR] File not found: {video_path}\n")
            continue

        srt_path = video_path.with_suffix(".srt")

        # Check if the opened file matches an unfinished multi-part job in config.json
        active_job = config_data.get("active_job")
        if (
            isinstance(active_job, dict)
            and active_job.get("video_path") == str(video_path.resolve())
            and int(active_job.get("completed_chunk_index", 0)) < int(active_job.get("target_chunks", 1))
        ):
            comp_idx = int(active_job.get("completed_chunk_index", 0))
            targ_chunks = int(active_job.get("target_chunks", 1))
            print(f"\n[RECOVERY] This file has an unfinished session ({comp_idx}/{targ_chunks} parts completed).")
            res_choice = custom_input(f"Do you want to continue from part {comp_idx + 1}? (Y/n to start over): ").lower()
            if res_choice in ("", "y", "yes"):
                run_video_transcription_job(
                    video_path=video_path,
                    srt_path=srt_path,
                    config_data=config_data,
                    language_code=active_job.get("language_code"),
                    resume_state=active_job
                )
                print("-" * 50 + "\n")
                continue
            else:
                set_active_job(config_data, None)

        # Interactive Language Selection for new transcription
        try:
            selected_lang = prompt_transcription_language(config_data)
        except TaskCancelled:
            print("[INFO] Cancelled. Returning to main menu...\n")
            continue

        run_video_transcription_job(
            video_path=video_path,
            srt_path=srt_path,
            config_data=config_data,
            language_code=selected_lang,
            resume_state=None
        )

        print("-" * 50 + "\n")


if __name__ == "__main__":
    main()