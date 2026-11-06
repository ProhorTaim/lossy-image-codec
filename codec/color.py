"""Цветовые пространства: RGB <-> YCbCr (BT.601), векторизованно на numpy.

Все преобразования работают с numpy-массивами без циклов по пикселям.
"""

import numpy as np


def rgb_to_ycbcr(rgb_uint8: np.ndarray) -> np.ndarray:
    """RGB uint8 (H, W, 3) -> YCbCr float64 (H, W, 3) по BT.601.

    Y   = 0.299 R + 0.587 G + 0.114 B
    Cb  = 128 - 0.168736 R - 0.331264 G + 0.5 B
    Cr  = 128 + 0.5 R - 0.418688 G - 0.081312 B
    """
    rgb = rgb_uint8.astype(np.float64)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = 128.0 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128.0 + 0.5 * r - 0.418688 * g - 0.081312 * b
    return np.stack([y, cb, cr], axis=-1)


def ycbcr_to_rgb(ycbcr_float: np.ndarray) -> np.ndarray:
    """YCbCr float64 (H, W, 3) -> RGB uint8 (H, W, 3) по BT.601.

    R = Y + 1.402 (Cr - 128)
    G = Y - 0.344136 (Cb - 128) - 0.714136 (Cr - 128)
    B = Y + 1.772 (Cb - 128)
    """
    ycbcr = ycbcr_float.astype(np.float64)
    y, cb, cr = ycbcr[..., 0], ycbcr[..., 1], ycbcr[..., 2]
    r = y + 1.402 * (cr - 128.0)
    g = y - 0.344136 * (cb - 128.0) - 0.714136 * (cr - 128.0)
    b = y + 1.772 * (cb - 128.0)
    rgb = np.stack([r, g, b], axis=-1)
    return np.clip(np.round(rgb), 0, 255).astype(np.uint8)


def chroma_subsample_420(ycbcr: np.ndarray):
    """YCbCr (H, W, 3) -> Y (H, W), Cb (H//2, W//2), Cr (H//2, W//2).

    Chroma-каналы усреднены по 2×2 блокам (стандартная 4:2:0).
    Если H или W < 2, канал chroma возвращается размером (1, 1) — чтобы
    не ломаться на крошечных картинках (1×1 и т.п.).
    """
    h, w, _ = ycbcr.shape
    y = ycbcr[..., 0]
    cb = ycbcr[..., 1]
    cr = ycbcr[..., 2]
    h2 = max(1, h // 2)
    w2 = max(1, w // 2)
    # Берем только полные 2×2 блоки, усредняем
    h_even = h2 * 2
    w_even = w2 * 2
    cb_small = cb[:h_even, :w_even].reshape(h2, 2, w2, 2).mean(axis=(1, 3))
    cr_small = cr[:h_even, :w_even].reshape(h2, 2, w2, 2).mean(axis=(1, 3))
    return y, cb_small, cr_small


def chroma_upsample_420(cb_small: np.ndarray, cr_small: np.ndarray,
                        h: int, w: int) -> tuple[np.ndarray, np.ndarray]:
    """Cb, Cr (h//2, w//2) -> Cb, Cr (h, w) nearest-neighbor 2×2.

    Используется для восстановления полноразмерного chroma после 4:2:0.
    При нечётных h/w досаджует крайние значения, чтобы размеры совпали.
    """
    cb = np.repeat(np.repeat(cb_small, 2, axis=0), 2, axis=1)
    cr = np.repeat(np.repeat(cr_small, 2, axis=0), 2, axis=1)
    # Падинг для нечётных размеров: досадить последнюю строку/столбец
    if cb.shape[0] < h or cb.shape[1] < w:
        cb = np.pad(cb, ((0, h - cb.shape[0]), (0, w - cb.shape[1])), mode='edge')
        cr = np.pad(cr, ((0, h - cr.shape[0]), (0, w - cr.shape[1])), mode='edge')
    return cb[:h, :w], cr[:h, :w]
