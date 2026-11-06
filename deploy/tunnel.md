# tunnel.md — публикация локального API через облачный туннель.

## cloudflared (рекомендуется)

```bash
# Установить cloudflared, затем:
cloudflared tunnel --url http://localhost:8000
```

Выдаст временный URL вида `https://xxxx.trycloudflare.com`, который можно
указать в арене как BASE_URL.

## ngrok (альтернатива)

```bash
ngrok http 8000
```

## Примечание
Арена вызывает наш HTTP API по публичному URL. Туннель нужен только для
разработки и отладки; в продакшене API разворачивается на собственном хостинге.
