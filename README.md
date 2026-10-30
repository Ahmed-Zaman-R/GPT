# ClearDesk

An offline Windows desktop app that cleans up document photos and combines them into a PDF. Your photos stay on your computer; original files are never modified.

## Run on Windows

Install **Python 3.12 (64-bit)** from python.org, including Tcl/Tk and the Python launcher. Open PowerShell in this project folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

1. Click **Import images** to select JPG, PNG, BMP, TIFF or WebP photos. Each imported file becomes one page (only the first frame of a multipage image is imported).
2. Select a page to preview it. **Clean gray** removes broad shadows and whitens paper; **Black & white** produces high-contrast pages; **Original** preserves colors. Cleanup settings apply to every page. Use **Preview original** for comparison; it does not change PDF export settings.
3. Adjust shadow removal, rotate pages, and move pages up or down. Drag a rectangle on the preview and confirm to crop. Reimport the original image to undo a crop.
4. Choose A4, Letter, or Image size, then **Export PDF**. A4 and Letter fit the image inside a portrait page with margins. Export uses full-resolution images; previews use reduced images and may differ slightly.

## Build a standalone Windows executable

Run on Windows after the installation commands above:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller==6.16.0
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name ClearDesk app.py
```

The result is `dist\ClearDesk.exe`; recipients do not need Python installed. The executable is unsigned, so Windows may display a reputation warning. The included **Windows executable** GitHub Actions workflow also builds it when manually run or when a `v*` tag is pushed; download the artifact from the completed run. This workflow must run in GitHub before an executable artifact exists.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests exercise shadow cleanup, text preservation, binary output, image import, and multipage PDF creation. Windows GUI behavior and executable packaging require Windows validation.

This version uses manual rectangular cropping, not automatic perspective correction. It does not include OCR or searchable PDFs. Very large batches require enough RAM to hold imported and processed pages. Color annotations are preserved only in Original mode.
