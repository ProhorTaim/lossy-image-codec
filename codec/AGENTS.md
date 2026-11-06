# AGENTS.md — зона разработчика алгоритма (codec/)

## Ты работаешь ТОЛЬКО в codec/
Не трогай api/, web/, deploy/, tests/ (кроме тестов кодека, согласованных с QA).
Не меняй openapi.yaml, AGENTS.md в корне, README.md — это контракты команды.

## Контракт, который нельзя ломать
encode(png_bytes: bytes, max_bytes: int) -> bytes
  - len(result) <= max_bytes, иначе CannotFit
  - BadInput на невалидный PNG или max_bytes <= 0
decode(fmt_bytes: bytes) -> bytes
  - PNG 8 бит, W×H точно как у оригинала
  - stateless, не требует оригинала
  - CorruptFormat на битые данные

Сигнатуры и исключения уже зафиксированы в codec/__init__.py и codec/errors.py.
Менять их можно только через отдельный PR с ревью QA и разработчика ПО.

## Запрещено
- Использовать JPEG/WebP/AVIF как единственный формат.
- Менять размеры картинки при decode. Если даунскейлил при encode — апскейль
  обратно сам, до исходных W×H.
- Хранить оригинал или состояние между encode и decode.
- Падать на мусоре — только исключения из codec/errors.py.
- Лезть в api/ и web/.

## Обязательно
- Всё, что делает кодек, — детерминированно: один вход → один выход.
- Каждый шаг rate control (подбор параметров под max_bytes) заканчивается
  проверкой len(result) <= max_bytes.
- Промежуточные данные — только в памяти, никаких temp-файлов.
- Публичные функции codec/ принимают/возвращают bytes, не PIL.Image, не numpy.

## Стиль
- Python 3.11+, type hints обязательны на публичных функциях.
- Никаких глобальных мутабельных состояний.
- Один модуль = одна ответственность (color, format, encoder, decoder,
  rate_control).
- Комментарии — про «почему», не про «что».

## Definition of Done для любой задачи в codec/
- encode укладывается в max_bytes на фикстурах 128×128 и 512×512 при 8 КБ.
- decode(fmt) даёт PNG тех же W×H, 8 бит.
- decode работает на «чистом» процессе без вызова encode.
- Нет обращений к сети, диску, времени, random без seed.
- make lint зелёный.
- Есть тест в tests/test_codec.py (пишешь вместе с QA, но не в одиночку).

## Как проверять локально (без API)
Тебе не нужен HTTP, чтобы проверять кодек. Пиши маленькие скрипты:

python3 -c "
from codec import encode, decode
png = open('tests/fixtures/grad128.png','rb').read()
fmt = encode(png, 8192)
assert len(fmt) <= 8192
back = decode(fmt)
assert back[:8] == b'\x89PNG\r\n\x1a\n'
print('ok', len(fmt))
"

Фикстуры появятся позже от QA. Пока можешь сгенерить свои через Pillow (он в venv):
python3 -c "
from PIL import Image
Image.new('RGB',(128,128)).save('/tmp/x.png')
"
Pillow и numpy — только в твоём venv, в репо зависимости добавляет разработчик ПО.