#!/usr/bin/env bash
# tests/check_api.sh — скрипт проверки API по сценарию из раздела 7 спеки.
#
# Сценарий check:
#   1. GET /v1/health -> 200 {"status":"ok"}
#   2. POST /v1/encode 128x128 градиент, max_bytes=8192 -> <= 8 КБ
#   3. POST /v1/encode 512x512 фото, max_bytes=8192 -> <= 8 КБ
#   4. POST /v1/encode 1x1, max_bytes=8192
#   5. POST /v1/encode RGBA, max_bytes=8192
#   6. POST /v1/decode битые байты -> 4xx
#
# На этом этапе — заглушка.

echo "TODO: реализовать check"
