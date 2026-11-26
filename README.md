# KomaStage

A cross-platform (**macOS, Windows & Linux**) desktop mascot engine built with Python and PyQt6. Turn your desktop into an interactive stage and import your own custom Shimeji character packs via `.zip` archives or folders.

## Features
- **Custom Character Import (`.zip` & Folder):** Import any standard Shimeji sprite pack with a single click—automatically detects nested `img/` folders.
- **KomaStage Control Panel:** Preview installed characters, summon multiple mascots (`+1`), and adjust mascot size (`64px`–`256px`) and movement speed (`50%`–`250%`) in real time.
- **State Machine & Physics:** Walking, running, special animations, sitting, hiding in a box, wall/ceiling climbing, and interactive drag-and-drop gravity.
- **Missing Frame Fallback:** Gracefully handles custom Shimeji packs with missing or non-standard animation frames without crashing.

## Download (No Installation Required)
Head over to the **[Releases](../../releases)** section on the right to download the pre-built binary for your OS:
- **macOS:** `KomaStage-Mac.zip` (Unzip and right-click > Open on first launch)
- **Windows:** `KomaStage.exe`
- **Linux:** `KomaStage-Linux.tar.gz` (Extract and run `./KomaStage`)

## Run from Source
    git clone https://github.com/hiikari76/KomaStage.git
    cd KomaStage
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    python main.py

## Credits
Default Hatsune Miku Shimeji sprites are sourced from [Shimeji.org](https://shimeji.org/u/5elo0kxg).
