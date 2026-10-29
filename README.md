# Media2SRT-CLI

**Media2SRT-CLI** is a cross-platform command-line tool that automatically generates accurate, word-level synchronized `.srt` subtitles from video or audio files and translates existing subtitles using Google's Gemini AI (`gemini-3.5-transcribe` & `gemini-3.5-flash-lite`).

Repository: <https://github.com/Matin6725/Media2SRT-CLI>

## ✨ Key Features

* **Word-Level Timestamp Synchronization**: Uses `gemini-3.5-transcribe` in verbatim word-granularity mode to build cleanly timed 1-line or 2-line `.srt` frames based on natural pauses, punctuation, and reading speed limits.

* **Smart Long-Video Chunking & Seamless Overlap Merging**: Automatically splits long videos (e.g., >30 minutes) into overlapping audio segments and uses sequence alignment (`difflib`) to merge chunk boundaries without losing or duplicating words.

* **Crash & Interrupt Recovery**: Saves incremental progress after every completed part in `config.json`. If the program closes or the network drops, you can resume right from the unfinished part on the next launch.

* **Timestamp-Safe Subtitle Translation**: Translates `.srt` and `.ass` files using `gemini-3.5-flash-lite`. For `.srt` files, timestamps stay safely inside Python while only the dialogue text is sent to the model as structured JSON.

* **Built-in Multi-API Key Manager**: Store, name, switch, or delete multiple Gemini API keys interactively. Easily switch keys mid-job if a quota limit is reached.

* **Zero-Hassle FFmpeg Setup**: Automatically detects if `ffmpeg` and `ffprobe` are installed; if missing, offers automatic installation via system package managers or portable static binaries.

* **Live Non-Blocking Keyboard Controls**: Monitor elapsed time in real time and press `c` at any moment to cancel the current task or `q` to safely clean up temporary files and exit.

## 🚀 Quick Start

### Prerequisites

* **Python 3.10+** installed on your system.

* A **Gemini API Key** (you will be prompted to enter and save it on first launch).

### Running on Windows

Simply double-click or run `run.bat` in Command Prompt / PowerShell:

```
run.bat
```

### Running on Linux / macOS

Make the launcher executable once, then run it:

```
chmod +x run.sh
./run.sh
```

> **Note:** On the first run, the launcher script automatically creates a local `.venv` virtual environment and installs `google-genai`. If the download is interrupted, the launcher automatically detects the incomplete setup on the next run, cleans up `.venv`, and rebuilds it cleanly.

## 🛠️ How to Use

Once the program starts, you can interact with the main menu using the following commands:

| Input / Shortcut | Action | 
| ----- | ----- | 
| **`<video_file_path>`** | Drag & drop a video file (or paste its path) and press Enter to generate an `.srt` subtitle alongside the video. | 
| **`t`** | Translate the last subtitle file generated during the current session. | 
| **`t <subtitle_path>`** | Translate a specific `.srt` or `.ass` subtitle file (e.g., `t movie.srt`). | 
| **`m`** | Open the interactive **Gemini API Key Manager** to add, delete, or switch your default API key. | 
| **`c`** | Cancel the active operation (FFmpeg extraction, upload, transcription, or translation) and return to the main menu. | 
| **`q`** | Safely clean up any temporary files and quit the application. | 

### Workflow Example

1. **Transcribe a Video**:

   * Drag and drop `lecture.mp4` into the terminal and press **Enter**.

   * Choose the audio language (`1` or **Enter** for Auto-detect, or type a code like `en`, `fa`, `es`, `de`, `ja`, etc.).

   * If the video is split into multiple parts, press **Enter** to process all parts or enter the number of parts you want.

   * Wait for completion; `lecture.srt` will be saved right next to `lecture.mp4`.

2. **Translate the Subtitle**:

   * Type `t` (or `t lecture.srt`) and press **Enter**.

   * Enter your desired translation instruction (or press **Enter** for the default *"Translate into Persian."*).

   * Once finished, choose whether to overwrite the original `.srt` file or keep the translated version as `lecture_new.srt`.

## ⚙️ Configuration

Advanced subtitle and chunking settings can be customized at the top of `Audio-to-SRT.py`:

* `ALLOW_TWO_LINES`, `MAX_WORDS_PER_LINE`, `MAX_CHARS_PER_LINE`: Control subtitle formatting and line length.

* `MIN_DURATION`, `MAX_DURATION`, `MAX_GAP`: Fine-tune subtitle display timing and pause detection.

* `SPLIT_DURATION_MINUTES`: Threshold in minutes for splitting long videos into chunks (set to `30` by default, or `None` to disable).

*(Your API keys, recent languages, and active job states are stored locally in `config.json`, which is excluded from Git via `.gitignore`.)*

## 📄 License

This project is licensed under the **MIT License**.
