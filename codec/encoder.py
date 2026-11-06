"""Энкодер: PNG -> байты собственного формата PIC1.

Пайплайн:
  1. Читаем PNG через Pillow (RGBA -> композит на белом, 16 бит -> 8, grayscale -> RGB).
  2. При besoin downscale (бинейно) до proc_w × proc_h.
  3. RGB -> YCbCr (или RGB напрямую в режиме mode=0).
  4. Chroma subsampling 4:2:0 (усреднение 2×2).
  5. Блоки 8×8, DCT-II (ортогнональная матрица).
  6. Квантование стандартными JPEG-матрицами × q_scale.
  7. Зигзаг + RLE + zlib.
  8. Заголовок PIC1 + сжатые данные.
"""

import io
import struct
import zlib

import numpy as np
from PIL import Image

from . import color as _color
from .errors import BadInput
from .format import (HEADER_SIZE, MODE_RGB, MODE_YCBCR_420,
                     _rle_encode, serialize_header)

# ---------------------------------------------------------------------------
# DCT-II матрица 8×8 (ортогнональная, M @ M.T = I)
# ---------------------------------------------------------------------------

_DCT_M: np.ndarray | None = None


def _dct_matrix() -> np.ndarray:
    global _DCT_M
    if _DCT_M is None:
        n = 8
        idx = np.arange(n)
        i = idx[:, None]
        j = idx[None, :]
        m = np.sqrt(2.0 / n) * np.cos((2 * j + 1) * i * np.pi / (2 * n))
        m[0, :] = 1.0 / np.sqrt(n)
        _DCT_M = m
    return _DCT_M


# ---------------------------------------------------------------------------
# JPEG-таблицы квантования (стандартные, приложение K ISO/IEC 10918-1)
# ---------------------------------------------------------------------------

_LUM_QUANT = np.array([
    16, 11, 10, 16, 24, 40, 51, 61,
    12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 52, 55, 61,
    12, 12, 14, 17, 22, 29, 52, 51,
    10, 10, 12, 17, 22, 29, 51, 51,
     8, 10, 12, 16, 22, 35, 45, 50,
     9, 11, 12, 18, 24, 35, 45, 50,
     8, 10, 13, 17, 26, 36, 48, 55,
], dtype=np.float64).reshape(8, 8)

_CHROM_QUANT = np.array([
    17, 18, 24, 47, 99, 99, 99, 99,
    18, 21, 26, 66, 99, 99, 99, 99,
    24, 26, 56, 99, 99, 99, 99, 99,
    47, 66, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
], dtype=np.float64).reshape(8, 8)

# ---------------------------------------------------------------------------
# Зигзаг-порядок для 8×8 (индексы строк и столбцов)
# ---------------------------------------------------------------------------

_ZIGZAG = np.array([
    0, 1, 8, 16, 9, 2, 3, 10,
    17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34,
    27, 20, 13, 6, 7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36,
    29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46,
    53, 60, 61, 54, 47, 55, 62, 63,
], dtype=np.int32).reshape(8, 8)

_ZIGZAG_ROWS = (_ZIGZAG // 8).ravel()
_ZIGZAG_COLS = (_ZIGZAG % 8).ravel()


# ---------------------------------------------------------------------------
# PNG I/O (вход только, Pillow — вспомогательное средство)
# ---------------------------------------------------------------------------

def _load_png_rgb(png_bytes: bytes) -> tuple[np.ndarray, tuple[int, int]]:
    """Читаем PNG из байтов.

    Возвращаем (H, W, 3) uint8 массив и (W, H) исходный размер.
    RGBA composited на белом, 16 бит -> 8, grayscale/palette -> RGB.
    Бросает BadInput на невалидный PNG.
    """
    buf = io.BytesIO(png_bytes)
    try:
        img = Image.open(buf)
        img.load()
    except Exception as exc:
        raise BadInput(f"invalid PNG: {exc}") from exc

    mode = img.mode
    if mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif mode == "LA":
        bg = Image.new("L", img.size, 255)
        bg.paste(img, mask=img.split()[1])
        img = bg.convert("RGB")
    elif mode == "P":
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif mode == "L":
        img = img.convert("RGB")
    elif mode in ("I;16", "I;16B", "I;16L"):
        img = img.convert("RGB")
    elif mode == "RGB":
        pass
    else:
        img = img.convert("RGB")

    if img.mode != "RGB":
        img = img.convert("RGB")

    arr = np.array(img)  # (H, W, 3) uint8
    size = img.size  # (W, H)
    return arr, size


def _save_png_rgb(arr_uint8: np.ndarray) -> bytes:
    """RGB uint8 (H, W, 3) -> PNG байты (8 бит)."""
    img = Image.fromarray(arr_uint8, "RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Работа с блоками 8×8
# ---------------------------------------------------------------------------

def _pad_to_multiple(arr: np.ndarray, multiple: int = 8) -> tuple[np.ndarray, int, int]:
    """Дополняем массив до размера, кратного 8, нулями.

    Возвращаем (padded, H, W) — исходные размеры до паддинга.
    """
    h, w = arr.shape[0], arr.shape[1]
    h2 = ((h + multiple - 1) // multiple) * multiple
    w2 = ((w + multiple - 1) // multiple) * multiple
    if arr.ndim == 2:
        padded = np.zeros((h2, w2), dtype=arr.dtype)
    else:
        padded = np.zeros((h2, w2, arr.shape[2]), dtype=arr.dtype)
    padded[:h, :w] = arr
    return padded, h, w


def _blocks_from_array(arr: np.ndarray) -> np.ndarray:
    """(H, W) -> (N, 8, 8) в порядке блоков (сначала по строкам, потом по столбцам).

    Требует, чтобы H и W были кратны 8.
    """
    h, w = arr.shape[0], arr.shape[1]
    hb, wb = h // 8, w // 8
    blocks = arr.reshape(hb, 8, wb, 8).transpose(0, 2, 1, 3).reshape(-1, 8, 8)
    return blocks


def _array_from_blocks(blocks: np.ndarray, h: int, w: int) -> np.ndarray:
    """(N, 8, 8) -> (H, W), обрезая паддинг до h×w."""
    hb = (h + 7) // 8
    wb = (w + 7) // 8
    arr = blocks.reshape(hb, wb, 8, 8).transpose(0, 2, 1, 3).reshape(hb * 8, wb * 8)
    return arr[:h, :w]


# ---------------------------------------------------------------------------
# Кодирование одного компонента
# ---------------------------------------------------------------------------

def _encode_component(blocks: np.ndarray, quant_matrix: np.ndarray,
                      q_scale: int) -> bytes:
    """DCT-II -> квантование -> зигзаг -> RLE -> zlib для одного компонента.

    blocks: (N, 8, 8) пространственный домен.
    Возвращает сжатые байты этого компонента.
    """
    dct_m = _dct_matrix()
    # DCT-II: coeffs = M @ block @ M.T  (векторно по всем блокам)
    coeffs = dct_m @ blocks @ dct_m.T  # (N, 8, 8)
    # Квантование: round(coeffs / (quant_matrix * q_scale))
    quantized = np.round(coeffs / (quant_matrix * q_scale)).astype(np.int32)
    # Зигзаг
    zigzag = quantized[:, _ZIGZAG_ROWS, _ZIGZAG_COLS]  # (N, 64)
    flat = zigzag.ravel()
    # RLE + zlib
    rle = _rle_encode(flat)
    return zlib.compress(rle)


def _encode_components(arrays: list[np.ndarray],
                       quant_matrices: list[np.ndarray],
                       q_scale: int) -> list[bytes]:
    """Кодирует список 2D массивов (каждый уже кратен 8 по осям).

    Возвращает список сжатых байт по одному на компонент.
    """
    parts = []
    for arr, qm in zip(arrays, quant_matrices):
        padded, h, w = _pad_to_multiple(arr)
        blocks = _blocks_from_array(padded)
        comp = _encode_component(blocks, qm, q_scale)
        parts.append(comp)
    return parts


# ---------------------------------------------------------------------------
# Режимы кодирования
# ---------------------------------------------------------------------------

def encode_image_rgb(arr: np.ndarray, q_scale: int) -> list[bytes]:
    """RGB (H, W, 3) uint8 -> список сжатых компонентов [R, G, B], mode=RGB."""
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    return _encode_components([r, g, b],
                              [_LUM_QUANT, _LUM_QUANT, _LUM_QUANT], q_scale)


def encode_image_ycbcr(arr: np.ndarray, q_scale: int) -> list[bytes]:
    """RGB (H, W, 3) uint8 -> список сжатых компонентов [Y, Cb, Cr], mode=YCbCr 4:2:0.

    Cb/Cr как 4:2:0 (полуразрешение). Если картинка меньше 2×2, chroma
    хранится как 1×1 (без потери общности).
    """
    ycbcr = _color.rgb_to_ycbcr(arr)
    y, cb, cr = _color.chroma_subsample_420(ycbcr)
    return _encode_components([y, cb, cr],
                              [_LUM_QUANT, _CHROM_QUANT, _CHROM_QUANT], q_scale)


# ---------------------------------------------------------------------------
# Сборка полного формата (без rate control)
# ---------------------------------------------------------------------------

def _pack_payload(mode: int, components: list[bytes]) -> bytes:
    """Упаковать список сжатых компонентов в payload: [len4][данные] × N."""
    out = bytearray()
    for comp in components:
        out.extend(struct.pack(">I", len(comp)))
        out.extend(comp)
    return bytes(out)


def _encode_full(png_bytes: bytes, q_scale: int, downscale_ratio: int,
                 mode: int) -> bytes:
    """Полное кодирование PIC1 для заданных параметров.

    Возвращает готовые байты формата (заголовок + payload).
    width/height в заголовке — исходные размеры до downscale.
    """
    from .format import MODE_YCBCR_420 as _MODE_YCBCR  # noqa: F811

    arr, (orig_w, orig_h) = _load_png_rgb(png_bytes)

    proc_w, proc_h = orig_w, orig_h
    if downscale_ratio > 1:
        proc_w = max(1, orig_w // downscale_ratio)
        proc_h = max(1, orig_h // downscale_ratio)
        img = Image.fromarray(arr, "RGB")
        img = img.resize((proc_w, proc_h), Image.Resampling.BILINEAR)
        arr = np.array(img)

    # Для крошечных картинок (меньше 2×2) YCbCr 4:2.0 не имеет смысла —
    # используем RGB напрямую.
    if mode == MODE_YCBCR_420 and (proc_h < 2 or proc_w < 2):
        mode = MODE_RGB

    if mode == MODE_RGB:
        components = encode_image_rgb(arr, q_scale)
    else:
        components = encode_image_ycbcr(arr, q_scale)

    payload = _pack_payload(mode, components)
    flags = 1 if downscale_ratio > 1 else 0
    header = serialize_header(orig_w, orig_h, mode, downscale_ratio,
                              q_scale, flags)
    return header + payload


def encode(png_bytes: bytes, max_bytes: int) -> bytes:
    """Закодировать PNG в PIC1 с уложением в max_bytes (через rate_control).

    Публичная точка входа, делегирует rate_control.encode.
    """
    from .rate_control import encode as _rc_encode
    return _rc_encode(png_bytes, max_bytes)
