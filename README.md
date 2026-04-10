# FDVC — Film Digital Vehicle Control
### ILM · RED Array Transfer Suite · v2.0

A unified on-set data management tool for large-scale RED camera arrays. Built for ILM's 42-camera volumetric capture stage, FDVC handles the full footage pipeline — from FTP pull off live cameras, to verified local transfer, to LTC timecode extraction — through a single PySide6 GUI.

---

## Features

- **FTP Pull** — targeted clip retrieval from up to 42 simultaneous RED cameras over a local network, maintaining full `CAMERA/REEL.RDM/CLIP.RDC` hierarchy
- **Verified Transfer** — multithreaded local-to-network transfer with xxhash128 integrity verification on every file
- **Metadata Scrape** — REDline-powered LTC timecode and FPS extraction across all R3D files, output to a master CSV
- **HTML Report** — embedded-logo transfer manifest with per-file hash comparison, human-readable file sizes, and total data summary
- **Mixed Media Support** — transfers RED, Blackmagic, Hyperdeck, and any other media in a single pass
- **Apple Silicon native** — resolves xxhsum for both M-series (`/opt/homebrew`) and Intel (`/usr/local`) Macs

---

## Requirements

```bash
python3 -m pip install PySide6 xxhash pandas
```

**macOS**
- xxhsum (optional, faster): `brew install xxhash`
- REDline (metadata tab only): ships with [REDCINE-X PRO](https://www.red.com/downloads)

**Ubuntu**
```bash
sudo apt install ffmpeg xxhash  # ffmpeg for completion sound, xxhash optional
pip3 install PySide6 xxhash pandas pyinstaller
```
> Build on the oldest Ubuntu version you need to support. A binary built on 20.04 runs on 20.04, 22.04, and 24.04. A binary built on 22.04 will not run on 20.04.

---

## Usage

```bash
python3 fdvc_gui.py
```

Or use the compiled app in `dist/` if built via PyInstaller.

### Modes

| Tab | Function |
|---|---|
| FTP Pull | Pull specific clips or full reels from the camera array |
| Transfer | Copy local footage to network with xxhash128 verification |
| Metadata | Scrape LTC timecode from R3D files via REDline |

### Clip input format (FTP tab)

```
G007_A083        ← specific clip: reel G007, camera A, clip 083
ALL:007          ← all cameras, reel 007 (calibration pass)
```

---

## Folder Hierarchy

Mirrors the RED card structure exactly:

```
ROOT/
  CAMERA_LABEL/        ← AA, GA, etc.
    REEL.RDM/
      CLIP.RDC/
        CLIP_001.R3D
        CLIP_001.RMD
        CLIP_001.rtn
```

---

## Camera Map

42 cameras mapped across `AA–KB` to a `172.20.114.141–182` subnet. Update `CAMERAS` in `fdvc_core.py` to match your network configuration.

---

## Credentials

Set environment variables to avoid plaintext credentials:

```bash
export FDVC_FTP_USER=your_user
export FDVC_FTP_PASS=your_password
```

---

## Build

**macOS**
```bash
~/Library/Python/3.9/bin/pyinstaller --onefile --windowed --add-data "ILM_FDVC_LOGO.png:." --add-data "swing3-94210.mp3:." --add-data "fdvc_core.py:." --add-data "fdvc_ftp.py:." --add-data "fdvc_transfer.py:." --add-data "fdvc_meta.py:." --name "FDVCTransferTool" fdvc_gui.py
```

**Ubuntu**
```bash
pyinstaller --onefile --windowed --add-data “ILM_FDVC_LOGO.png:.” --add-data “swing3-94210.mp3:.” --add-data “fdvc_core.py:.” --add-data “fdvc_ftp.py:.” --add-data “fdvc_transfer.py:.” --add-data “fdvc_meta.py:.” --name “FDVCTransferTool” fdvc_gui.py
```

Output: `dist/FDVCTransferTool`

---

## File Structure

| File | Purpose |
|---|---|
| `fdvc_gui.py` | PySide6 interface — start here |
| `fdvc_core.py` | Shared: camera map, hashing, FTP utils, manifest, HTML report |
| `fdvc_ftp.py` | FTP pull from camera array |
| `fdvc_transfer.py` | Verified local → network transfer |
| `fdvc_meta.py` | REDline LTC/timecode scraper |
| `fdvc.py` | CLI launcher (alternative to GUI) |

---

## Output

Every session produces a `_checksums/` folder at the transfer destination containing:
- `FDVC_Report_<PROJECT>_<TIMESTAMP>.html` — full per-file transfer report with hashes
- `fdvc_session.csv` — raw manifest (stage, camera, reel, clip, file, size, src_hash, dst_hash, status)

---

*Developed for ILM volumetric capture pipeline.*
