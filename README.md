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
| **OCR engine** | Windows.Media.Ocr | Apple Vision |
| **Clipboard** | win32 clipboard listener | Pasteboard changeCount poll |
| **File saves** | `Pictures\Screenshots` | Desktop / `Pictures/Screenshots` |
| **Config** | `%APPDATA%\SnipOCR\` | `~/Library/Application Support/SnipOCR/` |
| **Logs** | `%LOCALAPPDATA%\SnipOCR\` | `~/Library/Logs/SnipOCR/` |

Both engines are **fully offline** after install.

---

## Requirements

- **Python 3.11+**
- **Windows 10/11** *or* **macOS 12+** (Vision framework)
- Platform OCR support:
  - Windows: OCR language pack (usually `en-US` already installed)
  - macOS: built-in Vision (no extra language pack step for English)

### Windows — OCR language packs

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

---

## Tray menu

| Action | What it does |
|--------|----------------|
| **Enable / Disable SnipOCR** | Master switch |
| **Enable OCR all images** | OCR *any* clipboard image (not only screenshot tools) |
| **Show last result** | Re-open the last OCR popup |
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

| Key | Default | Meaning |
|-----|---------|---------|
| `enabled` | `true` | Master switch |
| `ocr_engine` | `auto` | `auto` / `windows` / `macos` |
| `ocr_language` | `en-US` | Preferred recognition language |
| `replace_clipboard_with_text` | `true` | Put OCR text on clipboard |
| `ocr_all_clipboard_images` | `false` | Skip snip-process filter |
| `watch_screenshot_folders` | `true` | Watch Desktop / Screenshots folders |
| `show_popup` | `true` | Show result window |
| `popup_autohide_seconds` | `8` | Auto-hide popup (`0` = stay) |
| `show_toast` | `true` | Desktop notifications |

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
      windows_ocr.py      # Windows.Media.Ocr
      macos_ocr.py        # Apple Vision
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

### macOS — Vision import errors

```bash
pip install 'pyobjc-framework-Vision' 'pyobjc-framework-Quartz' 'pyobjc-framework-Cocoa'
```

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

- OCR runs locally (Windows.Media.Ocr or Apple Vision)
- No network calls in the default path
- OCR text is not written to disk by default (only logs metadata)

---

## License

MIT — use freely.
