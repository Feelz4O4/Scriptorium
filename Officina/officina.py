import argparse
import io
import logging
import os
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from multiprocessing import Pool

from PIL import Image, ImageCms, ImageColor, ImageDraw, ImageOps, UnidentifiedImageError

try:
    from pillow_heif import register_heif_opener

    HEIF_PLUGIN_AVAILABLE = True
except ImportError:
    register_heif_opener = None
    HEIF_PLUGIN_AVAILABLE = False

DEFAULT_WORKERS = 8
DEFAULT_QUALITY = 90
VERSION = "1.1.0"
PRESETS = {
    "web": {"quality": 80, "subsampling": 2, "progressive": True, "optimize": True},
    "photo": {"quality": 90, "subsampling": 1, "progressive": True, "optimize": True},
    "archive": {
        "quality": 95,
        "subsampling": 0,
        "progressive": False,
        "optimize": True,
    },
}
HEIF_EXTENSIONS = {".heic", ".heif"}
JPEG_EXTENSIONS = {".jpg", ".jpeg"}
OUTPUT_FORMATS = ("jpg", "webp")
WORKER_HEIF_READY = False


@dataclass(frozen=True)
class ConversionTask:
    src: str
    dst: str
    quality: int
    overwrite: bool
    progressive: bool
    subsampling: int
    optimize: bool
    color_mode: str
    keep_exif: bool
    keep_icc: bool
    alpha_mode: str
    background_rgb: tuple[int, int, int]
    min_quality: int
    max_size_bytes: int | None
    output_format: str


def initialize_worker(enable_heif):
    global WORKER_HEIF_READY
    WORKER_HEIF_READY = False
    if not enable_heif:
        WORKER_HEIF_READY = True
        return
    if not HEIF_PLUGIN_AVAILABLE:
        return
    register_heif_opener()
    WORKER_HEIF_READY = True


def normalize_extensions(extensions):
    result = set()
    for ext in extensions:
        normalized = ext.strip().lower()
        if not normalized:
            continue
        if not normalized.startswith("."):
            normalized = "." + normalized
        result.add(normalized)
    return result


def checker_background(size, tile=16):
    bg = Image.new("RGB", size, (235, 235, 235))
    draw = ImageDraw.Draw(bg)
    for y in range(0, size[1], tile):
        for x in range(0, size[0], tile):
            if ((x // tile) + (y // tile)) % 2:
                draw.rectangle(
                    (x, y, min(x + tile, size[0]), min(y + tile, size[1])),
                    fill=(200, 200, 200),
                )
    return bg


def flatten_alpha(img, alpha_mode, background_rgb):
    rgba = img.convert("RGBA")
    if alpha_mode == "error":
        raise ValueError("image has transparency but alpha mode is 'error'")
    if alpha_mode == "white":
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
    elif alpha_mode == "black":
        bg = Image.new("RGB", rgba.size, (0, 0, 0))
    elif alpha_mode == "background":
        bg = Image.new("RGB", rgba.size, background_rgb)
    else:
        bg = checker_background(rgba.size)
    bg.paste(rgba, mask=rgba.getchannel("A"))
    return bg


def image_has_alpha(img):
    if img.mode in ("RGBA", "LA"):
        return True
    if img.mode == "P" and "transparency" in img.info:
        return True
    return False


def srgb_profile_bytes():
    try:
        return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    except Exception:
        return None


def prepare_for_jpeg(img, color_mode, alpha_mode, background_rgb):
    source_icc = img.info.get("icc_profile")
    exif_blob = img.info.get("exif")
    working = ImageOps.exif_transpose(img)

    if image_has_alpha(working):
        working = flatten_alpha(working, alpha_mode, background_rgb)
    else:
        working = working.convert("RGB")

    if color_mode == "preserve":
        return working, source_icc, exif_blob

    if source_icc:
        try:
            input_profile = ImageCms.ImageCmsProfile(io.BytesIO(source_icc))
            output_profile = ImageCms.createProfile("sRGB")
            converted = ImageCms.profileToProfile(
                working,
                input_profile,
                output_profile,
                outputMode="RGB",
            )
            return converted, converted.info.get("icc_profile") or srgb_profile_bytes(), exif_blob
        except Exception:
            return working, srgb_profile_bytes(), exif_blob

    return working, srgb_profile_bytes(), exif_blob


def prepare_for_webp(img, color_mode):
    source_icc = img.info.get("icc_profile")
    exif_blob = img.info.get("exif")
    working = ImageOps.exif_transpose(img)

    if color_mode == "preserve":
        return working, source_icc, exif_blob

    if source_icc:
        try:
            input_profile = ImageCms.ImageCmsProfile(io.BytesIO(source_icc))
            output_profile = ImageCms.createProfile("sRGB")
            output_mode = "RGBA" if "A" in working.getbands() else "RGB"
            converted = ImageCms.profileToProfile(
                working,
                input_profile,
                output_profile,
                outputMode=output_mode,
            )
            return converted, converted.info.get("icc_profile") or srgb_profile_bytes(), exif_blob
        except Exception:
            return working, srgb_profile_bytes(), exif_blob

    return working, srgb_profile_bytes(), exif_blob


def parse_args():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Convert images in parallel.")
    parser.add_argument(
        "--version",
        action="version",
        version=(
            f"%(prog)s v{VERSION} "
            f"(heif={'enabled' if HEIF_PLUGIN_AVAILABLE else 'disabled'})"
        ),
    )
    parser.add_argument(
        "--input",
        default=script_dir,
        help="Input folder to scan for files (default: script directory).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help='Output folder for converted files (default: "<input>/<output-format>").',
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of worker processes (default: {DEFAULT_WORKERS}).",
    )
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS.keys()),
        default="photo",
        help="Quality preset for output images (default: photo).",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=None,
        help=f"Output quality 1-95 (default from preset, photo={DEFAULT_QUALITY}).",
    )
    parser.add_argument(
        "--min-quality",
        type=int,
        default=40,
        help="Minimum JPEG quality when size-capping (1-95).",
    )
    parser.add_argument(
        "--max-size-mb",
        type=float,
        default=None,
        help="If set, reduce JPEG quality to keep output under this size (MB).",
    )
    recursive_group = parser.add_mutually_exclusive_group()
    recursive_group.add_argument(
        "--recursive",
        dest="recursive",
        action="store_true",
        help="Scan input folders recursively (default behavior).",
    )
    recursive_group.add_argument(
        "--non-recursive",
        dest="recursive",
        action="store_false",
        help="Scan only the top level of the input folder.",
    )
    parser.set_defaults(recursive=True)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files, ignoring mtime checks.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List planned conversions without writing output files.",
    )
    parser.add_argument(
        "--include-jpeg",
        action="store_true",
        help="Allow processing .jpg/.jpeg input files.",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Path to a log file (default: timestamped file in output folder).",
    )
    parser.add_argument(
        "--ext",
        action="append",
        default=None,
        help="Input extension to include. Repeatable (e.g. --ext .png --ext .heic).",
    )
    parser.add_argument(
        "--color-mode",
        choices=("srgb", "preserve"),
        default="srgb",
        help="Color handling mode (default: srgb).",
    )
    parser.add_argument(
        "--keep-exif",
        action="store_true",
        help="Preserve EXIF metadata in output file.",
    )
    parser.add_argument(
        "--keep-icc",
        action="store_true",
        help="Embed ICC profile in output file.",
    )
    parser.add_argument(
        "--alpha-mode",
        choices=("white", "black", "checker", "background", "error"),
        default="white",
        help="How to flatten transparent pixels for JPG output (default: white).",
    )
    parser.add_argument(
        "--background",
        default="#ffffff",
        help="Background color used when --alpha-mode background (e.g. #ffffff).",
    )
    parser.add_argument(
        "--output-format",
        choices=OUTPUT_FORMATS,
        default="jpg",
        help="Output image format (default: jpg).",
    )
    return parser.parse_args()


def build_tasks(
    input_dir,
    output_dir,
    allowed_extensions,
    include_jpeg,
    output_format,
    recursive=True,
    create_dirs=True,
):
    tasks = []
    skipped_jpeg = 0
    abs_input = os.path.abspath(input_dir)
    abs_output = os.path.abspath(output_dir)
    output_is_inside_input = os.path.commonpath([abs_input, abs_output]) == abs_input

    if recursive:
        walk_iter = os.walk(abs_input, topdown=True)
    else:
        top_files = []
        for name in os.listdir(abs_input):
            full = os.path.join(abs_input, name)
            if os.path.isfile(full):
                top_files.append(name)
        walk_iter = [(abs_input, [], top_files)]

    for root, dirs, files in walk_iter:
        if output_is_inside_input:
            dirs[:] = [
                d
                for d in dirs
                if os.path.abspath(os.path.join(root, d)) != abs_output
            ]
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in allowed_extensions:
                continue
            if ext in JPEG_EXTENSIONS and not include_jpeg:
                skipped_jpeg += 1
                continue
            src = os.path.join(root, filename)
            if not os.path.isfile(src):
                continue
            target_name = os.path.splitext(filename)[0] + f".{output_format}"
            rel_dir = os.path.relpath(root, abs_input)
            dst_dir = abs_output if rel_dir == "." else os.path.join(abs_output, rel_dir)
            if create_dirs:
                os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, target_name)
            tasks.append((src, dst))
    return tasks, skipped_jpeg


def should_skip_existing(src: str, dst: str, overwrite: bool) -> bool:
    if overwrite or not os.path.exists(dst):
        return False
    src_mtime = os.path.getmtime(src)
    dst_mtime = os.path.getmtime(dst)
    return dst_mtime >= src_mtime


def convert_one(task: ConversionTask):
    src = task.src
    dst = task.dst
    quality = task.quality
    overwrite = task.overwrite
    progressive = task.progressive
    subsampling = task.subsampling
    optimize = task.optimize
    color_mode = task.color_mode
    keep_exif = task.keep_exif
    keep_icc = task.keep_icc
    alpha_mode = task.alpha_mode
    background_rgb = task.background_rgb
    min_quality = task.min_quality
    max_size_bytes = task.max_size_bytes
    output_format = task.output_format
    try:
        pil_format = "JPEG" if output_format == "jpg" else "WEBP"
        src_ext = os.path.splitext(src)[1].lower()
        if src_ext in HEIF_EXTENSIONS and not WORKER_HEIF_READY:
            return ("failed", f"Failed {src} (HEIF support is not initialized)", None)
        if should_skip_existing(src, dst, overwrite):
            return ("skipped", f"Skipped {src} (destination is up to date)", None)
        with Image.open(src) as img:
            if output_format == "webp":
                working_img, output_icc, exif_blob = prepare_for_webp(img, color_mode)
                save_kwargs = {
                    "quality": quality,
                    "method": 6,
                }
            else:
                working_img, output_icc, exif_blob = prepare_for_jpeg(
                    img, color_mode, alpha_mode, background_rgb
                )
                save_kwargs = {
                    "quality": quality,
                    "optimize": optimize,
                    "progressive": progressive,
                    "subsampling": subsampling,
                }
            if keep_exif and exif_blob:
                save_kwargs["exif"] = exif_blob
            if keep_icc and output_icc:
                save_kwargs["icc_profile"] = output_icc

            chosen_quality = quality
            downsized = False
            warning = None
            chosen_bytes = None
            if max_size_bytes is not None:
                low = max(1, min_quality)
                high = quality
                best_quality = None
                best_bytes = None
                while low <= high:
                    mid = (low + high) // 2
                    test_kwargs = dict(save_kwargs)
                    test_kwargs["quality"] = mid
                    buffer = io.BytesIO()
                    working_img.save(buffer, pil_format, **test_kwargs)
                    size = buffer.tell()
                    if size <= max_size_bytes:
                        best_quality = mid
                        best_bytes = buffer.getvalue()
                        low = mid + 1
                    else:
                        high = mid - 1
                if best_bytes is not None:
                    chosen_quality = best_quality
                    chosen_bytes = best_bytes
                    downsized = chosen_quality < quality
                else:
                    fallback_kwargs = dict(save_kwargs)
                    fallback_kwargs["quality"] = min_quality
                    buffer = io.BytesIO()
                    working_img.save(buffer, pil_format, **fallback_kwargs)
                    chosen_quality = min_quality
                    chosen_bytes = buffer.getvalue()
                    downsized = True
                    warning = "exceeds max size at min quality; kept min-quality result"

            if chosen_bytes is not None:
                with open(dst, "wb") as handle:
                    handle.write(chosen_bytes)
            else:
                working_img.save(dst, pil_format, **save_kwargs)

            message = f"Converted {src} -> .{output_format}"
            if downsized:
                message += f" (quality={chosen_quality})"
            if warning:
                message += f" [{warning}]"
        return ("converted", message, None)
    except UnidentifiedImageError as exc:
        detail = traceback.format_exc()
        return ("failed", f"Failed {src} (unidentified image: {exc})", detail)
    except ValueError as exc:
        detail = traceback.format_exc()
        return ("failed", f"Failed {src} (value error: {exc})", detail)
    except OSError as exc:
        detail = traceback.format_exc()
        return ("failed", f"Failed {src} (OS error: {exc})", detail)
    except Exception as exc:
        detail = traceback.format_exc()
        return ("failed", f"Failed {src} ({type(exc).__name__}: {exc})", detail)


def main():
    args = parse_args()
    input_dir = os.path.abspath(args.input)
    if not os.path.isdir(input_dir):
        raise SystemExit(f"Input folder not found: {input_dir}")
    output_dir = os.path.abspath(args.output or os.path.join(input_dir, args.output_format))
    workers = max(1, args.workers)
    preset = PRESETS[args.preset]
    # We intentionally cap at 95: Pillow treats >95 as special high-quality
    # mode with diminishing returns and much larger files.
    quality = max(1, min(95, args.quality if args.quality is not None else preset["quality"]))
    min_quality = max(1, min(95, args.min_quality))
    if min_quality > quality:
        raise SystemExit("--min-quality must be less than or equal to --quality.")
    if args.max_size_mb is not None and args.max_size_mb <= 0:
        raise SystemExit("--max-size-mb must be greater than 0.")
    max_size_bytes = int(args.max_size_mb * 1024 * 1024) if args.max_size_mb else None
    try:
        background_rgba = ImageColor.getcolor(args.background, "RGBA")
    except ValueError as exc:
        raise SystemExit(f"Invalid --background color: {args.background}") from exc
    background_rgb = background_rgba[:3]
    if not args.dry_run:
        os.makedirs(output_dir, exist_ok=True)

    configured_extensions = normalize_extensions(args.ext or [".png", ".heic", ".heif"])
    if args.include_jpeg:
        configured_extensions |= JPEG_EXTENSIONS
    heif_requested = bool(configured_extensions & HEIF_EXTENSIONS)
    if heif_requested and not HEIF_PLUGIN_AVAILABLE:
        configured_extensions -= HEIF_EXTENSIONS
    if not configured_extensions:
        print("No usable input extensions configured.")
        return

    log_file = None
    logger = logging.getLogger("officina")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    if args.dry_run:
        logger.addHandler(logging.NullHandler())
    else:
        if args.log_file:
            log_file = os.path.abspath(args.log_file)
        else:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(output_dir, f"officina_{args.output_format}_{stamp}.log")
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(file_handler)
    logger.propagate = False
    logger.info(
        (
            "Run started | input=%s output=%s workers=%d preset=%s quality=%d overwrite=%s "
            "extensions=%s color_mode=%s keep_exif=%s keep_icc=%s alpha_mode=%s "
            "include_jpeg=%s recursive=%s dry_run=%s min_quality=%d max_size_mb=%s background=%s output_format=%s"
        ),
        input_dir,
        output_dir,
        workers,
        args.preset,
        quality,
        args.overwrite,
        sorted(configured_extensions),
        args.color_mode,
        args.keep_exif,
        args.keep_icc,
        args.alpha_mode,
        args.include_jpeg,
        args.recursive,
        args.dry_run,
        min_quality,
        args.max_size_mb,
        args.background,
        args.output_format,
    )
    if heif_requested and not HEIF_PLUGIN_AVAILABLE:
        warning = (
            "HEIF extensions requested but pillow-heif is not installed; HEIF files will be skipped."
        )
        print(warning)
        logger.warning(warning)

    tasks, skipped_jpeg = build_tasks(
        input_dir,
        output_dir,
        configured_extensions,
        args.include_jpeg,
        args.output_format,
        recursive=args.recursive,
        create_dirs=not args.dry_run,
    )
    if not tasks:
        print("No matching files found.")
        logger.info("No matching files found for extensions: %s", sorted(configured_extensions))
        if log_file:
            print(f"Log file: {log_file}")
        return

    if args.dry_run:
        started = time.time()
        would_convert = 0
        would_skip = 0
        total = len(tasks)
        for index, (src, dst) in enumerate(tasks, start=1):
            if should_skip_existing(src, dst, args.overwrite):
                would_skip += 1
                print(f"[{index}/{total}] Would skip {src} (destination is up to date)")
                continue
            would_convert += 1
            print(f"[{index}/{total}] Would convert {src} -> {dst}")
        elapsed = time.time() - started
        summary = (
            f"Dry run done in {elapsed:.2f}s | total: {total}, would_convert: {would_convert}, "
            f"would_skip: {would_skip}, skipped_jpeg: {skipped_jpeg}, workers: {workers}, "
            f"format: {args.output_format}"
        )
        print(summary)
        logger.info(summary)
        return

    started = time.time()
    converted = 0
    skipped = 0
    failed = 0
    downsized = 0
    total = len(tasks)
    queued_tasks = [
        ConversionTask(
            src=src,
            dst=dst,
            quality=quality,
            overwrite=args.overwrite,
            progressive=preset["progressive"],
            subsampling=preset["subsampling"],
            optimize=preset["optimize"],
            color_mode=args.color_mode,
            keep_exif=args.keep_exif,
            keep_icc=args.keep_icc,
            alpha_mode=args.alpha_mode,
            background_rgb=background_rgb,
            min_quality=min_quality,
            max_size_bytes=max_size_bytes,
            output_format=args.output_format,
        )
        for src, dst in tasks
    ]

    with Pool(
        processes=workers,
        initializer=initialize_worker,
        initargs=(heif_requested,),
    ) as pool:
        for index, (status, message, detail) in enumerate(
            pool.imap_unordered(convert_one, queued_tasks), start=1
        ):
            if status == "converted":
                converted += 1
                if "(quality=" in message:
                    downsized += 1
            elif status == "skipped":
                skipped += 1
            else:
                failed += 1
                logger.error(message)
                if detail:
                    logger.error("Traceback for failure:\n%s", detail)
            print(f"[{index}/{total}] {message}")

    elapsed = time.time() - started
    summary = (
        f"Done in {elapsed:.2f}s | total: {total}, converted: {converted}, "
        f"skipped: {skipped}, skipped_jpeg: {skipped_jpeg}, downsized: {downsized}, "
        f"failed: {failed}, workers: {workers}, format: {args.output_format}"
    )
    print(summary)
    logger.info(summary)
    if log_file:
        print(f"Log file: {log_file}")


if __name__ == "__main__":
    main()
