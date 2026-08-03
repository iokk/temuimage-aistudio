"""Normalize generated ecommerce suite images for delivery."""

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps


TARGET_SIZE = (1600, 1600)
MAX_BYTES = 2 * 1024 * 1024
DPI = (72, 72)
JPEG_QUALITIES = tuple(range(95, 0, -5))


def normalize_suite_image(source, destination_dir, stem, prefer_png=False):
    """Write *source* as a 1600px square ecommerce-ready image.

    The source is contained within the fixed canvas so no source pixels are
    cropped. Images with transparency retain it when the PNG result is small
    enough; otherwise they are composited onto white before JPEG encoding.
    """
    image = _load_image(source)
    contains_alpha = _contains_alpha(image)
    normalized = _contain_and_pad(image, contains_alpha)

    encoded, image_format, extension = _encode(normalized, contains_alpha, prefer_png)
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f"{stem}.{extension}"
    path.write_bytes(encoded)

    return {
        "path": str(path),
        "format": image_format,
        "width": TARGET_SIZE[0],
        "height": TARGET_SIZE[1],
        "bytes": len(encoded),
        "dpi": DPI,
    }


def _load_image(source):
    if isinstance(source, Image.Image):
        image = source.copy()
    else:
        with Image.open(source) as opened:
            image = opened.copy()
    return ImageOps.exif_transpose(image)


def _contains_alpha(image):
    return image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    )


def _contain_and_pad(image, contains_alpha):
    image = image.convert("RGBA" if contains_alpha else "RGB")
    source_width, source_height = image.size
    if source_width <= 0 or source_height <= 0:
        raise ValueError("source image must have positive dimensions")

    scale = min(TARGET_SIZE[0] / source_width, TARGET_SIZE[1] / source_height)
    resized_size = (
        max(1, round(source_width * scale)),
        max(1, round(source_height * scale)),
    )
    resized = image.resize(resized_size, Image.Resampling.LANCZOS)
    offset = (
        (TARGET_SIZE[0] - resized_size[0]) // 2,
        (TARGET_SIZE[1] - resized_size[1]) // 2,
    )

    if contains_alpha:
        canvas = Image.new("RGBA", TARGET_SIZE, (0, 0, 0, 0))
        canvas.alpha_composite(resized, offset)
    else:
        canvas = Image.new("RGB", TARGET_SIZE, "white")
        canvas.paste(resized, offset)
    return canvas


def _encode(image, contains_alpha, prefer_png):
    if contains_alpha or prefer_png:
        png = _encode_png(image)
        if len(png) <= MAX_BYTES:
            return png, "PNG", "png"

    jpeg_image = _flatten_to_white(image) if contains_alpha else image.convert("RGB")
    for quality in JPEG_QUALITIES:
        jpeg = _encode_jpeg(jpeg_image, quality)
        if len(jpeg) <= MAX_BYTES:
            return jpeg, "JPEG", "jpg"

    raise ValueError("cannot encode image below the 2MB ecommerce limit")


def _encode_png(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True, compress_level=9, dpi=DPI)
    return buffer.getvalue()


def _encode_jpeg(image, quality):
    buffer = BytesIO()
    image.save(
        buffer,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
        dpi=DPI,
    )
    return buffer.getvalue()


def _flatten_to_white(image):
    flattened = Image.new("RGB", image.size, "white")
    flattened.paste(image, mask=image.getchannel("A"))
    return flattened
