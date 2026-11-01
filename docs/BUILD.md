# Build the Windows executable

Use 64-bit Windows and a supported 64-bit Python installation. Building requires PyInstaller; playing the packaged game does not require Python.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python -m PyInstaller --noconfirm --clean --onefile --console --name DungeonMerchant --add-data "assets;assets" --add-data "index.html;." --add-data "*.js;." --add-data "*.css;." main.py
```

The executable is `dist/DungeonMerchant.exe`. Keep the console launcher open while playing; close it to stop the server. The game automatically opens a browser. For a verification launch without opening a browser:

```powershell
dist\DungeonMerchant.exe --no-browser --port 8765 --save output\verification-save.json
```

Do not publish local saves, imported audio, development environments, caches, tokens or build intermediates. Public audio can be regenerated with `python tools/generate_public_audio.py`. Test the source and the packaged executable before creating a release.
