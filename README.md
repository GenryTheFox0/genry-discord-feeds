# genry-discord-feeds

Робот сервера **Project 2099 (Team GenryTheFox)**: каждые 15 минут смотрит

- 🎬 YouTube-канал [@GenryTheFox1](https://www.youtube.com/@GenryTheFox1) → `#videos`
- 📦 релизы всех публичных репозиториев [GenryTheFox0](https://github.com/GenryTheFox0) → `#releases`
- 📰 посты на [Бусти](https://boosty.to/genrythefox) → `#news`

и шлёт новое в Discord через вебхуки каналов. Что уже отправлено, помнит `state.json`.

Секреты репозитория: `WEBHOOK_VIDEOS`, `WEBHOOK_RELEASES`, `WEBHOOK_NEWS`.
Переменные (необязательно): `PING_VIDEOS`, `PING_RELEASES`, `PING_NEWS` — id ролей, которые пинговать.

Вручную: Actions → discord-feeds → Run workflow (галочка `latest` — переслать последнее из каждой ленты).
