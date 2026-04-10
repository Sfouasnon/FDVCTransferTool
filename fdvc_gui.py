#!/usr/bin/env python3
"""
FDVC GUI v2.0 — PySide6 Interface
Tabs: FTP Pull | Transfer | Metadata
"""
import sys
import threading
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QCheckBox, QSpinBox, QSplitter, QFrame, QPlainTextEdit,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QObject, QThread, QSize
from PySide6.QtGui import QFont, QColor, QPalette, QTextCursor, QIcon

sys.path.insert(0, str(Path(__file__).parent))


# ── Stylesheet ─────────────────────────────────────────────────────────────────
STYLE = """
QMainWindow, QWidget {
    background-color: #111111;
    color: #e0e0e0;
    font-family: "SF Mono", "Menlo", monospace;
    font-size: 12px;
}
QTabWidget::pane {
    border: 1px solid #2a2a2a;
    background: #111111;
}
QTabBar::tab {
    background: #1a1a1a;
    color: #888;
    padding: 10px 28px;
    border: none;
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
}
QTabBar::tab:selected {
    background: #111111;
    color: #00ff9f;
    border-bottom: 2px solid #00ff9f;
}
QTabBar::tab:hover:!selected {
    color: #ccc;
    background: #1e1e1e;
}
QGroupBox {
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 8px;
    color: #666;
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}
QLineEdit {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 3px;
    padding: 6px 10px;
    color: #e0e0e0;
    selection-background-color: #00ff9f;
    selection-color: #000;
}
QLineEdit:focus {
    border-color: #00ff9f;
}
QPushButton {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 3px;
    padding: 7px 18px;
    color: #ccc;
    letter-spacing: 1px;
    font-size: 11px;
}
QPushButton:hover {
    background: #222;
    border-color: #00ff9f;
    color: #00ff9f;
}
QPushButton:pressed {
    background: #0d2a1a;
}
QPushButton#primary {
    background: #003d1f;
    border: 1px solid #00ff9f;
    color: #00ff9f;
    font-weight: bold;
}
QPushButton#primary:hover {
    background: #005229;
}
QPushButton#primary:disabled {
    background: #1a1a1a;
    border-color: #333;
    color: #444;
}
QPushButton#browse {
    padding: 6px 12px;
    color: #888;
    font-size: 11px;
    min-width: 36px;
}
QPlainTextEdit, QTextEdit {
    background: #0a0a0a;
    border: 1px solid #1e1e1e;
    border-radius: 3px;
    color: #00cc7a;
    font-family: "SF Mono", "Menlo", monospace;
    font-size: 11px;
    selection-background-color: #003d1f;
}
QProgressBar {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 2px;
    height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: #00ff9f;
    border-radius: 2px;
}
QTableWidget {
    background: #0d0d0d;
    border: 1px solid #1e1e1e;
    gridline-color: #1a1a1a;
    alternate-background-color: #111111;
}
QTableWidget::item {
    padding: 4px 8px;
    color: #ccc;
}
QTableWidget::item:selected {
    background: #003d1f;
    color: #00ff9f;
}
QHeaderView::section {
    background: #1a1a1a;
    color: #666;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #2a2a2a;
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
}
QSpinBox {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 3px;
    padding: 5px 8px;
    color: #e0e0e0;
    min-width: 60px;
}
QCheckBox {
    color: #888;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #333;
    border-radius: 2px;
    background: #1a1a1a;
}
QCheckBox::indicator:checked {
    background: #00ff9f;
    border-color: #00ff9f;
}
QSplitter::handle {
    background: #2a2a2a;
    width: 1px;
    height: 1px;
}
QLabel#header {
    color: #00ff9f;
    font-size: 10px;
    letter-spacing: 3px;
    text-transform: uppercase;
}
QLabel#stat {
    color: #00ff9f;
    font-size: 18px;
    font-weight: bold;
}
QLabel#stat_label {
    color: #444;
    font-size: 10px;
    letter-spacing: 1px;
}
QFrame#divider {
    background: #2a2a2a;
    max-height: 1px;
}
"""


# ── Worker signals ─────────────────────────────────────────────────────────────
class WorkerSignals(QObject):
    log       = Signal(str)          # text line for console
    progress  = Signal(int, int)     # (done, total) for progress bar
    table_row = Signal(dict)         # row dict for status table
    finished  = Signal(bool)         # success/fail


# ── Reusable widgets ───────────────────────────────────────────────────────────
def path_row(label: str, placeholder: str = "") -> tuple[QHBoxLayout, QLineEdit]:
    layout = QHBoxLayout()
    le = QLineEdit()
    le.setPlaceholderText(placeholder)
    btn = QPushButton("…")
    btn.setObjectName("browse")
    btn.setFixedWidth(36)
    btn.clicked.connect(lambda: _browse_dir(le))
    layout.addWidget(le)
    layout.addWidget(btn)
    return layout, le


def _browse_dir(line_edit: QLineEdit):
    d = QFileDialog.getExistingDirectory(None, "Select Folder",
                                         line_edit.text() or str(Path.home()))
    if d:
        line_edit.setText(d)


def make_console() -> QPlainTextEdit:
    c = QPlainTextEdit()
    c.setReadOnly(True)
    c.setMaximumBlockCount(2000)
    return c


def log_to(console: QPlainTextEdit, text: str, color: str = "#00cc7a"):
    ts = datetime.now().strftime("%H:%M:%S")
    console.appendHtml(
        f'<span style="color:#444">[{ts}]</span> '
        f'<span style="color:{color}">{text}</span>'
    )
    console.moveCursor(QTextCursor.End)


def make_status_table(columns: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(columns))
    t.setHorizontalHeaderLabels(columns)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    t.setAlternatingRowColors(True)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectRows)
    return t


def add_table_row(table: QTableWidget, values: list, status: str = ""):
    row = table.rowCount()
    table.insertRow(row)
    for col, val in enumerate(values):
        item = QTableWidgetItem(str(val))
        if col == 0:  # status column
            color = {"OK": "#00ff9f", "Verified": "#00ff9f",
                     "FAIL": "#ff4444", "MISSING": "#ff4444",
                     "OFFLINE": "#ff8800", "Skipped": "#666666",
                     "Running": "#ffcc00"}.get(val, "#ccc")
            item.setForeground(QColor(color))
        table.setItem(row, col, item)
    table.scrollToBottom()


# ── FTP Tab ────────────────────────────────────────────────────────────────────
class FTPTab(QWidget):
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()
        self._thread = None
        self._build_ui()
        self.signals.log.connect(lambda t: log_to(self.console, t))
        self.signals.progress.connect(self._on_progress)
        self.signals.table_row.connect(lambda d: add_table_row(
            self.table, [d.get(k,"") for k in ["status","camera","reel","clip","file","note"]]))
        self.signals.finished.connect(self._on_finished)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)

        # ── Config ──
        cfg = QGroupBox("Configuration")
        g = QGridLayout(cfg)
        g.setSpacing(8)

        g.addWidget(QLabel("Output Directory"), 0, 0)
        row, self.out_dir = path_row("", "/Volumes/LocalRAID/media")
        g.addLayout(row, 0, 1)

        g.addWidget(QLabel("Clip List"), 1, 0, Qt.AlignTop)
        self.clip_input = QPlainTextEdit()
        self.clip_input.setPlaceholderText(
            "One per line:\n  G007_A083\n  H007_B081\n  ALL:007   ← entire reel from all cameras"
        )
        self.clip_input.setFixedHeight(100)
        g.addWidget(self.clip_input, 1, 1)

        root.addWidget(cfg)

        # ── Controls ──
        ctrl = QHBoxLayout()
        self.btn_run = QPushButton("▶  BEGIN FTP PULL")
        self.btn_run.setObjectName("primary")
        self.btn_run.clicked.connect(self._run)
        ctrl.addWidget(self.btn_run)
        ctrl.addStretch()

        self.prog = QProgressBar()
        self.prog.setFixedHeight(6)
        self.prog_label = QLabel("—")
        self.prog_label.setFixedWidth(100)
        ctrl.addWidget(self.prog_label)
        ctrl.addWidget(self.prog)
        root.addLayout(ctrl)

        # ── Splitter: table + console ──
        split = QSplitter(Qt.Vertical)

        self.table = make_status_table(["Status","Camera","Reel","Clip","File","Note"])
        split.addWidget(self.table)

        self.console = make_console()
        split.addWidget(self.console)
        split.setSizes([220, 180])

        root.addWidget(split)

    def _on_progress(self, done, total):
        self.prog.setMaximum(max(total, 1))
        self.prog.setValue(done)
        self.prog_label.setText(f"{done} / {total}")

    def _on_finished(self, ok):
        self.btn_run.setEnabled(True)
        color = "#00ff9f" if ok else "#ff4444"
        msg   = "FTP pull complete." if ok else "FTP pull finished with errors."
        log_to(self.console, msg, color)

    def _run(self):
        out = self.out_dir.text().strip()
        clips_raw = self.clip_input.toPlainText().strip()
        if not out or not clips_raw:
            log_to(self.console, "⚠  Output dir and clip list required.", "#ff8800")
            return

        clips = [l.strip() for l in clips_raw.splitlines() if l.strip()]
        self.btn_run.setEnabled(False)
        self.table.setRowCount(0)
        log_to(self.console, f"Starting FTP pull → {out}")

        sig = self.signals
        out_path = Path(out)

        def work():
            try:
                from fdvc_core import Manifest
                from fdvc_ftp import pull_clips as _pull

                manifest_csv = out_path / "_manifests" / "fdvc_session.csv"
                out_path.mkdir(parents=True, exist_ok=True)
                manifest = Manifest(manifest_csv)

                # Monkey-patch progress into pull_clips via signals
                total_clips = len(clips)
                done_clips  = [0]

                # We wrap ftp_download_dir to emit signals
                import fdvc_core as core
                _orig_dl = core.ftp_download_dir

                def patched_dl(ftp, remote_dir, local_dir):
                    _orig_dl(ftp, remote_dir, local_dir)
                    done_clips[0] += 1
                    sig.progress.emit(done_clips[0], total_clips)

                core.ftp_download_dir = patched_dl

                # Redirect print → signal
                import builtins
                _orig_print = builtins.print
                def sig_print(*args, **kwargs):
                    text = " ".join(str(a) for a in args)
                    text = text.strip()
                    if text:
                        color = "#ff4444" if "❌" in text else \
                                "#ffcc00" if "⚠" in text else "#00cc7a"
                        sig.log.emit(text)
                builtins.print = sig_print

                try:
                    _pull(clips, out_path, manifest)
                finally:
                    builtins.print = _orig_print
                    core.ftp_download_dir = _orig_dl

                # Emit table rows from manifest
                import csv
                with open(manifest_csv, newline="") as f:
                    for row in csv.DictReader(f):
                        if row.get("stage") == "FTP":
                            sig.table_row.emit(row)

                sig.finished.emit(True)
            except Exception as e:
                sig.log.emit(f"❌  {e}")
                sig.finished.emit(False)

        self._thread = threading.Thread(target=work, daemon=True)
        self._thread.start()


# ── Transfer Tab ───────────────────────────────────────────────────────────────
class TransferTab(QWidget):
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()
        self._thread = None
        self._build_ui()
        self.signals.log.connect(lambda t: log_to(self.console, t))
        self.signals.progress.connect(self._on_progress)
        self.signals.table_row.connect(lambda d: add_table_row(
            self.table,
            [d.get(k,"") for k in ["status","camera","reel","clip","file","size_bytes","src_hash"]]))
        self.signals.finished.connect(self._on_finished)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)

        cfg = QGroupBox("Configuration")
        g = QGridLayout(cfg)
        g.setSpacing(8)

        g.addWidget(QLabel("Project Name"), 0, 0)
        self.project = QLineEdit()
        self.project.setPlaceholderText("e.g.  ILM_PROJ_001")
        g.addWidget(self.project, 0, 1)

        g.addWidget(QLabel("Source (local)"), 1, 0)
        row, self.src = path_row("", "/Volumes/LocalRAID/media")
        g.addLayout(row, 1, 1)

        g.addWidget(QLabel("Destination (network)"), 2, 0)
        row, self.dst = path_row("", "/Volumes/NetworkShare/media")
        g.addLayout(row, 2, 1)

        g.addWidget(QLabel("Clip Filter"), 3, 0)
        self.clip_filter = QLineEdit()
        self.clip_filter.setPlaceholderText("Blank = all  |  e.g. GA  G007_A083  H007")
        g.addWidget(self.clip_filter, 3, 1)

        opts = QHBoxLayout()
        self.verify_chk = QCheckBox("Verify xxhash128")
        self.verify_chk.setChecked(True)
        opts.addWidget(self.verify_chk)
        opts.addSpacing(20)
        opts.addWidget(QLabel("Threads"))
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 16)
        self.threads_spin.setValue(4)
        opts.addWidget(self.threads_spin)
        opts.addStretch()
        g.addLayout(opts, 4, 1)

        root.addWidget(cfg)

        ctrl = QHBoxLayout()
        self.btn_run = QPushButton("▶  BEGIN TRANSFER")
        self.btn_run.setObjectName("primary")
        self.btn_run.clicked.connect(self._run)
        ctrl.addWidget(self.btn_run)
        ctrl.addStretch()

        self.prog_label = QLabel("—")
        self.prog_label.setFixedWidth(100)
        self.prog = QProgressBar()
        self.prog.setFixedHeight(6)
        ctrl.addWidget(self.prog_label)
        ctrl.addWidget(self.prog)
        root.addLayout(ctrl)

        # Stats row
        stats = QHBoxLayout()
        for attr, label in [("stat_ok","VERIFIED"), ("stat_fail","FAILED"), ("stat_skip","SKIPPED")]:
            box = QVBoxLayout()
            n = QLabel("0")
            n.setObjectName("stat")
            l = QLabel(label)
            l.setObjectName("stat_label")
            box.addWidget(n, alignment=Qt.AlignCenter)
            box.addWidget(l, alignment=Qt.AlignCenter)
            setattr(self, attr, n)
            stats.addLayout(box)
        stats.addStretch()
        root.addLayout(stats)

        split = QSplitter(Qt.Vertical)
        self.table = make_status_table(["Status","Camera","Reel","Clip","File","Size","Hash"])
        split.addWidget(self.table)
        self.console = make_console()
        split.addWidget(self.console)
        split.setSizes([240, 160])
        root.addWidget(split)

    def _on_progress(self, done, total):
        self.prog.setMaximum(max(total, 1))
        self.prog.setValue(done)
        self.prog_label.setText(f"{done} / {total}")

    def _update_stats(self):
        ok = fail = skip = 0
        for row in range(self.table.rowCount()):
            s = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
            if s in ("Verified", "OK"):    ok   += 1
            elif s in ("FAIL","MISSING"):  fail += 1
            elif s == "Skipped":           skip += 1
        self.stat_ok.setText(str(ok))
        self.stat_fail.setText(str(fail))
        self.stat_skip.setText(str(skip))

    def _on_finished(self, ok):
        self.btn_run.setEnabled(True)
        self._update_stats()
        color = "#00ff9f" if ok else "#ff4444"
        log_to(self.console, "Transfer complete." if ok else "Transfer finished with errors.", color)

    def _run(self):
        src = self.src.text().strip()
        dst = self.dst.text().strip()
        project = self.project.text().strip()
        if not all([src, dst, project]):
            log_to(self.console, "⚠  Source, destination, and project name required.", "#ff8800")
            return

        self.btn_run.setEnabled(False)
        self.table.setRowCount(0)
        self.stat_ok.setText("0"); self.stat_fail.setText("0"); self.stat_skip.setText("0")

        clip_filter = self.clip_filter.text().strip().split() or []
        threads     = self.threads_spin.value()
        verify      = self.verify_chk.isChecked()
        sig         = self.signals
        src_path    = Path(src)
        dst_path    = Path(dst)
        manifest_csv = src_path / "_manifests" / "fdvc_session.csv"

        log_to(self.console, f"Transfer: {src} → {dst}  [{threads} threads, verify={'ON' if verify else 'OFF'}]")

        def work():
            try:
                from fdvc_core import Manifest, write_html_report
                from fdvc_transfer import discover_files, transfer_file
                import threading as _t
                import csv

                dst_path.mkdir(parents=True, exist_ok=True)
                manifest = Manifest(manifest_csv)

                files_meta = discover_files(src_path, clip_filter)
                if not files_meta:
                    sig.log.emit("❌  No files found. Check source path or clip filter.")
                    sig.finished.emit(False)
                    return

                files = [
                    (f, dst_path / f.relative_to(src_path), cam, reel, clip)
                    for f, cam, reel, clip in files_meta
                ]

                sig.progress.emit(0, len(files))
                done    = [0]
                lock    = _t.Lock()

                from concurrent.futures import ThreadPoolExecutor, as_completed
                with ThreadPoolExecutor(max_workers=threads) as pool:
                    futures = {
                        pool.submit(transfer_file, s, d, manifest, cam, reel, clip, verify, lock): s
                        for s, d, cam, reel, clip in files
                    }
                    for future in as_completed(futures):
                        src_f = futures[future]
                        done[0] += 1
                        sig.progress.emit(done[0], len(files))
                        try:
                            future.result()
                        except Exception as e:
                            sig.log.emit(f"❌  {src_f.name}: {e}")

                # Read manifest and emit rows
                with open(manifest_csv, newline="") as f:
                    for row in csv.DictReader(f):
                        if row.get("stage") == "Transfer":
                            sig.table_row.emit(row)

                # HTML report → dst/_checksums/
                from fdvc_core import play_completion_sound
                ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
                checksums   = dst_path / "_checksums"
                checksums.mkdir(parents=True, exist_ok=True)
                report      = checksums / f"FDVC_Report_{project}_{ts}.html"
                ok_c, fail_c = write_html_report(manifest_csv, project, report)
                sig.log.emit(f"📄  Report: {report}  (✔{ok_c} ✘{fail_c})")
                play_completion_sound()
                sig.finished.emit(fail_c == 0)

            except Exception as e:
                sig.log.emit(f"❌  {e}")
                sig.finished.emit(False)

        self._thread = threading.Thread(target=work, daemon=True)
        self._thread.start()


# ── Meta Tab ───────────────────────────────────────────────────────────────────
class MetaTab(QWidget):
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()
        self._thread = None
        self._build_ui()
        self.signals.log.connect(lambda t: log_to(self.console, t))
        self.signals.progress.connect(self._on_progress)
        self.signals.table_row.connect(lambda d: add_table_row(
            self.table,
            [d.get(k,"") for k in ["status","camera","file","ltc_in","ltc_out","fps"]]))
        self.signals.finished.connect(self._on_finished)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)

        cfg = QGroupBox("Configuration")
        g = QGridLayout(cfg)
        g.setSpacing(8)

        g.addWidget(QLabel("R3D Root"), 0, 0)
        row, self.r3d_root = path_row("", "/Volumes/LocalRAID/media")
        g.addLayout(row, 0, 1)

        g.addWidget(QLabel("Per-Frame CSV Output"), 1, 0)
        row, self.pf_dir = path_row("", "/tmp/fdvc_perframe")
        g.addLayout(row, 1, 1)

        root.addWidget(cfg)

        ctrl = QHBoxLayout()
        self.btn_run = QPushButton("▶  SCRAPE LTC METADATA")
        self.btn_run.setObjectName("primary")
        self.btn_run.clicked.connect(self._run)
        ctrl.addWidget(self.btn_run)
        ctrl.addStretch()
        self.prog_label = QLabel("—")
        self.prog_label.setFixedWidth(100)
        self.prog = QProgressBar()
        self.prog.setFixedHeight(6)
        ctrl.addWidget(self.prog_label)
        ctrl.addWidget(self.prog)
        root.addLayout(ctrl)

        split = QSplitter(Qt.Vertical)
        self.table = make_status_table(["Status","Camera","File","LTC In","LTC Out","FPS"])
        split.addWidget(self.table)
        self.console = make_console()
        split.addWidget(self.console)
        split.setSizes([260, 140])
        root.addWidget(split)

    def _on_progress(self, done, total):
        self.prog.setMaximum(max(total, 1))
        self.prog.setValue(done)
        self.prog_label.setText(f"{done} / {total}")

    def _on_finished(self, ok):
        self.btn_run.setEnabled(True)
        color = "#00ff9f" if ok else "#ff4444"
        log_to(self.console, "Metadata scrape complete." if ok else "Scrape finished with errors.", color)

    def _run(self):
        r3d = self.r3d_root.text().strip()
        pf  = self.pf_dir.text().strip()
        if not r3d or not pf:
            log_to(self.console, "⚠  R3D root and output folder required.", "#ff8800")
            return

        self.btn_run.setEnabled(False)
        self.table.setRowCount(0)
        sig         = self.signals
        r3d_path    = Path(r3d)
        pf_path     = Path(pf)
        manifest_csv = r3d_path / "_manifests" / "fdvc_session.csv"

        log_to(self.console, f"Scanning {r3d_path} for .R3D files…")

        def work():
            try:
                from fdvc_core import Manifest
                from fdvc_meta import find_redline, run_redline, summarize
                import csv as _csv

                r3d_files = sorted(r3d_path.rglob("*.R3D"))
                if not r3d_files:
                    sig.log.emit("❌  No .R3D files found.")
                    sig.finished.emit(False)
                    return

                sig.log.emit(f"Found {len(r3d_files)} R3D files.")
                sig.progress.emit(0, len(r3d_files))

                try:
                    redline = find_redline()
                except RuntimeError as e:
                    sig.log.emit(f"❌  {e}")
                    sig.finished.emit(False)
                    return

                manifest = Manifest(manifest_csv)
                pf_path.mkdir(parents=True, exist_ok=True)

                rows = []
                for i, r3d_file in enumerate(r3d_files, 1):
                    pf_csv = pf_path / f"{r3d_file.stem}_per_frame.csv"
                    sig.log.emit(f"→ {r3d_file.name}")
                    try:
                        run_redline(redline, r3d_file, pf_csv)
                        info = summarize(pf_csv, r3d_file)
                        rows.append(info)
                        sig.log.emit(
                            f"  ✔  {info['camera']}  "
                            f"{info['ltc_in']} → {info['ltc_out']}  "
                            f"{info['fps']}fps"
                        )
                        manifest.write(
                            stage="Meta", camera=info["camera"],
                            file=info["file"],
                            note=f"LTC {info['ltc_in']}→{info['ltc_out']} {info['fps']}fps",
                            status="OK"
                        )
                        sig.table_row.emit({
                            "status": "OK",
                            "camera": info["camera"],
                            "file":   info["file"],
                            "ltc_in": info["ltc_in"],
                            "ltc_out": info["ltc_out"],
                            "fps":    info["fps"],
                        })
                    except Exception as e:
                        sig.log.emit(f"  ✘  {r3d_file.name}: {e}")
                        manifest.write(stage="Meta", file=r3d_file.name,
                                       status="FAIL", note=str(e))
                        sig.table_row.emit({
                            "status": "FAIL", "camera": "", "file": r3d_file.name,
                            "ltc_in": "", "ltc_out": "", "fps": str(e)
                        })
                    sig.progress.emit(i, len(r3d_files))

                # Write master CSV
                if rows:
                    ts_tag  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    master  = pf_path / f"master_ltc_{ts_tag}.csv"
                    master.parent.mkdir(parents=True, exist_ok=True)
                    with open(master, "w", newline="", encoding="utf-8") as f:
                        w = _csv.DictWriter(f, fieldnames=["camera","file","ltc_in","ltc_out","fps"])
                        w.writeheader()
                        w.writerows(rows)
                    sig.log.emit(f"📋  Master LTC CSV: {master}")

                sig.finished.emit(True)

            except Exception as e:
                sig.log.emit(f"❌  {e}")
                sig.finished.emit(False)

        self._thread = threading.Thread(target=work, daemon=True)
        self._thread.start()


# ── Main Window ────────────────────────────────────────────────────────────────
class FDVCWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FDVC  ·  ILM Digital Vehicle Control")
        self.setMinimumSize(900, 700)
        self.resize(1100, 780)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        title_bar = QWidget()
        title_bar.setFixedHeight(44)
        title_bar.setStyleSheet("background:#0a0a0a; border-bottom: 1px solid #1e1e1e;")
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(20, 0, 20, 0)

        title = QLabel("FDVC")
        title.setStyleSheet("color:#00ff9f; font-size:14px; font-weight:bold; letter-spacing:4px;")
        subtitle = QLabel("ILM · RED ARRAY · APPLE SILICON")
        subtitle.setStyleSheet("color:#333; font-size:10px; letter-spacing:3px;")

        tb_layout.addWidget(title)
        tb_layout.addWidget(subtitle)
        tb_layout.addStretch()

        self.clock = QLabel()
        self.clock.setStyleSheet("color:#333; font-size:10px; letter-spacing:1px;")
        tb_layout.addWidget(self.clock)

        layout.addWidget(title_bar)

        # Tabs
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(FTPTab(),      "FTP  PULL")
        tabs.addTab(TransferTab(), "TRANSFER")
        tabs.addTab(MetaTab(),     "METADATA")

        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.addWidget(tabs)
        layout.addWidget(container)

        # Clock update
        from PySide6.QtCore import QTimer
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(1000)
        self._tick()

    def _tick(self):
        self.clock.setText(datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))


# ── Launch ─────────────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("FDVC")
    app.setStyleSheet(STYLE)

    # Use dark palette as base
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#111111"))
    palette.setColor(QPalette.WindowText, QColor("#e0e0e0"))
    palette.setColor(QPalette.Base, QColor("#0a0a0a"))
    palette.setColor(QPalette.AlternateBase, QColor("#111111"))
    palette.setColor(QPalette.Text, QColor("#e0e0e0"))
    palette.setColor(QPalette.Button, QColor("#1a1a1a"))
    palette.setColor(QPalette.ButtonText, QColor("#ccc"))
    palette.setColor(QPalette.Highlight, QColor("#00ff9f"))
    palette.setColor(QPalette.HighlightedText, QColor("#000"))
    app.setPalette(palette)

    win = FDVCWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
