"""Декодер: байты PIC1 -> PNG 8 бит.

Обратный пайплайн:
  1. parse_header -> W×H, mode, downscale_ratio, q_scale.
  2. zlib декомпрессия -> RLE декодирование -> де-зигзаг.
  3. Де-квантование (JPEG-матрицы × q_scale).
  4. IDCT -> пространственный домен.
  5. YCbCr -> RGB (или RGB напрямую).
  6. Chroma upsample 4:2:0 (nearest-neighbor 2×2).
  7. При downscale_ratio > 1 — бинейный апскейл до исходных W×H.
  8. Сохранение PNG 8 бит в bytes через Pillow.

Stateless: не требует оригинала, не хранит состояние между вызовами.
"""

import io
import struct
import zlib

import numpy as np
from PIL import Image

from . import color as _color
from .errors import CorruptFormat
from .format import (HEADER_SIZE, MODE_RGB, MODE_YCBCR_420, _rle_decode,
                     parse_header)

# ---------------------------------------------------------------------------
# DCT-II матрица 8×8 (ортогнональная, IDCT = M.T @ coeffs @ M)
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
# JPEG-таблицы квантования (те же, что в энкодере)
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
# Зигзаг-порядок для 8×8
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
# Декодирование одного компонента
# ---------------------------------------------------------------------------

def _decode_component(data: bytes, num_blocks: int, quant_matrix: np.ndarray,
                      q_scale: int, h: int, w: int) -> np.ndarray:
    """zlib -> RLE -> де-зигзаг -> де-квантование -> IDCT -> массив h×w."""
    rle = zlib.decompress(data)
    values = _rle_decode(rle, num_blocks * 64)

    # Дополняем нулями если поток был обрезан (защита от битых данных)
    expected = num_blocks * 64
    if len(values) < expected:
        values.extend([0] * (expected - len(values)))
    values = values[:expected]

    arr = np.array(values, dtype=np.float64).reshape(num_blocks, 64)

    # Де-зигзаг: значения идут в зигзаг-порядке, возвращаем в естественный 8×8
    blocks = np.zeros((num_blocks, 8, 8), dtype=np.float64)
    blocks[:, _ZIGZAG_ROWS, _ZIGZAG_COLS] = arr

    # Де-квантование
    coeffs = blocks * (quant_matrix * q_scale)

    # IDCT: spatial = M.T @ coeffs @ M
    dct_m = _dct_matrix()
    spatial = dct_m.T @ coeffs @ dct_m  # (N, 8, 8)

    # Собрать массивы из блоков, обрезать паддинг
    hb = (h + 7) // 8
    wb = (w + 7) // 8
    result = spatial.reshape(hb, wb, 8, 8).transpose(0, 2, 1, 3).reshape(hb * 8, wb * 8)
    return result[:h, :w]


def _read_component(payload: bytes, offset: int) -> tuple[bytes, int]:
    """Прочитать один сжатый компонент: [len4][данные]. Возвращает (данные, новый offset)."""
    if offset + 4 > len(payload):
        raise CorruptFormat("truncated component length")
    comp_len = struct.unpack(">I", payload[offset:offset + 4])[0]
    if offset + 4 + comp_len > len(payload):
        raise CorruptFormat("truncated component data")
    return payload[offset + 4:offset + 4 + comp_len], offset + 4 + comp_len


def _save_png_rgb(arr_uint8: np.ndarray) -> bytes:
    """RGB uint8 (H, W, 3) -> PNG байты (8 бит)."""
    img = Image.fromarray(arr_uint8, "RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Точка входа decode
# ---------------------------------------------------------------------------

def decode(fmt_bytes: bytes) -> bytes:
    """Декодировать байты PIC1 в PNG 8 бит.

    Гарантии: W×H совпадают с оригиналом. Stateless.
    Бросает CorruptFormat на битые данные.
    """
    if len(fmt_bytes) < HEADER_SIZE:
        raise CorruptFormat("data too short for PIC1 header")

    header = parse_header(fmt_bytes)
    width = header["width"]
    height = header["height"]
    mode = header["mode"]
    downscale_ratio = header["downscale_ratio"]
    q_scale = header["q_scale"]

    payload = fmt_bytes[HEADER_SIZE:]

    proc_w = max(1, width // downscale_ratio)
    proc_h = max(1, height // downscale_ratio)

    if mode == MODE_RGB:
        # Три компонента: R, G, B на proc_h × proc_w
        offset = 0
        channels = []
        hb = (proc_h + 7) // 8
        wb = (proc_w + 7) // 8
        num_blocks = hb * wb
        for _ in range(3):
            comp_data, offset = _read_component(payload, offset)
            channel = _decode_component(comp_data, num_blocks, _LUM_QUANT,
                                        q_scale, proc_h, proc_w)
            channels.append(channel)
        rgb = np.stack(channels, axis=-1)
        rgb = np.clip(np.round(rgb), 0, 255).astype(np.uint8)

    else:  # MODE_YCBCR_420
        offset = 0

        # Y компонента (полное разрешение proc_h × proc_w)
        comp_data, offset = _read_component(payload, offset)
        hb = (proc_h + 7) // 8
        wb = (proc_w + 7) // 8
        num_blocks_y = hb * wb
        y = _decode_component(comp_data, num_blocks_y, _LUM_QUANT, q_scale,
                              proc_h, proc_w)

        # Cb компонента (proc_h//2 × proc_w//2)
        cb_h = max(1, proc_h // 2)
        cb_w = max(1, proc_w // 2)
        comp_data, offset = _read_component(payload, offset)
        hb = (cb_h + 7) // 8
        wb = (cb_w + 7) // 8
        num_blocks_cb = hb * wb
        cb = _decode_component(comp_data, num_blocks_cb, _CHROM_QUANT, q_scale,
                               cb_h, cb_w)

        # Cr компонента (proc_h//2 × proc_w//2)
        comp_data, offset = _read_component(payload, offset)
        cr = _decode_component(comp_data, num_blocks_cb, _CHROM_QUANT, q_scale,
                               cb_h, cb_w)

        # Upsample chroma до полного разрешения
        cb_full, cr_full = _color.chroma_upsample_420(cb, cr, proc_h, proc_w)

        # YCbCr -> RGB
        ycbcr = np.stack([y, cb_full, cr_full], axis=-1)
        rgb = _color.ycbcr_to_rgb(ycbcr)

    # Апскейл до исходных W×H если был downscale
    if downscale_ratio > 1:
        img = Image.fromarray(rgb, "RGB")
        img = img.resize((width, height), Image.Resampling.BILINEAR)
        rgb = np.array(img)

    return _save_png_rgb(rgb)
