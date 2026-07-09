# SnipOCR

<p align="center">
  <img src="assets/logo.png" alt="SnipOCR logo" width="160" height="160">
</p>

<p align="center"><strong>SnipOCR</strong> — automatic <em>local</em> OCR when you take a screenshot.</p>

Works on **Windows** and **macOS**. When you capture the screen, SnipOCR:

1. Detects the new screenshot (clipboard and/or screenshot folder)
2. Runs **on-device OCR** (no cloud)
3. Puts the text on your clipboard
4. Shows a popup so you can review / edit / re-copy

---

## Platforms

| | Windows | macOS |
|--|---------|--------|
| **Capture** | Snipping Tool (`Win+Shift+S`) | Screenshot (`⌘⇧4`, `⌘⌃⇧4` for clipboard) |
| **OS OCR** | Windows.Media.Ocr | Apple Vision |
| **Neural OCR** | RapidOCR + ONNX Runtime (same on both) | RapidOCR + ONNX Runtime |
| **Clipboard** | win32 clipboard listener | Pasteboard changeCount poll |
| **File saves** | `Pictures\Screenshots` | Desktop / `Pictures/Screenshots` |
| **Config** | `%APPDATA%\SnipOCR\` | `~/Library/Application Support/SnipOCR/` |
| **Logs** | `%LOCALAPPDATA%\SnipOCR\` | `~/Library/Logs/SnipOCR/` |

All engines are **fully offline** after install (RapidOCR downloads ONNX models once on first use).

---

## OCR engines

SnipOCR supports three backends:

| Engine id | Name | Platform | Notes |
|-----------|------|----------|--------|
| `auto` | OS default | Win / Mac | Windows OCR or Apple Vision |
| `windows` | Windows OCR | Windows | Language packs via Windows Capability |
| `macos` | macOS Vision | macOS | Built-in Vision framework |
| **`rapid`** | **RapidOCR (ONNX)** | **Win + Mac (+ Linux)** | Light PP-OCR models via ONNX Runtime |

### When to use RapidOCR

- Same quality/behavior on Windows **and** macOS
- No Windows OCR language-pack setup
- Strong multi-language recognition (Chinese, Japanese, Korean, Latin, Arabic, …)
- Optional acceleration: DirectML (Windows), CoreML (macOS), CUDA (NVIDIA)

OS engines remain the lightest install path for pure English UI snips.

---

## Requirements

- **Python 3.11+**
- **Windows 10/11** *or* **macOS 12+**
- Platform OCR (optional if you only use RapidOCR):
  - Windows: OCR language pack (usually `en-US` already installed)
  - macOS: built-in Vision
- RapidOCR (recommended for cross-platform AI OCR):
  - `rapidocr` + `onnxruntime` (installed via `requirements.txt`)
  - First run downloads small ONNX models (~10–20 MB typical)

### Windows — OCR language packs (OS engine only)

Open **Windows PowerShell as Administrator**:

```powershell
Get-WindowsCapability -Online | Where-Object { $_.Name -Like 'Language.OCR*' }

Get-WindowsCapability -Online |
  Where-Object { $_.Name -Like 'Language.OCR*en-US*' } |
  Add-WindowsCapability -Online
```

Or:

```powershell
.\scripts\install_ocr_lang.ps1 -Language en-US
```

### macOS — Accessibility / notifications (optional)

- Screen Recording permission is **not** required; SnipOCR only reads the **clipboard** and screenshot **files** you already captured.
- Notifications use `osascript` (standard user notification).

### Optional GPU acceleration (RapidOCR)

```powershell
# Windows — DirectML (many AMD/Intel/NVIDIA GPUs)
pip uninstall -y onnxruntime onnxruntime-gpu onnxruntime-directml
pip install onnxruntime-directml

# NVIDIA CUDA (any OS with a matching CUDA toolkit)
pip uninstall -y onnxruntime onnxruntime-gpu onnxruntime-directml
pip install onnxruntime-gpu
```

macOS: the standard `onnxruntime` wheel may expose **CoreML**. Leave `rapidocr_accel` on `auto`.

Then set in config (or tray → **RapidOCR acceleration**):

```json
"rapidocr_accel": "dml"
```

or `"coreml"` / `"cuda"` / `"cpu"`.

---

## Quick start

### Windows

```powershell
cd path\to\snipocr
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Or:

```powershell
.\scripts\run.ps1
```

### macOS

```bash
cd path/to/snipocr
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Or:

```bash
chmod +x scripts/run.sh
./scripts/run.sh
```

A tray / menu-bar icon appears. Take a screenshot — text is OCR’d and copied.

**macOS tip:** hold **Control** while capturing (`⌘⌃⇧4`) to put the snip on the clipboard directly. File-based captures on Desktop are also watched.

### Switch to RapidOCR

1. Tray → **OCR engine** → **RapidOCR (ONNX)**  
2. Or edit config:

```json
"ocr_engine": "rapid"
```

First recognition may download models (one-time). Subsequent snips stay local and fast.

Optional: pre-download default models:

```bash
rapidocr download_models
```

---

## Tray menu

| Action | What it does |
|--------|----------------|
| **Enable / Disable SnipOCR** | Master switch |
| **Enable OCR all images** | OCR *any* clipboard image (not only screenshot tools) |
| **Show last result** | Re-open the last OCR popup |
| **OCR engine** | Radio: OS default / Windows or Vision / **RapidOCR (ONNX)** |
| **RapidOCR model** | Auto / Small / Mobile / Server / Tiny |
| **RapidOCR acceleration** | Auto / CPU / CoreML / DirectML / CUDA |
| **Quit** | Exit |

---

## How detection works

By default SnipOCR only OCRs images when:

1. A screenshot process was recently active  
   (Windows: `ScreenClippingHost` / Snipping Tool · macOS: `screencapture` / Screenshot), **or**
2. A new screenshot-like file appears in a known folder, **or**
3. (Windows) the clipboard owner is a snipping process

That avoids OCR-ing random images you copy from a browser.

Turn on **OCR all images** from the tray if you want every clipboard image processed.

Clipboard + file paths are de-duplicated so the same snip is not OCR’d twice.

---

## Settings

Stored at:

| Platform | Path |
|----------|------|
| Windows | `%APPDATA%\SnipOCR\config.json` |
| macOS | `~/Library/Application Support/SnipOCR/config.json` |

### Core

| Key | Default | Meaning |
|-----|---------|---------|
| `enabled` | `true` | Master switch |
| `ocr_engine` | `auto` | `auto` / `windows` / `macos` / **`rapid`** |
| `ocr_language` | `en-US` | Preferred language (BCP-47 or RapidOCR alias) |
| `replace_clipboard_with_text` | `true` | Put OCR text on clipboard |
| `ocr_all_clipboard_images` | `false` | Skip snip-process filter |
| `watch_screenshot_folders` | `true` | Watch Desktop / Screenshots folders |
| `show_popup` | `true` | Show result window |
| `popup_autohide_seconds` | `8` | Auto-hide popup (`0` = stay) |
| `show_toast` | `true` | Desktop notifications |
| `collapse_single_newlines` | `false` | Join soft line breaks into spaces |

### RapidOCR (when `ocr_engine` is `rapid`)

| Key | Default | Meaning |
|-----|---------|---------|
| `rapidocr_model_type` | `auto` | `auto` / `small` / `mobile` / `server` / `tiny` |
| `rapidocr_ocr_version` | `auto` | `auto` / `PP-OCRv6` / `PP-OCRv5` / `PP-OCRv4` |
| `rapidocr_use_cls` | `true` | Run text-line orientation classifier |
| `rapidocr_text_score` | `0.5` | Drop lines below this confidence |
| `rapidocr_accel` | `auto` | `auto` / `cpu` / `dml` / `coreml` / `cuda` |
| `rapidocr_intra_op_threads` | `-1` | ONNX Runtime intra-op threads (`-1` = library default) |
| `rapidocr_inter_op_threads` | `-1` | ONNX Runtime inter-op threads |

**Model tips**

| Preset | Typical use |
|--------|-------------|
| `auto` | English → mobile PP-OCRv4; otherwise small PP-OCRv6 (fast multi-lang) |
| `small` | Default modern path (PP-OCRv6 small when available) |
| `mobile` | Smaller / older mobile models |
| `server` | Heavier, higher accuracy |
| `tiny` | Experimental; may fall back if unsupported for your language |

**Language mapping** (`ocr_language` → RapidOCR)

| Examples | RapidOCR rec model |
|----------|-------------------|
| `en`, `en-US` | `en` |
| `zh-CN`, `zh` | `ch` (Chinese + often English) |
| `zh-TW`, `zh-HK` | `chinese_cht` |
| `ja`, `ja-JP` | `japan` |
| `ko`, `ko-KR` | `korean` |
| `de`, `fr`, `es`, `pt`, … | `latin` |
| `ru`, `uk`, … | `cyrillic` |
| `ar`, `hi`, `th`, `el`, … | matching script models |

If a language + model combo is unavailable, SnipOCR automatically falls back to a working combination.

Example config for cross-platform neural OCR:

```json
{
  "enabled": true,
  "ocr_engine": "rapid",
  "ocr_language": "en-US",
  "rapidocr_model_type": "auto",
  "rapidocr_ocr_version": "auto",
  "rapidocr_use_cls": true,
  "rapidocr_text_score": 0.5,
  "rapidocr_accel": "auto",
  "replace_clipboard_with_text": true,
  "show_popup": true,
  "show_toast": true
}
```

Logs:

| Platform | Path |
|----------|------|
| Windows | `%LOCALAPPDATA%\SnipOCR\snipocr.log` |
| macOS | `~/Library/Logs/SnipOCR/snipocr.log` |

---

## Project layout

```
snipocr/
  main.py
  assets/                 # brand logo + icons
  app/
    platform_util.py      # OS detection, paths, hints
    clipboard_io.py       # cross-platform facade
    clipboard_io_win.py
    clipboard_io_mac.py
    clipboard_watcher.py
    screenshot_watcher.py
    snip_detector.py
    service.py
    result_ui.py
    tray.py
    settings.py
    notifications.py
    paths.py
    ocr/
      base.py             # OCREngine protocol + OCRResult
      windows_ocr.py      # Windows.Media.Ocr
      macos_ocr.py        # Apple Vision
      rapid_ocr.py        # RapidOCR + ONNX Runtime
  scripts/
    run.ps1
    run.sh
    install_ocr_lang.ps1
    generate_logo.py
```

---

## Troubleshooting

### Windows — “No Windows OCR engine”

Install the OCR language pack (see above). Confirm:

```powershell
# Windows PowerShell 5.x
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
```

Or switch to RapidOCR: tray → **OCR engine** → **RapidOCR (ONNX)**.

### macOS — Vision import errors

```bash
pip install 'pyobjc-framework-Vision' 'pyobjc-framework-Quartz' 'pyobjc-framework-Cocoa'
```

### RapidOCR — “not installed” / import errors

```bash
pip install -U rapidocr onnxruntime
```

First use needs network once to download models (ModelScope CDN). After that, fully offline.

Pre-download:

```bash
rapidocr download_models
rapidocr check
```

### RapidOCR is slow on first snip

- Cold start loads ONNX sessions; later snips are much faster.
- Prefer `rapidocr_model_type: "auto"` or `"small"`.
- Enable GPU EP if available (`dml` / `coreml` / `cuda`).
- Huge screenshots are downscaled (max side 2000 px).

### Snips do nothing

- Is the tray icon enabled?
- Did you use the OS screenshot tool?
- Try **Enable OCR all images** once to test the OCR path.
- Check the log file paths above.
- On macOS, prefer `⌘⌃⇧4` (clipboard) or ensure Desktop/Screenshots is writable.

### Clipboard still has the image

If no text was found, the image is left on the clipboard on purpose.

---

## Privacy

- OCR runs locally (Windows.Media.Ocr, Apple Vision, or RapidOCR/ONNX)
- No cloud OCR API in the default path
- RapidOCR may download model weights once from RapidAI/ModelScope on first use
- OCR text is not written to disk by default (only logs metadata)

---

## License

MIT — use freely.
