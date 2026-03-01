#!/usr/bin/env python3
"""
GUI front-end for versicle.py
Requires: customtkinter  (pip install customtkinter)
"""

from __future__ import annotations

import multiprocessing
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk


_WORKER_IMPORT_ERROR = None
iter_png_files = None
process_png = None
collect_png_files = None
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

try:
    import versicle as _mod
    iter_png_files = _mod.iter_png_files
    process_png = _mod.process_png
    collect_png_files = _mod.collect_png_files
except Exception as exc:  # pragma: no cover
    _WORKER_IMPORT_ERROR = str(exc)


ctk.set_appearance_mode("dark")
try:
    ctk.set_default_color_theme("orange")
except Exception:  # pragma: no cover
    # Fall back to a guaranteed built-in theme.
    ctk.set_default_color_theme("blue")

FONT_MONO = ("Courier New", 12)
FONT_LABEL = ("Courier New", 12)
FONT_HEAD = ("Courier New", 13, "bold")

BG_PANEL = "#0d0800"
BG_LOG = "#080500"
ACCENT = "#ff6600"
FG_WROTE = "#ff8c00"
FG_SKIPPED = "#cc4400"
FG_FAILED = "#ff2200"
FG_INFO = "#cc5500"


class PathListFrame(ctk.CTkFrame):
    """Displays a list of selected paths with add/remove controls."""

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._paths: list[str] = []

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=6, pady=(6, 2))

        ctk.CTkLabel(top, text="Input paths", font=FONT_HEAD).pack(side="left")
        ctk.CTkButton(
            top,
            text="+ Folder",
            width=80,
            command=self._add_folder,
            fg_color=ACCENT,
            hover_color="#3a7fc1",
        ).pack(side="right", padx=(4, 0))
        ctk.CTkButton(
            top,
            text="+ File",
            width=72,
            command=self._add_file,
            fg_color=ACCENT,
            hover_color="#3a7fc1",
        ).pack(side="right", padx=(4, 0))

        self._listbox = tk.Listbox(
            self,
            bg=BG_LOG,
            fg=FG_INFO,
            selectbackground=ACCENT,
            selectforeground="white",
            relief="flat",
            borderwidth=0,
            font=FONT_MONO,
            height=6,
            activestyle="none",
        )
        self._listbox.pack(fill="both", expand=True, padx=6, pady=2)

        bot = ctk.CTkFrame(self, fg_color="transparent")
        bot.pack(fill="x", padx=6, pady=(2, 6))
        ctk.CTkButton(
            bot,
            text="Remove selected",
            width=130,
            fg_color="#3a3a3a",
            hover_color="#555",
            command=self._remove_selected,
        ).pack(side="left")
        ctk.CTkButton(
            bot,
            text="Clear all",
            width=90,
            fg_color="#3a3a3a",
            hover_color="#555",
            command=self._clear,
        ).pack(side="left", padx=6)

    def _add_folder(self):
        p = filedialog.askdirectory(title="Select folder")
        if p and p not in self._paths:
            self._paths.append(p)
            self._listbox.insert("end", p)

    def _add_file(self):
        files = filedialog.askopenfilenames(
            title="Select PNG file(s)", filetypes=[("PNG files", "*.png *.PNG")]
        )
        for p in files:
            if p not in self._paths:
                self._paths.append(p)
                self._listbox.insert("end", p)

    def _remove_selected(self):
        for idx in reversed(self._listbox.curselection()):
            self._paths.pop(idx)
            self._listbox.delete(idx)

    def _clear(self):
        self._paths.clear()
        self._listbox.delete(0, "end")

    @property
    def paths(self) -> list[str]:
        return list(self._paths)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Versicle")
        self.geometry("780x660")
        self.minsize(640, 520)
        self.configure(fg_color=BG_PANEL)

        self._running = False
        self._thread: threading.Thread | None = None
        self._log_queue: queue.Queue[tuple[str, str]] = queue.Queue()

        self._build_ui()
        self._poll_log()

        if _WORKER_IMPORT_ERROR:
            self._btn_run.configure(state="disabled")
            self._status_label.configure(text="Worker import failed.")
            self._log_write(f"Failed to import worker: {_WORKER_IMPORT_ERROR}", "failed")
            messagebox.showerror(
                "Worker Import Error",
                "Could not load versicle.py.\n\n"
                f"Details:\n{_WORKER_IMPORT_ERROR}",
            )

    def _build_ui(self):
        title_bar = ctk.CTkFrame(self, fg_color="#111111", corner_radius=0)
        title_bar.pack(fill="x")
        ctk.CTkLabel(
            title_bar,
            text="PNG METADATA -> MARKDOWN",
            font=("Courier New", 14, "bold"),
            text_color=ACCENT,
        ).pack(pady=10, padx=16, anchor="w")

        self._path_frame = PathListFrame(self, fg_color="#222222", corner_radius=8)
        self._path_frame.pack(fill="x", padx=14, pady=(10, 6))

        opts = ctk.CTkFrame(self, fg_color="#222222", corner_radius=8)
        opts.pack(fill="x", padx=14, pady=6)
        ctk.CTkLabel(opts, text="Options", font=FONT_HEAD).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(8, 4)
        )

        self._var_recursive = ctk.BooleanVar(value=False)
        self._var_all_tags = ctk.BooleanVar(value=False)
        self._var_skip_exist = ctk.BooleanVar(value=False)

        def _chk(parent, text, var, row, col):
            ctk.CTkCheckBox(
                parent,
                text=text,
                variable=var,
                font=FONT_LABEL,
                checkbox_width=18,
                checkbox_height=18,
                border_color=ACCENT,
                checkmark_color="white",
                fg_color=ACCENT,
            ).grid(row=row, column=col, sticky="w", padx=(14, 20), pady=6)

        _chk(opts, "Recursive", self._var_recursive, 1, 0)
        _chk(opts, "All tags", self._var_all_tags, 1, 1)
        _chk(opts, "Skip existing .md", self._var_skip_exist, 1, 2)

        ctk.CTkLabel(opts, text="Workers:", font=FONT_LABEL).grid(
            row=1, column=3, sticky="e", padx=(20, 4)
        )
        cpu_max = max(1, multiprocessing.cpu_count())
        self._workers_var = ctk.IntVar(value=1)
        self._workers_spin = ctk.CTkOptionMenu(
            opts,
            values=[str(i) for i in range(1, cpu_max + 1)],
            variable=ctk.StringVar(value="1"),
            width=70,
            fg_color="#333",
            button_color=ACCENT,
            button_hover_color="#3a7fc1",
            command=lambda v: self._workers_var.set(int(v)),
        )
        self._workers_spin.grid(row=1, column=4, sticky="w", padx=(0, 14), pady=6)
        opts.columnconfigure(5, weight=1)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(4, 0))

        self._btn_run = ctk.CTkButton(
            btn_row,
            text="Run",
            font=("Segoe UI", 13, "bold"),
            fg_color=ACCENT,
            hover_color="#3a7fc1",
            height=38,
            command=self._start,
        )
        self._btn_run.pack(side="left")

        self._btn_stop = ctk.CTkButton(
            btn_row,
            text="Stop",
            font=("Segoe UI", 13, "bold"),
            fg_color="#6b2121",
            hover_color="#8b3131",
            height=38,
            command=self._stop,
            state="disabled",
        )
        self._btn_stop.pack(side="left", padx=8)

        self._status_label = ctk.CTkLabel(
            btn_row, text="", font=FONT_LABEL, text_color=FG_INFO
        )
        self._status_label.pack(side="left", padx=8)

        self._progress = ctk.CTkProgressBar(
            self,
            fg_color="#222222",
            progress_color=ACCENT,
            height=6,
            corner_radius=3,
        )
        self._progress.pack(fill="x", padx=14, pady=(8, 2))
        self._progress.set(0)

        ctk.CTkLabel(self, text="Log", font=FONT_HEAD, anchor="w").pack(
            fill="x", padx=16, pady=(10, 2)
        )

        log_frame = ctk.CTkFrame(self, fg_color=BG_LOG, corner_radius=8)
        log_frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self._log = tk.Text(
            log_frame,
            bg=BG_LOG,
            fg=FG_INFO,
            font=FONT_MONO,
            relief="flat",
            borderwidth=0,
            wrap="word",
            state="disabled",
            selectbackground=ACCENT,
        )
        self._log.tag_config("wrote", foreground=FG_WROTE)
        self._log.tag_config("skipped", foreground=FG_SKIPPED)
        self._log.tag_config("failed", foreground=FG_FAILED)
        self._log.tag_config("info", foreground=FG_INFO)
        self._log.tag_config("head", foreground=ACCENT)

        scrollbar = ctk.CTkScrollbar(log_frame, command=self._log.yview)
        self._log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", pady=4)
        self._log.pack(side="left", fill="both", expand=True, padx=6, pady=6)

        ctk.CTkButton(
            self,
            text="Clear log",
            width=90,
            height=26,
            fg_color="#2a2a2a",
            hover_color="#444",
            command=self._clear_log,
        ).pack(anchor="e", padx=14, pady=(0, 6))

    def _log_write(self, text: str, tag: str = "info"):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n", tag)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _poll_log(self):
        try:
            while True:
                msg, tag = self._log_queue.get_nowait()
                self._log_write(msg, tag)
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    def _start(self):
        if _WORKER_IMPORT_ERROR:
            self._log_write("Cannot start: worker module failed to import.", "failed")
            return

        paths = self._path_frame.paths
        if not paths:
            self._log_write("No input paths selected.", "failed")
            return

        self._running = True
        self._btn_run.configure(state="disabled")
        self._btn_stop.configure(state="normal")
        self._status_label.configure(text="Running...")
        self._progress.set(0)

        opts = {
            "recursive": self._var_recursive.get(),
            "all_tags": self._var_all_tags.get(),
            "overwrite": not self._var_skip_exist.get(),
            "workers": self._workers_var.get(),
            "paths": paths,
        }

        self._thread = threading.Thread(target=self._run_worker, args=(opts,), daemon=True)
        self._thread.start()

    def _stop(self):
        self._running = False
        self._log_queue.put(("Stop requested - cancelling pending work...", "skipped"))

    def _run_worker(self, opts: dict):
        q = self._log_queue
        try:
            paths = opts["paths"]
            all_tags = opts["all_tags"]
            overwrite = opts["overwrite"]
            workers = opts["workers"]
            recursive = opts["recursive"]

            png_files = collect_png_files(paths, recursive=recursive)

            if not png_files:
                q.put(("No PNG files found.", "failed"))
                return

            total = len(png_files)
            q.put((f"Found {total} PNG file(s). Starting...\n", "head"))

            wrote_n = skipped_n = failed_n = 0
            done_count = 0

            def _tick(done: int):
                self.after(0, self._progress.set, done / total)
                self.after(
                    0,
                    lambda d=done: self._status_label.configure(text=f"Processing {d}/{total}..."),
                )

            def _emit(md_or_png: str, status: str, error: str):
                nonlocal wrote_n, skipped_n, failed_n
                if status == "wrote":
                    wrote_n += 1
                    q.put((f"Wrote:   {md_or_png}", "wrote"))
                elif status == "skipped":
                    skipped_n += 1
                    q.put((f"Skipped: {md_or_png}", "skipped"))
                else:
                    failed_n += 1
                    q.put((f"Failed:  {md_or_png} ({error})", "failed"))

            if workers == 1 or len(png_files) == 1:
                for png_path in png_files:
                    if not self._running:
                        break
                    md_or_png, status, error = process_png(
                        str(png_path), all_tags, overwrite
                    )
                    _emit(md_or_png, status, error)
                    done_count += 1
                    _tick(done_count)
            else:
                from concurrent.futures import ProcessPoolExecutor, as_completed

                results: list[tuple[int, str, str, str]] = []
                executor = ProcessPoolExecutor(max_workers=workers)
                futures = {
                    executor.submit(process_png, str(p), all_tags, overwrite): i
                    for i, p in enumerate(png_files)
                }
                try:
                    for fut in as_completed(futures):
                        idx = futures[fut]
                        if not self._running:
                            for pending in futures:
                                pending.cancel()
                            executor.shutdown(wait=False, cancel_futures=True)
                            break
                        try:
                            results.append((idx, *fut.result()))
                        except Exception as exc:  # pragma: no cover
                            results.append((idx, str(png_files[idx]), "failed", str(exc)))
                        done_count += 1
                        _tick(done_count)
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)

                for _, md_or_png, status, error in sorted(results, key=lambda r: r[0]):
                    _emit(md_or_png, status, error)

            done_label = "Stopped" if not self._running else "Done"
            q.put(
                (
                    f"\n{done_label} - wrote: {wrote_n}  skipped: {skipped_n}  failed: {failed_n}",
                    "head",
                )
            )
            if self._running:
                self.after(0, self._progress.set, 1.0)
        except Exception as exc:  # pragma: no cover
            q.put((f"Unexpected error: {exc}", "failed"))
        finally:
            self.after(0, self._finish)

    def _finish(self):
        self._running = False
        self._btn_run.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        self._status_label.configure(text="Finished.")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = App()
    app.mainloop()
