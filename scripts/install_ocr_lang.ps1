# Install Windows OCR language packs (requires Administrator).
# Example: .\install_ocr_lang.ps1
# Example: .\install_ocr_lang.ps1 -Language en-US

param(
    [string]$Language = "en-US"
)

$ErrorActionPreference = "Stop"

Write-Host "Listing Language.OCR capabilities..."
Get-WindowsCapability -Online |
    Where-Object { $_.Name -Like 'Language.OCR*' } |
    Format-Table Name, State -AutoSize

$cap = Get-WindowsCapability -Online |
    Where-Object { $_.Name -Like "Language.OCR*$Language*" } |
    Select-Object -First 1

if (-not $cap) {
    Write-Error "No OCR capability matched language '$Language'."
}

Write-Host "Installing $($cap.Name) (State=$($cap.State))..."
$cap | Add-WindowsCapability -Online

Write-Host "Done. Restart SnipOCR if it is running."
Write-Host "Verify in PowerShell (Windows PowerShell 5.x):"
Write-Host @'
  [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
  [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
'@
