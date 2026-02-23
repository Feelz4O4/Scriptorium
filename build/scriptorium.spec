# scriptorium.spec
# PyInstaller spec for scriptorium GUI (Officina + Versicle)
#
# Build from repository root:
#   pyinstaller .\build\scriptorium.spec

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


_SPEC_FILE = Path(globals().get("__file__", Path.cwd() / "build" / "scriptorium.spec")).resolve()
BUILD_DIR = _SPEC_FILE.parent
REPO_ROOT = BUILD_DIR.parent
SCRIPT_DIR = REPO_ROOT / "Scriptorium"

SCRIPTORIUM_GUI = SCRIPT_DIR / "scriptorium_gui.py"
OFFICINA_SCRIPT = REPO_ROOT / "Officina" / "officina.py"
VERSICLE_SCRIPT = REPO_ROOT / "Versicle" / "versicle.py"
APP_ICON = SCRIPT_DIR / "logo.ico"

ctk_datas = collect_data_files("customtkinter")

a_datas = [
    # Bundle engine scripts beside the app at runtime.
    (str(OFFICINA_SCRIPT), "."),
    (str(VERSICLE_SCRIPT), "."),
    # customtkinter assets (themes/images).
    *ctk_datas,
]
if APP_ICON.exists():
    a_datas.append((str(APP_ICON), "."))

a = Analysis(
    [str(SCRIPTORIUM_GUI)],
    pathex=[
        str(SCRIPT_DIR),
        str(REPO_ROOT),
        str(REPO_ROOT / "Officina"),
        str(REPO_ROOT / "Versicle"),
    ],
    binaries=[],
    datas=a_datas,
    hiddenimports=[
        # Engine modules (bundled as data and also analyzed for dependencies)
        "officina",
        "versicle",
        # Officina Pillow imports used at runtime
        "PIL.Image",
        "PIL.ImageCms",
        "PIL.ImageColor",
        "PIL.ImageDraw",
        "PIL.ImageOps",
        "PIL._tkinter_finder",
        "PIL.PngImagePlugin",
        "PIL.JpegImagePlugin",
        "PIL.WebPImagePlugin",
        "pillow_heif",
        "multiprocessing.spawn",
        "multiprocessing.forkserver",
        *collect_submodules("customtkinter"),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="scriptorium",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(APP_ICON) if APP_ICON.exists() else None,
)
