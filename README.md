# FDVC v2.0 — Unified RED Array Transfer Suite
**Apple Silicon · xxhash128 · RED Hierarchy Preserved**

---

## Files

| File | Purpose |
|---|---|
| `fdvc.py` | Unified launcher — start here |
| `fdvc_core.py` | Shared: camera map, hashing, FTP utils, manifest, HTML report |
| `fdvc_ftp.py` | Pull clips from 42-camera array → local storage |
| `fdvc_transfer.py` | Local → network transfer with xxhash128 verification |
| `fdvc_meta.py` | REDline LTC/timecode scraper → master CSV |

---

## Quick Start

```bash
# Interactive menu
python3 fdvc.py

# Direct mode
python3 fdvc.py ftp
python3 fdvc.py transfer
python3 fdvc.py meta
python3 fdvc.py all        # ftp → transfer → meta in sequence
```

---

## Folder Hierarchy

All tools write and expect this structure — mirrors the RED card exactly:

```
ROOT/
  CAMERA_LABEL/        ← AA, GA, etc.
    REEL.RDM/
      CLIP.RDC/
        CLIP_001.R3D
        CLIP_001.RMD
        ...
```

---

## Clip Input Format (FTP mode)

```
G007_A083          ← specific clip: reel G007, camera A, clip 083
ALL:007            ← all cameras, reel 007 (calibration pass)
```

---

## Credentials

Set env vars to avoid plaintext passwords:

```bash
export FDVC_FTP_USER=ftp1
export FDVC_FTP_PASS=your_password
```

Or edit defaults in `fdvc_core.py`.

---

## Dependencies

```bash
# Required
pip install xxhash pandas

# REDline (for meta mode) — ships with REDCINE-X PRO
# xxhsum binary (optional, faster than pure-python)
brew install xxhash
```

---

## Manifest

Every operation appends to a single `fdvc_session.csv`:

```
timestamp | stage | camera | reel | clip | file | size_bytes | src_hash | dst_hash | status | note
```

Stages: `FTP` → `Transfer` → `Meta`

HTML report auto-generated after transfer stage.

---

## Notes

- Transfer skips files already at destination with matching hash
- FTP pull verifies every downloaded file immediately
- `ALL:007` is the intended trigger for a 12-camera calibration pass
- xxhsum binary used if found; falls back to pure-python xxhash, then sha256
