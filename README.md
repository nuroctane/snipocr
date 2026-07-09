# SnipOCR

<p align="center">
  <img src="assets/logo.png" alt="SnipOCR logo" width="160" height="160">
</p>

<p align="center"><strong>SnipOCR</strong> — automatic local OCR for Windows Snipping Tool captures.</p>

Automatic **local OCR** for Windows Snipping Tool captures.

1. Press **Win+Shift+S** and snip text on screen  
2. SnipOCR reads the clipboard image  
3. Runs **Windows.Media.Ocr** offline on your PC  
4. Puts the text on your clipboard and shows a popup  

No cloud APIs. Everything stays on your device.

## Requirements

- Windows 10/11  
- Python 3.11+  
- A Windows **OCR language pack** (usually `en-US` is already installed)

### Check / install OCR language packs

Open **Windows PowerShell as Administrator**:

```powershell
Get-WindowsCapability -Online | Where-Object { $_.Name -Like 'Language.OCR*' }

# Install English (US) if missing:
Get-WindowsCapability -Online |
  Where-Object { $_.Name -Like 'Language.OCR*en-US*' } |
  Add-WindowsCapability -Online
```

Or run:

```powershell
.\scripts\install_ocr_lang.ps1 -Language en-US
```

## Quick start

```powershell
cd C:\Users\david\Laboratory\snipocr
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Or:

```powershell
.\scripts\run.ps1
```

A tray icon appears. Snip something with **Win+Shift+S** — text is OCR’d and copied.

## Tray menu

| Action | What it does |
|--------|----------------|
| **Enable / Disable SnipOCR** | Master switch |
| **Enable OCR all images** | OCR *any* clipboard image (not only Snipping Tool) |
| **Show last result** | Re-open the last OCR popup |
| **Quit** | Exit |

## How snip detection works

By default SnipOCR only OCRs clipboard images when **Snipping Tool / ScreenClippingHost** was recently active. That avoids OCR-ing random images you copy from a browser.

Turn on **OCR all images** from the tray if you want every clipboard image processed.

## Settings

Stored at:

```
%APPDATA%\SnipOCR\config.json
```

Useful keys:

| Key | Default | Meaning |
|-----|---------|---------|
| `enabled` | `true` | Master switch |
| `ocr_language` | `en-US` | Windows OCR language tag |
| `replace_clipboard_with_text` | `true` | Put OCR text on clipboard |
| `ocr_all_clipboard_images` | `false` | Skip snip-process filter |
| `show_popup` | `true` | Show result window |
| `popup_autohide_seconds` | `8` | Auto-hide popup (0 = stay) |
| `show_toast` | `true` | Toast notifications |

Logs:

```
%LOCALAPPDATA%\SnipOCR\snipocr.log
```

## Project layout

```
snipocr/
  main.py
  assets/
    logo.png          # master brand mark (black + geometric)
    logo.ico          # Windows tray / window icon
    logo-*.png        # sized exports
    icon-*.png
  app/
    clipboard_io.py
    clipboard_watcher.py
    snip_detector.py
    service.py
    result_ui.py
    tray.py
    settings.py
    notifications.py
    paths.py
    ocr/
      windows_ocr.py
  scripts/
    run.ps1
    install_ocr_lang.ps1
    generate_logo.py
```

## Troubleshooting

**No text / “No Windows OCR engine”**  
Install the OCR language pack (see above). Confirm languages:

```powershell
# Windows PowerShell 5.x
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
```

**Snips do nothing**  
- Is the tray icon enabled?  
- Did you snip with Snipping Tool (`Win+Shift+S`)?  
- Try **Enable OCR all images** once to test the OCR path.  
- Check `%LOCALAPPDATA%\SnipOCR\snipocr.log`

**Clipboard still has the image**  
If no text was found, the image is left on the clipboard on purpose.

## Privacy

- OCR runs locally via Windows.Media.Ocr  
- No network calls in the default path  
- OCR text is not written to disk by default (only logs metadata)

## License

MIT — use freely.
