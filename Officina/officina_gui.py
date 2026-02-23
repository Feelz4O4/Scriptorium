import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import threading
import subprocess
import sys
import os
import queue

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

DARK_BG = "#0f0f0f"
PANEL_BG = "#1a1a1a"
ACCENT = "#c87941"
ACCENT_DIM = "#8a5530"
TEXT = "#e8e0d5"
TEXT_DIM = "#7a7068"
SUCCESS = "#4a9e6a"
FAIL = "#9e4a4a"


class OfficinaGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.app_name = "officina_gui"
        self.detected_version = "unknown"
        self.title(f"{self.app_name}.exe")
        self.geometry("760x900")
        self.minsize(720, 780)
        self.resizable(True, True)
        self.configure(fg_color=DARK_BG)

        self.log_queue = queue.Queue()
        self.running = False

        self._build_ui()
        self._poll_log()
        self.after(50, self._startup_diagnostics)

    def _build_ui(self):
        title_frame = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=0, height=56)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)

        ctk.CTkLabel(
            title_frame,
            text="Officina",
            font=("Courier New", 22, "bold"),
            text_color=ACCENT,
        ).place(x=24, rely=0.5, anchor="w")

        ctk.CTkLabel(
            title_frame,
            text="Images -> JPG/WEBP | 8 workers",
            font=("Courier New", 11),
            text_color=TEXT_DIM,
        ).place(relx=1.0, x=-24, rely=0.5, anchor="e")

        content = ctk.CTkScrollableFrame(
            self,
            fg_color=DARK_BG,
            scrollbar_button_color=ACCENT_DIM,
            scrollbar_button_hover_color=ACCENT,
        )
        content.pack(fill="both", expand=True, padx=20, pady=16)

        self._section_label(content, "INPUT FOLDER")
        input_row = ctk.CTkFrame(content, fg_color="transparent")
        input_row.pack(fill="x", pady=(4, 12))

        self.input_var = tk.StringVar()
        ctk.CTkEntry(
            input_row,
            textvariable=self.input_var,
            placeholder_text="Select source folder...",
            fg_color=PANEL_BG,
            border_color="#333",
            text_color=TEXT,
            font=("Courier New", 12),
            height=36,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            input_row,
            text="Browse",
            width=90,
            height=36,
            fg_color=ACCENT_DIM,
            hover_color=ACCENT,
            text_color=TEXT,
            font=("Courier New", 12, "bold"),
            command=self._pick_input,
        ).pack(side="left")

        self._section_label(content, "OUTPUT FOLDER")
        output_row = ctk.CTkFrame(content, fg_color="transparent")
        output_row.pack(fill="x", pady=(4, 12))

        self.output_var = tk.StringVar()
        ctk.CTkEntry(
            output_row,
            textvariable=self.output_var,
            placeholder_text="Default: <input>/<output-format>",
            fg_color=PANEL_BG,
            border_color="#333",
            text_color=TEXT,
            font=("Courier New", 12),
            height=36,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            output_row,
            text="Browse",
            width=90,
            height=36,
            fg_color=ACCENT_DIM,
            hover_color=ACCENT,
            text_color=TEXT,
            font=("Courier New", 12, "bold"),
            command=self._pick_output,
        ).pack(side="left")

        self._section_label(content, "LOG FILE (OPTIONAL)")
        log_row = ctk.CTkFrame(content, fg_color="transparent")
        log_row.pack(fill="x", pady=(4, 12))

        self.log_file_var = tk.StringVar()
        ctk.CTkEntry(
            log_row,
            textvariable=self.log_file_var,
            placeholder_text="Default: output/officina_YYYYMMDD_HHMMSS.log",
            fg_color=PANEL_BG,
            border_color="#333",
            text_color=TEXT,
            font=("Courier New", 12),
            height=36,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            log_row,
            text="Browse",
            width=90,
            height=36,
            fg_color=ACCENT_DIM,
            hover_color=ACCENT,
            text_color=TEXT,
            font=("Courier New", 12, "bold"),
            command=self._pick_log_file,
        ).pack(side="left")

        settings = ctk.CTkFrame(content, fg_color=PANEL_BG, corner_radius=8)
        settings.pack(fill="x", pady=(0, 12))

        settings_inner = ctk.CTkFrame(settings, fg_color="transparent")
        settings_inner.pack(fill="x", padx=16, pady=12)

        col1 = ctk.CTkFrame(settings_inner, fg_color="transparent")
        col1.pack(side="left", fill="x", expand=True)
        self._mini_label(col1, "PRESET")
        self.preset_var = tk.StringVar(value="photo")
        ctk.CTkOptionMenu(
            col1,
            variable=self.preset_var,
            values=["photo", "web", "archive"],
            fg_color=DARK_BG,
            button_color=ACCENT_DIM,
            button_hover_color=ACCENT,
            text_color=TEXT,
            font=("Courier New", 12),
            width=120,
        ).pack(anchor="w", pady=(4, 0))

        col2 = ctk.CTkFrame(settings_inner, fg_color="transparent")
        col2.pack(side="left", fill="x", expand=True, padx=16)
        self._mini_label(col2, "QUALITY")
        q_row = ctk.CTkFrame(col2, fg_color="transparent")
        q_row.pack(anchor="w", pady=(4, 0))
        self.quality_override_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            q_row,
            text="Override",
            variable=self.quality_override_var,
            fg_color=ACCENT,
            hover_color=ACCENT_DIM,
            text_color=TEXT,
            font=("Courier New", 11),
            command=self._set_quality_enabled,
        ).pack(side="left", padx=(0, 8))
        self.quality_var = tk.IntVar(value=90)
        self.quality_label = ctk.CTkLabel(
            q_row,
            text="90",
            font=("Courier New", 13, "bold"),
            text_color=ACCENT,
            width=30,
        )
        self.quality_label.pack(side="left")
        self.quality_slider = ctk.CTkSlider(
            q_row,
            from_=1,
            to=95,
            variable=self.quality_var,
            width=120,
            button_color=ACCENT,
            button_hover_color=ACCENT,
            progress_color=ACCENT_DIM,
            command=lambda v: self.quality_label.configure(text=str(int(v))),
        )
        self.quality_slider.pack(side="left", padx=(8, 0))
        self._set_quality_enabled()

        col3 = ctk.CTkFrame(settings_inner, fg_color="transparent")
        col3.pack(side="left", fill="x", expand=True)
        self._mini_label(col3, "WORKERS")
        self.workers_var = tk.IntVar(value=8)
        w_row = ctk.CTkFrame(col3, fg_color="transparent")
        w_row.pack(anchor="w", pady=(4, 0))
        self.workers_label = ctk.CTkLabel(
            w_row,
            text="8",
            font=("Courier New", 13, "bold"),
            text_color=ACCENT,
            width=20,
        )
        self.workers_label.pack(side="left")
        ctk.CTkSlider(
            w_row,
            from_=1,
            to=16,
            variable=self.workers_var,
            width=100,
            button_color=ACCENT,
            button_hover_color=ACCENT,
            progress_color=ACCENT_DIM,
            command=lambda v: self.workers_label.configure(text=str(int(v))),
        ).pack(side="left", padx=(8, 0))

        options = ctk.CTkFrame(content, fg_color=PANEL_BG, corner_radius=8)
        options.pack(fill="x", pady=(0, 12))
        opts_inner = ctk.CTkFrame(options, fg_color="transparent")
        opts_inner.pack(fill="x", padx=16, pady=10)

        self.overwrite_var = tk.BooleanVar(value=False)
        self.include_jpeg_var = tk.BooleanVar(value=False)
        self.keep_exif_var = tk.BooleanVar(value=False)
        self.keep_icc_var = tk.BooleanVar(value=False)

        check_style = dict(
            fg_color=ACCENT,
            hover_color=ACCENT_DIM,
            text_color=TEXT,
            font=("Courier New", 12),
            border_color="#555",
            checkmark_color=DARK_BG,
        )

        ctk.CTkCheckBox(
            opts_inner,
            text="Overwrite existing",
            variable=self.overwrite_var,
            **check_style,
        ).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(
            opts_inner,
            text="Include JPEG input",
            variable=self.include_jpeg_var,
            **check_style,
        ).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(
            opts_inner,
            text="Keep EXIF",
            variable=self.keep_exif_var,
            **check_style,
        ).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(
            opts_inner,
            text="Keep ICC profile",
            variable=self.keep_icc_var,
            **check_style,
        ).pack(side="left")

        advanced = ctk.CTkFrame(content, fg_color=PANEL_BG, corner_radius=8)
        advanced.pack(fill="x", pady=(0, 12))
        adv_inner = ctk.CTkFrame(advanced, fg_color="transparent")
        adv_inner.pack(fill="x", padx=16, pady=10)

        self._mini_label(adv_inner, "COLOR MODE", inline=True)
        self.color_mode_var = tk.StringVar(value="srgb")
        ctk.CTkOptionMenu(
            adv_inner,
            variable=self.color_mode_var,
            values=["srgb", "preserve"],
            fg_color=DARK_BG,
            button_color=ACCENT_DIM,
            button_hover_color=ACCENT,
            text_color=TEXT,
            font=("Courier New", 12),
            width=120,
        ).pack(side="left", padx=(8, 18))

        self._mini_label(adv_inner, "FORMAT", inline=True)
        self.output_format_var = tk.StringVar(value="jpg")
        ctk.CTkOptionMenu(
            adv_inner,
            variable=self.output_format_var,
            values=["jpg", "webp"],
            fg_color=DARK_BG,
            button_color=ACCENT_DIM,
            button_hover_color=ACCENT,
            text_color=TEXT,
            font=("Courier New", 12),
            width=110,
        ).pack(side="left", padx=(8, 18))

        self._mini_label(adv_inner, "ALPHA MODE", inline=True)
        self.alpha_var = tk.StringVar(value="white")
        ctk.CTkOptionMenu(
            adv_inner,
            variable=self.alpha_var,
            values=["white", "black", "checker", "background", "error"],
            fg_color=DARK_BG,
            button_color=ACCENT_DIM,
            button_hover_color=ACCENT,
            text_color=TEXT,
            font=("Courier New", 12),
            width=120,
        ).pack(side="left", padx=(8, 18))

        self._mini_label(adv_inner, "BACKGROUND", inline=True)
        self.background_var = tk.StringVar(value="#ffffff")
        ctk.CTkEntry(
            adv_inner,
            textvariable=self.background_var,
            width=95,
            fg_color=DARK_BG,
            border_color="#333",
            text_color=TEXT,
            font=("Courier New", 11),
            placeholder_text="#ffffff",
            height=30,
        ).pack(side="left", padx=(8, 18))

        self._mini_label(adv_inner, "EXT", inline=True)
        self.ext_var = tk.StringVar(value=".png,.heic,.heif")
        ctk.CTkEntry(
            adv_inner,
            textvariable=self.ext_var,
            width=170,
            fg_color=DARK_BG,
            border_color="#333",
            text_color=TEXT,
            font=("Courier New", 11),
            placeholder_text=".png,.heic,.heif",
            height=30,
        ).pack(side="left", padx=(8, 0))

        limits = ctk.CTkFrame(content, fg_color=PANEL_BG, corner_radius=8)
        limits.pack(fill="x", pady=(0, 12))
        limits_inner = ctk.CTkFrame(limits, fg_color="transparent")
        limits_inner.pack(fill="x", padx=16, pady=10)

        self._mini_label(limits_inner, "MAX SIZE MB", inline=True)
        self.max_size_mb_var = tk.StringVar(value="")
        ctk.CTkEntry(
            limits_inner,
            textvariable=self.max_size_mb_var,
            width=90,
            fg_color=DARK_BG,
            border_color="#333",
            text_color=TEXT,
            font=("Courier New", 11),
            placeholder_text="e.g. 2.0",
            height=30,
        ).pack(side="left", padx=(8, 18))

        self._mini_label(limits_inner, "MIN QUALITY", inline=True)
        self.min_quality_var = tk.IntVar(value=40)
        self.min_quality_label = ctk.CTkLabel(
            limits_inner,
            text="40",
            font=("Courier New", 13, "bold"),
            text_color=ACCENT,
            width=30,
        )
        self.min_quality_label.pack(side="left", padx=(8, 0))
        ctk.CTkSlider(
            limits_inner,
            from_=1,
            to=95,
            variable=self.min_quality_var,
            width=120,
            button_color=ACCENT,
            button_hover_color=ACCENT,
            progress_color=ACCENT_DIM,
            command=lambda v: self.min_quality_label.configure(text=str(int(v))),
        ).pack(side="left", padx=(8, 0))

        self.progress = ctk.CTkProgressBar(
            content,
            fg_color=PANEL_BG,
            progress_color=ACCENT,
            height=6,
            corner_radius=3,
        )
        self.progress.pack(fill="x", pady=(0, 4))
        self.progress.set(0)

        self.status_var = tk.StringVar(value="Ready.")
        ctk.CTkLabel(
            content,
            textvariable=self.status_var,
            font=("Courier New", 11),
            text_color=TEXT_DIM,
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        self._section_label(content, "LOG")
        self.log_box = ctk.CTkTextbox(
            content,
            fg_color=PANEL_BG,
            text_color=TEXT_DIM,
            font=("Courier New", 11),
            height=120,
            border_width=0,
            wrap="word",
        )
        self.log_box.pack(fill="x", pady=(4, 12))
        self.log_box.configure(state="disabled")
        self.log_box.tag_config("default", foreground=TEXT_DIM)
        self.log_box.tag_config("accent", foreground=ACCENT)
        self.log_box.tag_config("success", foreground=SUCCESS)
        self.log_box.tag_config("fail", foreground=FAIL)

        self.run_btn = ctk.CTkButton(
            content,
            text="RUN Officina",
            height=48,
            fg_color=ACCENT,
            hover_color="#dc8c54",
            text_color="#ffffff",
            font=("Courier New", 15, "bold"),
            corner_radius=6,
            command=self._run,
        )
        self.run_btn.pack(fill="x", pady=(6, 0))

    def _section_label(self, parent, text):
        ctk.CTkLabel(
            parent,
            text=text,
            font=("Courier New", 10, "bold"),
            text_color=TEXT_DIM,
            anchor="w",
        ).pack(fill="x")

    def _mini_label(self, parent, text, inline=False):
        ctk.CTkLabel(
            parent,
            text=text,
            font=("Courier New", 10, "bold"),
            text_color=TEXT_DIM,
            anchor="w",
        ).pack(side="left" if inline else "top", anchor="w")

    def _set_quality_enabled(self):
        state = "normal" if self.quality_override_var.get() else "disabled"
        text_color = ACCENT if self.quality_override_var.get() else TEXT_DIM
        self.quality_slider.configure(state=state)
        self.quality_label.configure(text_color=text_color)

    def _pick_input(self):
        path = filedialog.askdirectory(title="Select input folder")
        if path:
            self.input_var.set(path)

    def _pick_output(self):
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self.output_var.set(path)

    def _pick_log_file(self):
        path = filedialog.asksaveasfilename(
            title="Select log file",
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("All files", "*.*")],
        )
        if path:
            self.log_file_var.set(path)

    def _log(self, text, level="default"):
        self.log_queue.put((text, level))

    def _set_window_title(self):
        self.title(f"{self.app_name}.exe v{self.detected_version}")

    def _startup_diagnostics(self):
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "officina.py")
        self._log("Startup diagnostics:", "accent")
        self._log(f"Python: {sys.executable}", "default")
        try:
            version_proc = subprocess.run(
                [sys.executable, script, "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
            version_text = (version_proc.stdout or version_proc.stderr).strip()
            if version_proc.returncode == 0 and version_text:
                # Example: "officina.py v1.2.0 (heif=enabled)"
                parts = version_text.split()
                for token in parts:
                    if token.startswith("v"):
                        self.detected_version = token.lstrip("v")
                        break
                self._log(version_text, "success")
            else:
                self._log("Unable to read officina version.", "fail")
            self._set_window_title()
        except Exception as exc:
            self._log(f"Version check failed: {exc}", "fail")
            self._set_window_title()

        try:
            import pillow_heif  # noqa: F401

            self._log("HEIF plugin: available", "success")
        except Exception:
            self._log("HEIF plugin: missing (install pillow-heif for .heic/.heif)", "fail")

    def _poll_log(self):
        try:
            while True:
                text, level = self.log_queue.get_nowait()
                tag = level if level in {"default", "accent", "success", "fail"} else "default"
                self.log_box.configure(state="normal")
                self.log_box.insert("end", text + "\n", tag)
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    def _collect_run_config(self):
        input_dir = self.input_var.get().strip()
        output_dir = self.output_var.get().strip()
        log_file = self.log_file_var.get().strip()
        ext_tokens = [e.strip() for e in self.ext_var.get().split(",") if e.strip()]
        return {
            "input_dir": input_dir,
            "output_dir": output_dir,
            "log_file": log_file,
            "preset": self.preset_var.get(),
            "quality_override": self.quality_override_var.get(),
            "quality": int(self.quality_var.get()),
            "workers": int(self.workers_var.get()),
            "overwrite": self.overwrite_var.get(),
            "include_jpeg": self.include_jpeg_var.get(),
            "keep_exif": self.keep_exif_var.get(),
            "keep_icc": self.keep_icc_var.get(),
            "color_mode": self.color_mode_var.get(),
            "output_format": self.output_format_var.get(),
            "alpha_mode": self.alpha_var.get(),
            "background": self.background_var.get().strip(),
            "extensions": ext_tokens,
            "max_size_mb": self.max_size_mb_var.get().strip(),
            "min_quality": int(self.min_quality_var.get()),
        }

    def _run(self):
        if self.running:
            return

        config = self._collect_run_config()
        if not config["input_dir"] or not os.path.isdir(config["input_dir"]):
            self.status_var.set("[!] Please select a valid input folder.")
            return
        if config["max_size_mb"]:
            try:
                max_size = float(config["max_size_mb"])
                if max_size <= 0:
                    raise ValueError
            except ValueError:
                self.status_var.set("[!] MAX SIZE MB must be a number greater than 0.")
                return
        if config["min_quality"] < 1 or config["min_quality"] > 95:
            self.status_var.set("[!] MIN QUALITY must be between 1 and 95.")
            return
        if config["quality_override"] and config["min_quality"] > config["quality"]:
            self.status_var.set("[!] MIN QUALITY must be <= QUALITY.")
            return

        self.running = True
        self.run_btn.configure(text="RUNNING...", state="disabled")
        self.progress.set(0)
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.status_var.set("Running...")

        threading.Thread(target=self._worker, args=(config,), daemon=True).start()

    def _worker(self, config):
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "officina.py")
        cmd = [
            sys.executable,
            script,
            "--input",
            config["input_dir"],
            "--preset",
            config["preset"],
            "--workers",
            str(config["workers"]),
            "--alpha-mode",
            config["alpha_mode"],
            "--background",
            config["background"] or "#ffffff",
            "--color-mode",
            config["color_mode"],
            "--output-format",
            config["output_format"],
            "--min-quality",
            str(config["min_quality"]),
        ]
        if config["quality_override"]:
            cmd += ["--quality", str(config["quality"])]
        if config["output_dir"]:
            cmd += ["--output", config["output_dir"]]
        if config["log_file"]:
            cmd += ["--log-file", config["log_file"]]
        if config["overwrite"]:
            cmd.append("--overwrite")
        if config["include_jpeg"]:
            cmd.append("--include-jpeg")
        if config["keep_exif"]:
            cmd.append("--keep-exif")
        if config["keep_icc"]:
            cmd.append("--keep-icc")
        if config["max_size_mb"]:
            cmd += ["--max-size-mb", config["max_size_mb"]]
        for ext in config["extensions"]:
            cmd += ["--ext", ext]

        self._log("$ " + subprocess.list2cmdline(cmd), "accent")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            lines = []
            if proc.stdout is not None:
                for line in proc.stdout:
                    line = line.rstrip()
                    lines.append(line)
                    level = "default"
                    if "Converted " in line or "Done in " in line:
                        level = "success"
                    elif "Failed " in line or "ERROR" in line or "Traceback" in line:
                        level = "fail"
                    self._log(line, level)
                    if line.startswith("["):
                        try:
                            part = line[1:line.index("]")]
                            cur, tot = part.split("/")
                            self.after(0, self.progress.set, int(cur) / int(tot))
                        except Exception:
                            pass
                    self.after(0, self.status_var.set, line[:90] if line else "Running...")

            proc.wait()
            final = next((l for l in reversed(lines) if l.startswith("Done")), None)
            if proc.returncode == 0:
                self.after(0, self.progress.set, 1.0)
                self.after(0, self.status_var.set, final or "Complete")
            else:
                self.after(0, self.status_var.set, final or "[!] Finished with errors")
        except Exception as exc:
            self._log(f"ERROR: {exc}", "fail")
            self.after(0, self.status_var.set, f"Error: {exc}")
        finally:
            self.after(0, self._done)

    def _done(self):
        self.running = False
        self.run_btn.configure(text="RUN Officina", state="normal")


if __name__ == "__main__":
    app = OfficinaGUI()
    app.mainloop()
