"""
scriptorium_gui.py
Unified GUI for Officina (image converter) and Versicle (PNG metadata extractor).
Requires: customtkinter, Pillow  |  Optional: pillow-heif
"""
from __future__ import annotations

import multiprocessing
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

# ---------------------------------------------------------------------------
# Engine discovery (works from source tree and PyInstaller bundle)
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    if hasattr(sys, "_MEIPASS"):
        roots.append(Path(getattr(sys, "_MEIPASS")))
    roots.extend(
        [
            _SCRIPT_DIR,
            _SCRIPT_DIR.parent,
            _SCRIPT_DIR.parent / "Officina",
            _SCRIPT_DIR.parent / "Versicle",
        ]
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _resolve_engine_script(filename: str) -> Path | None:
    for root in _candidate_roots():
        candidate = root / filename
        if candidate.is_file():
            return candidate.resolve()
    return None


_OFFICINA_SCRIPT = _resolve_engine_script("officina.py")
_VERSICLE_SCRIPT = _resolve_engine_script("versicle.py")
_APP_ICON = _resolve_engine_script("logo.ico")
if _OFFICINA_SCRIPT and str(_OFFICINA_SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(_OFFICINA_SCRIPT.parent))
if _VERSICLE_SCRIPT and str(_VERSICLE_SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(_VERSICLE_SCRIPT.parent))

_versicle_import_error: str | None = None
iter_png_files = None
process_png = None
collect_png_files = None
try:
    import versicle as _vmod
    iter_png_files = _vmod.iter_png_files
    process_png = _vmod.process_png
    collect_png_files = _vmod.collect_png_files
except Exception as _exc:
    _versicle_import_error = str(_exc)

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

DARK_BG   = "#0f0f0f"
PANEL_BG  = "#1a1a1a"
ACCENT    = "#c87941"
ACCENT_DIM = "#8a5530"
TEXT      = "#e8e0d5"
TEXT_DIM  = "#7a7068"
SUCCESS   = "#4a9e6a"
FAIL      = "#9e4a4a"
HOVER     = "#dc8c54"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _section_label(parent: ctk.CTkBaseClass, text: str):
    ctk.CTkLabel(
        parent,
        text=text,
        font=("Courier New", 10, "bold"),
        text_color=TEXT_DIM,
        anchor="w",
    ).pack(fill="x")


def _mini_label(parent: ctk.CTkBaseClass, text: str, inline: bool = False):
    ctk.CTkLabel(
        parent,
        text=text,
        font=("Courier New", 10, "bold"),
        text_color=TEXT_DIM,
        anchor="w",
    ).pack(side="left" if inline else "top", anchor="w")


def _make_log_box(parent: ctk.CTkBaseClass, height: int = 160) -> ctk.CTkTextbox:
    box = ctk.CTkTextbox(
        parent,
        fg_color=PANEL_BG,
        text_color=TEXT_DIM,
        font=("Courier New", 11),
        height=height,
        border_width=0,
        wrap="word",
    )
    box.pack(fill="both", expand=True, pady=(4, 0))
    box.configure(state="disabled")
    box.tag_config("default", foreground=TEXT_DIM)
    box.tag_config("accent",  foreground=ACCENT)
    box.tag_config("success", foreground=SUCCESS)
    box.tag_config("fail",    foreground=FAIL)
    return box


def _log_write(box: ctk.CTkTextbox, text: str, level: str = "default"):
    tag = level if level in {"default", "accent", "success", "fail"} else "default"
    box.configure(state="normal")
    box.insert("end", text + "\n", tag)
    box.see("end")
    box.configure(state="disabled")


def _clear_log(box: ctk.CTkTextbox):
    box.configure(state="normal")
    box.delete("1.0", "end")
    box.configure(state="disabled")


def _build_officina_cmd(cfg: dict) -> list[str]:
    args = [
        "--input", cfg["input_dir"],
        "--preset", cfg["preset"],
        "--workers", str(cfg["workers"]),
        "--alpha-mode", cfg["alpha_mode"],
        "--background", cfg["background"] or "#ffffff",
        "--color-mode", cfg["color_mode"],
        "--output-format", cfg["output_format"],
        "--min-quality", str(cfg["min_quality"]),
    ]
    if cfg["quality_override"]:
        args += ["--quality", str(cfg["quality"])]
    if cfg["output_dir"]:
        args += ["--output", cfg["output_dir"]]
    if cfg["log_file"]:
        args += ["--log-file", cfg["log_file"]]
    if cfg["overwrite"]:
        args.append("--overwrite")
    if cfg["include_jpeg"]:
        args.append("--include-jpeg")
    if cfg["keep_exif"]:
        args.append("--keep-exif")
    if cfg["keep_icc"]:
        args.append("--keep-icc")
    if cfg["max_size_mb"]:
        args += ["--max-size-mb", cfg["max_size_mb"]]
    for ext in cfg["extensions"]:
        args += ["--ext", ext]
    if getattr(sys, "frozen", False):
        return [sys.executable, "--officina-cli", *args]
    return [sys.executable, str(_OFFICINA_SCRIPT), *args]


# ---------------------------------------------------------------------------
# Officina tab
# ---------------------------------------------------------------------------
class OfficinaTab(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, input_var: tk.StringVar, **kw):
        super().__init__(master, fg_color=DARK_BG, **kw)
        self._input_var = input_var   # shared with main window
        self._running   = False
        self._log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._build_ui()
        self._poll_log()

    # -- UI -----------------------------------------------------------------
    def _build_ui(self):
        content = ctk.CTkScrollableFrame(
            self,
            fg_color=DARK_BG,
            scrollbar_button_color=ACCENT_DIM,
            scrollbar_button_hover_color=ACCENT,
        )
        content.pack(fill="both", expand=True, padx=20, pady=12)

        # Output folder
        _section_label(content, "OUTPUT FOLDER")
        out_row = ctk.CTkFrame(content, fg_color="transparent")
        out_row.pack(fill="x", pady=(4, 12))
        self._output_var = tk.StringVar()
        ctk.CTkEntry(
            out_row, textvariable=self._output_var,
            placeholder_text="Default: <input>/<output-format>",
            fg_color=PANEL_BG, border_color="#333", text_color=TEXT,
            font=("Courier New", 12), height=36,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            out_row, text="Browse", width=90, height=36,
            fg_color=ACCENT_DIM, hover_color=ACCENT, text_color=TEXT,
            font=("Courier New", 12, "bold"), command=self._pick_output,
        ).pack(side="left")

        # Log file
        _section_label(content, "LOG FILE (OPTIONAL)")
        log_row = ctk.CTkFrame(content, fg_color="transparent")
        log_row.pack(fill="x", pady=(4, 12))
        self._log_file_var = tk.StringVar()
        ctk.CTkEntry(
            log_row, textvariable=self._log_file_var,
            placeholder_text="Default: output/officina_YYYYMMDD_HHMMSS.log",
            fg_color=PANEL_BG, border_color="#333", text_color=TEXT,
            font=("Courier New", 12), height=36,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            log_row, text="Browse", width=90, height=36,
            fg_color=ACCENT_DIM, hover_color=ACCENT, text_color=TEXT,
            font=("Courier New", 12, "bold"), command=self._pick_log_file,
        ).pack(side="left")

        # Settings row
        settings = ctk.CTkFrame(content, fg_color=PANEL_BG, corner_radius=8)
        settings.pack(fill="x", pady=(0, 12))
        si = ctk.CTkFrame(settings, fg_color="transparent")
        si.pack(fill="x", padx=16, pady=12)

        # Preset
        col1 = ctk.CTkFrame(si, fg_color="transparent")
        col1.pack(side="left", fill="x", expand=True)
        _mini_label(col1, "PRESET")
        self._preset_var = tk.StringVar(value="photo")
        ctk.CTkOptionMenu(
            col1, variable=self._preset_var, values=["photo", "web", "archive"],
            fg_color=DARK_BG, button_color=ACCENT_DIM, button_hover_color=ACCENT,
            text_color=TEXT, font=("Courier New", 12), width=120,
        ).pack(anchor="w", pady=(4, 0))

        # Quality
        col2 = ctk.CTkFrame(si, fg_color="transparent")
        col2.pack(side="left", fill="x", expand=True, padx=16)
        _mini_label(col2, "QUALITY")
        q_row = ctk.CTkFrame(col2, fg_color="transparent")
        q_row.pack(anchor="w", pady=(4, 0))
        self._quality_override_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            q_row, text="Override", variable=self._quality_override_var,
            fg_color=ACCENT, hover_color=ACCENT_DIM, text_color=TEXT,
            font=("Courier New", 11), command=self._set_quality_enabled,
        ).pack(side="left", padx=(0, 8))
        self._quality_var = tk.IntVar(value=90)
        self._quality_label = ctk.CTkLabel(
            q_row, text="90", font=("Courier New", 13, "bold"),
            text_color=ACCENT, width=30,
        )
        self._quality_label.pack(side="left")
        self._quality_slider = ctk.CTkSlider(
            q_row, from_=1, to=95, variable=self._quality_var, width=120,
            button_color=ACCENT, button_hover_color=ACCENT, progress_color=ACCENT_DIM,
            command=lambda v: self._quality_label.configure(text=str(int(v))),
        )
        self._quality_slider.pack(side="left", padx=(8, 0))
        self._set_quality_enabled()

        # Workers
        col3 = ctk.CTkFrame(si, fg_color="transparent")
        col3.pack(side="left", fill="x", expand=True)
        _mini_label(col3, "WORKERS")
        self._workers_var = tk.IntVar(value=8)
        w_row = ctk.CTkFrame(col3, fg_color="transparent")
        w_row.pack(anchor="w", pady=(4, 0))
        self._workers_label = ctk.CTkLabel(
            w_row, text="8", font=("Courier New", 13, "bold"),
            text_color=ACCENT, width=20,
        )
        self._workers_label.pack(side="left")
        ctk.CTkSlider(
            w_row, from_=1, to=16, variable=self._workers_var, width=100,
            button_color=ACCENT, button_hover_color=ACCENT, progress_color=ACCENT_DIM,
            command=lambda v: self._workers_label.configure(text=str(int(v))),
        ).pack(side="left", padx=(8, 0))

        # Checkboxes
        chk_style = dict(
            fg_color=ACCENT, hover_color=ACCENT_DIM, text_color=TEXT,
            font=("Courier New", 12), border_color="#555", checkmark_color=DARK_BG,
        )
        opts_frame = ctk.CTkFrame(content, fg_color=PANEL_BG, corner_radius=8)
        opts_frame.pack(fill="x", pady=(0, 12))
        oi = ctk.CTkFrame(opts_frame, fg_color="transparent")
        oi.pack(fill="x", padx=16, pady=10)

        self._overwrite_var     = tk.BooleanVar(value=False)
        self._include_jpeg_var  = tk.BooleanVar(value=False)
        self._keep_exif_var     = tk.BooleanVar(value=False)
        self._keep_icc_var      = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(oi, text="Overwrite existing",  variable=self._overwrite_var,    **chk_style).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(oi, text="Include JPEG input",  variable=self._include_jpeg_var, **chk_style).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(oi, text="Keep EXIF",           variable=self._keep_exif_var,    **chk_style).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(oi, text="Keep ICC profile",    variable=self._keep_icc_var,     **chk_style).pack(side="left")

        # Advanced row
        adv = ctk.CTkFrame(content, fg_color=PANEL_BG, corner_radius=8)
        adv.pack(fill="x", pady=(0, 12))
        ai = ctk.CTkFrame(adv, fg_color="transparent")
        ai.pack(fill="x", padx=16, pady=10)

        _mini_label(ai, "COLOR MODE", inline=True)
        self._color_mode_var = tk.StringVar(value="srgb")
        ctk.CTkOptionMenu(
            ai, variable=self._color_mode_var, values=["srgb", "preserve"],
            fg_color=DARK_BG, button_color=ACCENT_DIM, button_hover_color=ACCENT,
            text_color=TEXT, font=("Courier New", 12), width=120,
        ).pack(side="left", padx=(8, 18))

        _mini_label(ai, "FORMAT", inline=True)
        self._output_format_var = tk.StringVar(value="jpg")
        ctk.CTkOptionMenu(
            ai, variable=self._output_format_var, values=["jpg", "webp"],
            fg_color=DARK_BG, button_color=ACCENT_DIM, button_hover_color=ACCENT,
            text_color=TEXT, font=("Courier New", 12), width=110,
        ).pack(side="left", padx=(8, 18))

        _mini_label(ai, "ALPHA MODE", inline=True)
        self._alpha_var = tk.StringVar(value="white")
        ctk.CTkOptionMenu(
            ai, variable=self._alpha_var,
            values=["white", "black", "checker", "background", "error"],
            fg_color=DARK_BG, button_color=ACCENT_DIM, button_hover_color=ACCENT,
            text_color=TEXT, font=("Courier New", 12), width=120,
        ).pack(side="left", padx=(8, 18))

        _mini_label(ai, "BACKGROUND", inline=True)
        self._background_var = tk.StringVar(value="#ffffff")
        ctk.CTkEntry(
            ai, textvariable=self._background_var, width=95,
            fg_color=DARK_BG, border_color="#333", text_color=TEXT,
            font=("Courier New", 11), placeholder_text="#ffffff", height=30,
        ).pack(side="left", padx=(8, 18))

        _mini_label(ai, "EXT", inline=True)
        self._ext_var = tk.StringVar(value=".png,.heic,.heif")
        ctk.CTkEntry(
            ai, textvariable=self._ext_var, width=170,
            fg_color=DARK_BG, border_color="#333", text_color=TEXT,
            font=("Courier New", 11), placeholder_text=".png,.heic,.heif", height=30,
        ).pack(side="left", padx=(8, 0))

        # Limits row
        lim = ctk.CTkFrame(content, fg_color=PANEL_BG, corner_radius=8)
        lim.pack(fill="x", pady=(0, 12))
        li = ctk.CTkFrame(lim, fg_color="transparent")
        li.pack(fill="x", padx=16, pady=10)

        _mini_label(li, "MAX SIZE MB", inline=True)
        self._max_size_mb_var = tk.StringVar(value="")
        ctk.CTkEntry(
            li, textvariable=self._max_size_mb_var, width=90,
            fg_color=DARK_BG, border_color="#333", text_color=TEXT,
            font=("Courier New", 11), placeholder_text="e.g. 2.0", height=30,
        ).pack(side="left", padx=(8, 18))

        _mini_label(li, "MIN QUALITY", inline=True)
        self._min_quality_var = tk.IntVar(value=40)
        self._min_quality_label = ctk.CTkLabel(
            li, text="40", font=("Courier New", 13, "bold"),
            text_color=ACCENT, width=30,
        )
        self._min_quality_label.pack(side="left", padx=(8, 0))
        ctk.CTkSlider(
            li, from_=1, to=95, variable=self._min_quality_var, width=120,
            button_color=ACCENT, button_hover_color=ACCENT, progress_color=ACCENT_DIM,
            command=lambda v: self._min_quality_label.configure(text=str(int(v))),
        ).pack(side="left", padx=(8, 0))

        # Progress + status
        self._progress = ctk.CTkProgressBar(
            content, fg_color=PANEL_BG, progress_color=ACCENT, height=6, corner_radius=3,
        )
        self._progress.pack(fill="x", pady=(0, 4))
        self._progress.set(0)

        self._status_var = tk.StringVar(value="Ready.")
        ctk.CTkLabel(
            content, textvariable=self._status_var,
            font=("Courier New", 11), text_color=TEXT_DIM, anchor="w",
        ).pack(fill="x", pady=(0, 8))

        # Log
        _section_label(content, "LOG")
        self._log_box = _make_log_box(content)

        # Run button
        self._run_btn = ctk.CTkButton(
            content, text="RUN OFFICINA", height=48,
            fg_color=ACCENT, hover_color=HOVER, text_color="#ffffff",
            font=("Courier New", 15, "bold"), corner_radius=6,
            command=self._run,
        )
        self._run_btn.pack(fill="x", pady=(10, 0))

    # -- Helpers ------------------------------------------------------------
    def _set_quality_enabled(self):
        state = "normal" if self._quality_override_var.get() else "disabled"
        tc    = ACCENT   if self._quality_override_var.get() else TEXT_DIM
        self._quality_slider.configure(state=state)
        self._quality_label.configure(text_color=tc)

    def _pick_output(self):
        p = filedialog.askdirectory(title="Select output folder")
        if p:
            self._output_var.set(p)

    def _pick_log_file(self):
        p = filedialog.asksaveasfilename(
            title="Select log file", defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("All files", "*.*")],
        )
        if p:
            self._log_file_var.set(p)

    def _poll_log(self):
        try:
            while True:
                text, level = self._log_queue.get_nowait()
                _log_write(self._log_box, text, level)
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    def _collect_config(self) -> dict:
        ext_tokens = [e.strip() for e in self._ext_var.get().split(",") if e.strip()]
        return {
            "input_dir":        self._input_var.get().strip(),
            "output_dir":       self._output_var.get().strip(),
            "log_file":         self._log_file_var.get().strip(),
            "preset":           self._preset_var.get(),
            "quality_override": self._quality_override_var.get(),
            "quality":          int(self._quality_var.get()),
            "workers":          int(self._workers_var.get()),
            "overwrite":        self._overwrite_var.get(),
            "include_jpeg":     self._include_jpeg_var.get(),
            "keep_exif":        self._keep_exif_var.get(),
            "keep_icc":         self._keep_icc_var.get(),
            "color_mode":       self._color_mode_var.get(),
            "output_format":    self._output_format_var.get(),
            "alpha_mode":       self._alpha_var.get(),
            "background":       self._background_var.get().strip(),
            "extensions":       ext_tokens,
            "max_size_mb":      self._max_size_mb_var.get().strip(),
            "min_quality":      int(self._min_quality_var.get()),
        }

    # -- Run ----------------------------------------------------------------
    def _run(self):
        if self._running:
            return
        if _OFFICINA_SCRIPT is None:
            self._status_var.set("[!] officina.py not found.")
            _log_write(self._log_box, "Could not locate officina.py.", "fail")
            return
        cfg = self._collect_config()
        if not cfg["input_dir"] or not os.path.isdir(cfg["input_dir"]):
            self._status_var.set("[!] Please select a valid input folder.")
            return
        if cfg["max_size_mb"]:
            try:
                if float(cfg["max_size_mb"]) <= 0:
                    raise ValueError
            except ValueError:
                self._status_var.set("[!] MAX SIZE MB must be > 0.")
                return
        if not (1 <= cfg["min_quality"] <= 95):
            self._status_var.set("[!] MIN QUALITY must be 1–95.")
            return
        if cfg["quality_override"] and cfg["min_quality"] > cfg["quality"]:
            self._status_var.set("[!] MIN QUALITY must be <= QUALITY.")
            return

        self._running = True
        self._run_btn.configure(text="RUNNING...", state="disabled")
        self._progress.set(0)
        _clear_log(self._log_box)
        self._status_var.set("Running...")
        threading.Thread(target=self._worker, args=(cfg,), daemon=True).start()

    def _worker(self, cfg: dict):
        cmd = _build_officina_cmd(cfg)

        self._log_queue.put(("$ " + subprocess.list2cmdline(cmd), "accent"))
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            lines: list[str] = []
            if proc.stdout:
                for raw in proc.stdout:
                    line = raw.rstrip()
                    lines.append(line)
                    level = "default"
                    if "Converted " in line or "Done in " in line:
                        level = "success"
                    elif "Failed " in line or "ERROR" in line or "Traceback" in line:
                        level = "fail"
                    self._log_queue.put((line, level))
                    if line.startswith("["):
                        try:
                            part = line[1:line.index("]")]
                            cur, tot = part.split("/")
                            self.after(0, self._progress.set, int(cur) / int(tot))
                        except Exception:
                            pass
                    self.after(0, self._status_var.set, line[:90] or "Running...")
            proc.wait()
            final = next((l for l in reversed(lines) if l.startswith("Done")), None)
            if proc.returncode == 0:
                self.after(0, self._progress.set, 1.0)
                self.after(0, self._status_var.set, final or "Complete.")
            else:
                self.after(0, self._status_var.set, final or "[!] Finished with errors.")
        except Exception as exc:
            self._log_queue.put((f"ERROR: {exc}", "fail"))
            self.after(0, self._status_var.set, f"Error: {exc}")
        finally:
            self.after(0, self._done)

    def _done(self):
        self._running = False
        self._run_btn.configure(text="RUN OFFICINA", state="normal")

    # -- Startup diagnostics (called by main window after init) -------------
    def run_diagnostics(self, log_queue: "queue.Queue[tuple[str,str]]"):
        """Probe officina.py version + HEIF availability, push results to log."""
        if _OFFICINA_SCRIPT is None:
            log_queue.put(("officina.py not found.", "fail"))
            return
        script = str(_OFFICINA_SCRIPT)
        try:
            cmd = [sys.executable, "--officina-cli", "--version"] if getattr(
                sys, "frozen", False
            ) else [sys.executable, str(_OFFICINA_SCRIPT), "--version"]
            r = subprocess.run(
                cmd,
                capture_output=True, text=True, check=False,
            )
            out = (r.stdout or r.stderr).strip()
            if r.returncode == 0 and out:
                log_queue.put((out, "success"))
            else:
                log_queue.put(("Unable to read officina version.", "fail"))
        except Exception as exc:
            log_queue.put((f"Version check failed: {exc}", "fail"))
        try:
            import pillow_heif  # noqa: F401
            log_queue.put(("HEIF plugin: available", "success"))
        except Exception:
            log_queue.put(("HEIF plugin: not installed (pillow-heif optional)", "default"))


# ---------------------------------------------------------------------------
# Versicle tab
# ---------------------------------------------------------------------------
class VersicleTab(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, input_var: tk.StringVar, **kw):
        super().__init__(master, fg_color=DARK_BG, **kw)
        self._input_var  = input_var
        self._running    = False
        self._log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._build_ui()
        self._poll_log()

    def _build_ui(self):
        content = ctk.CTkScrollableFrame(
            self, fg_color=DARK_BG,
            scrollbar_button_color=ACCENT_DIM,
            scrollbar_button_hover_color=ACCENT,
        )
        content.pack(fill="both", expand=True, padx=20, pady=12)

        # Info note
        ctk.CTkLabel(
            content,
            text="Extracts PNG text metadata (parameters / postprocessing / extras) to same-name .md files.",
            font=("Courier New", 11),
            text_color=TEXT_DIM,
            anchor="w",
            wraplength=680,
        ).pack(fill="x", pady=(0, 12))

        # Options
        opts = ctk.CTkFrame(content, fg_color=PANEL_BG, corner_radius=8)
        opts.pack(fill="x", pady=(0, 12))
        oi = ctk.CTkFrame(opts, fg_color="transparent")
        oi.pack(fill="x", padx=16, pady=10)

        chk_style = dict(
            fg_color=ACCENT, hover_color=ACCENT_DIM, text_color=TEXT,
            font=("Courier New", 12), border_color="#555", checkmark_color=DARK_BG,
        )

        self._recursive_var   = tk.BooleanVar(value=False)
        self._all_tags_var    = tk.BooleanVar(value=False)
        self._write_mode_var  = tk.StringVar(value="overwrite")
        ctk.CTkCheckBox(oi, text="Recursive",        variable=self._recursive_var,  **chk_style).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(oi, text="All tags",         variable=self._all_tags_var,   **chk_style).pack(side="left", padx=(0, 20))

        mode_row = ctk.CTkFrame(content, fg_color=PANEL_BG, corner_radius=8)
        mode_row.pack(fill="x", pady=(0, 12))
        mi = ctk.CTkFrame(mode_row, fg_color="transparent")
        mi.pack(fill="x", padx=16, pady=10)
        _mini_label(mi, "WRITE MODE", inline=True)
        ctk.CTkRadioButton(
            mi,
            text="Overwrite existing .md",
            variable=self._write_mode_var,
            value="overwrite",
            **chk_style,
        ).pack(side="left", padx=(12, 20))
        ctk.CTkRadioButton(
            mi,
            text="Skip existing .md",
            variable=self._write_mode_var,
            value="skip",
            **chk_style,
        ).pack(side="left")

        # Workers
        w_frame = ctk.CTkFrame(content, fg_color=PANEL_BG, corner_radius=8)
        w_frame.pack(fill="x", pady=(0, 12))
        wi = ctk.CTkFrame(w_frame, fg_color="transparent")
        wi.pack(fill="x", padx=16, pady=10)
        _mini_label(wi, "WORKERS", inline=True)
        cpu_max = max(1, multiprocessing.cpu_count())
        self._workers_var = tk.IntVar(value=1)
        self._workers_label = ctk.CTkLabel(
            wi, text="1", font=("Courier New", 13, "bold"), text_color=ACCENT, width=20,
        )
        self._workers_label.pack(side="left", padx=(8, 0))
        ctk.CTkSlider(
            wi, from_=1, to=min(cpu_max, 16), variable=self._workers_var, width=120,
            button_color=ACCENT, button_hover_color=ACCENT, progress_color=ACCENT_DIM,
            command=lambda v: self._workers_label.configure(text=str(int(v))),
        ).pack(side="left", padx=(8, 0))

        # Progress + status
        self._progress = ctk.CTkProgressBar(
            content, fg_color=PANEL_BG, progress_color=ACCENT, height=6, corner_radius=3,
        )
        self._progress.pack(fill="x", pady=(0, 4))
        self._progress.set(0)

        self._status_var = tk.StringVar(value="Ready.")
        ctk.CTkLabel(
            content, textvariable=self._status_var,
            font=("Courier New", 11), text_color=TEXT_DIM, anchor="w",
        ).pack(fill="x", pady=(0, 8))

        # Log
        _section_label(content, "LOG")
        self._log_box = _make_log_box(content)

        # Buttons
        btn_row = ctk.CTkFrame(content, fg_color="transparent")
        btn_row.pack(fill="x", pady=(10, 0))

        self._run_btn = ctk.CTkButton(
            btn_row, text="RUN VERSICLE", height=48,
            fg_color=ACCENT, hover_color=HOVER, text_color="#ffffff",
            font=("Courier New", 15, "bold"), corner_radius=6,
            command=self._run,
        )
        self._run_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._stop_btn = ctk.CTkButton(
            btn_row, text="STOP", width=100, height=48,
            fg_color=FAIL, hover_color="#c05050", text_color="#ffffff",
            font=("Courier New", 15, "bold"), corner_radius=6,
            state="disabled", command=self._stop,
        )
        self._stop_btn.pack(side="left")

        if _versicle_import_error:
            self._run_btn.configure(state="disabled")
            self._status_var.set("[!] versicle.py could not be imported.")
            _log_write(self._log_box, f"Import error: {_versicle_import_error}", "fail")

    def _poll_log(self):
        try:
            while True:
                text, level = self._log_queue.get_nowait()
                _log_write(self._log_box, text, level)
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    def _run(self):
        if self._running or _versicle_import_error:
            return
        input_dir = self._input_var.get().strip()
        if not input_dir or not os.path.isdir(input_dir):
            self._status_var.set("[!] Please select a valid input folder.")
            return

        self._running = True
        self._run_btn.configure(text="RUNNING...", state="disabled")
        self._stop_btn.configure(state="normal")
        self._progress.set(0)
        _clear_log(self._log_box)
        self._status_var.set("Running...")

        opts = {
            "paths":      [input_dir],
            "recursive":  self._recursive_var.get(),
            "all_tags":   self._all_tags_var.get(),
            "overwrite":  self._write_mode_var.get() == "overwrite",
            "workers":    int(self._workers_var.get()),
        }
        threading.Thread(target=self._worker, args=(opts,), daemon=True).start()

    def _stop(self):
        self._running = False
        self._log_queue.put(("Stop requested – cancelling pending work...", "default"))

    def _worker(self, opts: dict):
        q = self._log_queue
        try:
            png_files = collect_png_files(opts["paths"], recursive=opts["recursive"])
            if not png_files:
                q.put(("No PNG files found.", "fail"))
                return

            total = len(png_files)
            q.put((f"Found {total} PNG file(s). Starting...", "accent"))

            wrote_n = skipped_n = failed_n = 0

            def _emit(md: str, status: str, error: str):
                nonlocal wrote_n, skipped_n, failed_n
                if status == "wrote":
                    wrote_n += 1; q.put((f"Wrote:   {md}", "success"))
                elif status == "skipped":
                    skipped_n += 1; q.put((f"Skipped: {md}", "default"))
                else:
                    failed_n += 1; q.put((f"Failed:  {md}  ({error})", "fail"))

            def _tick(done: int):
                self.after(0, self._progress.set, done / total)
                self.after(0, self._status_var.set, f"Processing {done}/{total}...")

            done_count = 0
            if opts["workers"] == 1 or total == 1:
                for png_path in png_files:
                    if not self._running:
                        break
                    md, status, error = process_png(str(png_path), opts["all_tags"], opts["overwrite"])
                    _emit(md, status, error)
                    done_count += 1
                    _tick(done_count)
            else:
                results: list[tuple[int, str, str, str]] = []
                executor = ProcessPoolExecutor(max_workers=opts["workers"])
                futures = {
                    executor.submit(process_png, str(p), opts["all_tags"], opts["overwrite"]): i
                    for i, p in enumerate(png_files)
                }
                try:
                    for fut in as_completed(futures):
                        idx = futures[fut]
                        if not self._running:
                            for pend in futures:
                                pend.cancel()
                            executor.shutdown(wait=False, cancel_futures=True)
                            break
                        try:
                            results.append((idx, *fut.result()))
                        except Exception as exc:
                            results.append((idx, str(png_files[idx]), "failed", str(exc)))
                        done_count += 1
                        _tick(done_count)
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)
                for _, md, status, error in sorted(results, key=lambda r: r[0]):
                    _emit(md, status, error)

            label = "Stopped" if not self._running else "Done"
            q.put((f"\n{label} — wrote: {wrote_n}  skipped: {skipped_n}  failed: {failed_n}", "accent"))
            self.after(0, self._progress.set, 1.0)
        except Exception as exc:
            q.put((f"Unexpected error: {exc}", "fail"))
        finally:
            self.after(0, self._done)

    def _done(self):
        self._running = False
        self._run_btn.configure(text="RUN VERSICLE", state="normal")
        self._stop_btn.configure(state="disabled")
        self._status_var.set("Finished.")


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class Scriptorium(ctk.CTk):
    VERSION = "1.1.0"

    def __init__(self):
        super().__init__()
        self.title(f"scriptorium.exe  v{self.VERSION}")
        if _APP_ICON is not None:
            try:
                self.iconbitmap(str(_APP_ICON))
            except Exception:
                pass
        self.geometry("800x960")
        self.minsize(740, 800)
        self.resizable(True, True)
        self.configure(fg_color=DARK_BG)

        self._log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._build_ui()
        self._poll_diag_log()
        self.after(80, self._run_diagnostics)

    def _build_ui(self):
        # ── Title bar ──────────────────────────────────────────────────────
        title_frame = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=0, height=56)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)
        ctk.CTkLabel(
            title_frame, text="SCRIPTORIUM",
            font=("Courier New", 22, "bold"), text_color=ACCENT,
        ).place(x=24, rely=0.5, anchor="w")
        ctk.CTkLabel(
            title_frame, text="Officina  ·  Versicle",
            font=("Courier New", 11), text_color=TEXT_DIM,
        ).place(relx=1.0, x=-24, rely=0.5, anchor="e")

        # ── Shared input folder ────────────────────────────────────────────
        inp_outer = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=0)
        inp_outer.pack(fill="x")
        inp_inner = ctk.CTkFrame(inp_outer, fg_color="transparent")
        inp_inner.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            inp_inner, text="INPUT FOLDER",
            font=("Courier New", 10, "bold"), text_color=TEXT_DIM,
        ).pack(anchor="w")

        inp_row = ctk.CTkFrame(inp_inner, fg_color="transparent")
        inp_row.pack(fill="x", pady=(4, 0))

        self._input_var = tk.StringVar()
        ctk.CTkEntry(
            inp_row, textvariable=self._input_var,
            placeholder_text="Select source folder — shared by both tools...",
            fg_color=DARK_BG, border_color=ACCENT_DIM, text_color=TEXT,
            font=("Courier New", 12), height=38,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            inp_row, text="Browse", width=90, height=38,
            fg_color=ACCENT_DIM, hover_color=ACCENT, text_color=TEXT,
            font=("Courier New", 12, "bold"), command=self._pick_input,
        ).pack(side="left")

        # ── Startup diagnostics log (collapsible-ish: just a small textbox) ─
        diag_frame = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=0)
        diag_frame.pack(fill="x")
        self._diag_box = ctk.CTkTextbox(
            diag_frame, fg_color=PANEL_BG, text_color=TEXT_DIM,
            font=("Courier New", 10), height=48, border_width=0, wrap="word",
        )
        self._diag_box.pack(fill="x", padx=20, pady=(2, 6))
        self._diag_box.configure(state="disabled")
        self._diag_box.tag_config("default", foreground=TEXT_DIM)
        self._diag_box.tag_config("success", foreground=SUCCESS)
        self._diag_box.tag_config("fail",    foreground=FAIL)
        self._diag_box.tag_config("accent",  foreground=ACCENT)

        # ── Tab view ──────────────────────────────────────────────────────
        self._tabs = ctk.CTkTabview(
            self,
            fg_color=DARK_BG,
            segmented_button_fg_color=PANEL_BG,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=HOVER,
            segmented_button_unselected_color=PANEL_BG,
            segmented_button_unselected_hover_color=ACCENT_DIM,
            text_color=TEXT,
            text_color_disabled=TEXT_DIM,
        )
        self._tabs.pack(fill="both", expand=True, padx=0, pady=0)

        self._tabs.add("Officina")
        self._tabs.add("Versicle")

        self._officina_tab = OfficinaTab(
            self._tabs.tab("Officina"), self._input_var,
        )
        self._officina_tab.pack(fill="both", expand=True)

        self._versicle_tab = VersicleTab(
            self._tabs.tab("Versicle"), self._input_var,
        )
        self._versicle_tab.pack(fill="both", expand=True)

    def _pick_input(self):
        p = filedialog.askdirectory(title="Select input folder")
        if p:
            self._input_var.set(p)

    # -- Diagnostics -------------------------------------------------------
    def _run_diagnostics(self):
        _log_write(self._diag_box, f"scriptorium v{self.VERSION}  |  Python {sys.version.split()[0]}", "accent")
        threading.Thread(
            target=self._officina_tab.run_diagnostics,
            args=(self._log_queue,), daemon=True,
        ).start()

    def _poll_diag_log(self):
        try:
            while True:
                text, level = self._log_queue.get_nowait()
                _log_write(self._diag_box, text, level)
        except queue.Empty:
            pass
        self.after(150, self._poll_diag_log)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def _run_officina_embedded(forwarded_args: list[str]) -> int:
    if _OFFICINA_SCRIPT is None:
        raise SystemExit("officina.py not found.")
    import officina as _officina

    original_argv = sys.argv[:]
    try:
        sys.argv = [str(_OFFICINA_SCRIPT), *forwarded_args]
        code = _officina.main()
        return code if isinstance(code, int) else 0
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    multiprocessing.freeze_support()   # required for PyInstaller --onefile
    if len(sys.argv) > 1 and sys.argv[1] == "--officina-cli":
        raise SystemExit(_run_officina_embedded(sys.argv[2:]))
    app = Scriptorium()
    app.mainloop()
