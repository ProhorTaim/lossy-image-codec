"""Бинарный формат PIC1: заголовок + сжатые данные.

Схема заголовка (big-endian, всего 18 байт):
  offset 0  : magic        4 байта  b'PIC1'
  offset 4  : version      uint8    = 1
  offset 5  : flags        uint8    бит 0 — был downscale, остальное 0
  offset 6  : width        uint32   исходная ширина W
  offset 10 : height       uint32   исходная высота H
  offset 14 : mode         uint8    0 = RGB напрямую, 1 = YCbCr 4:2:0
  offset 15 : downscale_ratio uint8 1 = без downscale, 2 = /2, 4 = /4
  offset 16 : q_scale      uint16   использованный масштаб квантования
  offset 18 : payload      残り     zlib(RLE(zigzag(quantized DCT-коэффициенты)))

Формат самодостаточен: decoder восстанавливает W×H, mode, downscale_ratio,
q_scale только из этих байт.
"""

import struct
from .errors import CorruptFormat

MAGIC = b"PIC1"
VERSION = 1
HEADER_SIZE = 18

MODE_RGB = 0
MODE_YCBCR_420 = 1

_HEADER_STRUCT = struct.Struct(">4sBBIIBBH")


def serialize_header(width: int, height: int, mode: int,
                     downscale_ratio: int, q_scale: int,
                     flags: int = 0) -> bytes:
    """Собрать 18-байтовый заголовок формата в big-endian порядке."""
    return _HEADER_STRUCT.pack(
        MAGIC, VERSION, flags, width, height,
        mode, downscale_ratio, q_scale,
    )


def parse_header(data: bytes) -> dict:
    """Распарсить заголовок PIC1.

    Бросает CorruptFormat на битые, слишком короткие или неизвестные данные.
    Возвращает словарь с полями width, height, mode, downscale_ratio,
    q_scale, flags.
    """
    if len(data) < HEADER_SIZE:
        raise CorruptFormat("data too short for PIC1 header")
    magic, version, flags, width, height, mode, downscale_ratio, q_scale = \
        _HEADER_STRUCT.unpack(data[:HEADER_SIZE])
    if magic != MAGIC:
        raise CorruptFormat("bad magic: expected b'PIC1'")
    if version != VERSION:
        raise CorruptFormat(f"unsupported version: {version}")
    if mode not in (MODE_RGB, MODE_YCBCR_420):
        raise CorruptFormat(f"unsupported mode: {mode}")
    if downscale_ratio not in (1, 2, 4):
        raise CorruptFormat(f"unsupported downscale_ratio: {downscale_ratio}")
    return {
        "width": width,
        "height": height,
        "mode": mode,
        "downscale_ratio": downscale_ratio,
        "q_scale": q_scale,
        "flags": flags,
    }


def _rle_encode(values) -> bytes:
    """RLE сжатие потока квантованных коэффициентов.

    Каждый символ: uint8 run (0-15) + int16 value (big-endian).
    Run = 15 с value = 0 означает «16 нулей подряд» (продолжается).
    Конец потока — символ (0, 0) (EOB).
    """
    out = bytearray()
    zero_run = 0
    for v in values:
        v = int(v)
        if v == 0:
            zero_run += 1
            while zero_run >= 16:
                out.extend(struct.pack(">Bh", 15, 0))
                zero_run -= 16
        else:
            while zero_run >= 16:
                out.extend(struct.pack(">Bh", 15, 0))
                zero_run -= 16
            out.extend(struct.pack(">Bh", zero_run, v))
            zero_run = 0
    out.extend(struct.pack(">Bh", 0, 0))  # EOB
    return bytes(out)


def _rle_decode(data: bytes, expected_count: int) -> list:
    """Обратный RLE. Возвращает список целых длиной до expected_count."""
    values = []
    i = 0
    n = len(data)
    while i + 3 <= n:
        run = data[i]
        val = struct.unpack(">h", data[i + 1:i + 3])[0]
        i += 3
        if run == 0 and val == 0:
            break  # EOB
        values.extend([0] * run)
        values.append(val)
    return values[:expected_count]
