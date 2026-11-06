# Perceptual Image Codec

Собственный lossy-кодек для изображений с адаптацией под заданный размер файла.
Разработан для турнира: сохраняет максимальное визуальное качество в рамках
лимита max_bytes.

## Роли
- Разработчик алгоритма: ___
- Разработчик ПО: ___
- DevOps: ___
- QA: ___

## Как запустить локально
TODO: инструкция появится после реализации API.

## Контракты
- openapi.yaml — HTTP API по спецификации организаторов
- AGENTS.md — правила проекта (читать всем)
- codec/__init__.py — внутренний интерфейс encode/decode

## Проверка
- make test
- make check

## Чего НЕ делать
- Использовать готовые кодеки (JPEG/WebP/AVIF) как единственный формат.
- Хранить оригинал на сервере.
- Менять размеры при decode.

## Definition of Done для этой задачи
- [ ] Все папки и файлы из списка созданы.
- [ ] codec/__init__.py содержит рабочие (не падающие при импорте) заглушки
      encode/decode с NotImplementedError.
- [ ] codec/errors.py содержит 4 класса ошибок.
- [ ] Makefile: make lint и make test не падают (даже если тестов 0).
- [ ] openapi.yaml содержит спецификацию организаторов.
- [ ] AGENTS.md и README.md заполнены.
- [ ] .gitignore покрывает Python, Node.js, .env, IDE.
- [ ] Один коммит с сообщением:
      chore: initial project skeleton and contracts
