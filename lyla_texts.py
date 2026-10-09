"""Everything LYLA says, in the four languages of the server (en, ru, es, pt). Shared by the GitHub robot and the live bot."""
import json
import random
import urllib.parse
import urllib.request

BOOSTY = 'https://boosty.to/genrythefox'
ALERTS = 'https://www.donationalerts.com/r/genrythefox'
DONATEPAY = 'https://donatepay.ru/don/1411886'
LANGS = ['en', 'ru', 'es', 'pt']
FLAG = {'en': '🇬🇧', 'ru': '🇷🇺', 'es': '🇪🇸', 'pt': '🇧🇷'}

# ---------------------------------------------------------------- news mirrored into every zone
ZONE_NEWS = {
    'video': {'en': '🎬 **New video from Genry!** {title}\n{url}', 'ru': '🎬 **Новое видео Генри!** {title}\n{url}',
              'es': '🎬 **¡Nuevo video de Genry!** {title}\n{url}', 'pt': '🎬 **Vídeo novo do Genry!** {title}\n{url}'},
    'release': {'en': '📦 **New release — {repo} {name}**\nDownload / changelog: {url}',
                'ru': '📦 **Новый релиз — {repo} {name}**\nСкачать и что нового: {url}',
                'es': '📦 **Nueva versión — {repo} {name}**\nDescarga y cambios: {url}',
                'pt': '📦 **Nova versão — {repo} {name}**\nDownload e novidades: {url}'},
    'boosty': {'en': '🗞️ **New post on Genry\'s Boosty:** {title}\n{url}', 'ru': '🗞️ **Новый пост на Бусти Генри:** {title}\n{url}',
               'es': '🗞️ **Nuevo post en el Boosty de Genry:** {title}\n{url}', 'pt': '🗞️ **Post novo no Boosty do Genry:** {title}\n{url}'},
}

# ---------------------------------------------------------------- Boosty promo for the zone chats (twice a week)
PROMO = {
    'en': [
        '💎 **LYLA:** Quick reminder, spiders: everything Genry makes — ports, mod makers, videos — runs on Boosty support. '
        'Supporters get builds first, and 300 ₽+ unlocks the 💎 VIP lounge with the team. 👉 ' + BOOSTY,
        '🕷️ **LYLA:** Want Project 2099 builds before anyone else? Test builds go to Boosty supporters first. '
        'Link Discord in your Boosty settings and your role arrives on its own 💗 ' + BOOSTY,
        '🌙 **LYLA:** Every donation is one more night of Genry porting games. One-off: ' + ALERTS + ' · monthly: ' + BOOSTY,
    ],
    'ru': [
        '💎 **LYLA:** Паучки, напоминаю: всё, что делает Генри — порты, конструкторы, видео — живёт на подписках Бусти. '
        'Подписчики получают сборки раньше всех, а с 300 ₽ открывается 💎 VIP-лаунж с командой. 👉 ' + BOOSTY,
        '🕷️ **LYLA:** Хочешь Project 2099 раньше всех? Тестовые сборки сначала уходят подписчикам Бусти. '
        'Привяжи Discord в настройках Бусти — роль прилетит сама 💗 ' + BOOSTY,
        '🌙 **LYLA:** Каждый донат — это ещё одна ночь Генри над портами. Разово: ' + ALERTS + ' · ' + DONATEPAY + ' · подписка: ' + BOOSTY,
    ],
    'es': [
        '💎 **LYLA:** Recordatorio, arañitas: todo lo que hace Genry — ports, creadores de mods, videos — vive del apoyo en Boosty. '
        'Los que apoyan reciben las versiones primero, y desde 300 ₽ se abre el 💎 VIP lounge. 👉 ' + BOOSTY,
        '🕷️ **LYLA:** ¿Quieres Project 2099 antes que nadie? Las versiones de prueba van primero a quienes apoyan en Boosty. '
        'Vincula Discord en Boosty y tu rol llega solo 💗 ' + BOOSTY,
        '🌙 **LYLA:** Cada donación es una noche más de Genry portando juegos. Donar: ' + ALERTS + ' · mensual: ' + BOOSTY,
    ],
    'pt': [
        '💎 **LYLA:** Lembrete, aranhinhas: tudo o que o Genry faz — ports, criadores de mods, vídeos — vive do apoio no Boosty. '
        'Quem apoia recebe as versões primeiro, e a partir de 300 ₽ abre o 💎 VIP lounge. 👉 ' + BOOSTY,
        '🕷️ **LYLA:** Quer o Project 2099 antes de todo mundo? As versões de teste vão primeiro para quem apoia no Boosty. '
        'Vincule o Discord no Boosty e seu cargo chega sozinho 💗 ' + BOOSTY,
        '🌙 **LYLA:** Cada doação é mais uma noite do Genry portando jogos. Doar: ' + ALERTS + ' · mensal: ' + BOOSTY,
    ],
}

# ---------------------------------------------------------------- renewal news (1st and 27th of every month)
RENEW = {
    'start': {
        'en': '📅 **New month in Nueva York 2099!** If your Boosty support renews by hand, renew it today so you keep your role, '
              'the 💎 VIP lounge and the 🧪 test builds. 👉 ' + BOOSTY,
        'ru': '📅 **Новый месяц в Нуэва-Йорке 2099!** Если подписка на Бусти продлевается вручную — продли сегодня, '
              'чтобы не потерять роль, 💎 VIP-лаунж и 🧪 тестовые сборки. 👉 ' + BOOSTY,
        'es': '📅 **¡Nuevo mes en Nueva York 2099!** Si tu apoyo en Boosty se renueva a mano, renuévalo hoy para no perder tu rol, '
              'el 💎 VIP lounge y las 🧪 versiones de prueba. 👉 ' + BOOSTY,
        'pt': '📅 **Novo mês em Nova York 2099!** Se o seu apoio no Boosty renova manualmente, renove hoje para não perder seu cargo, '
              'o 💎 VIP lounge e as 🧪 versões de teste. 👉 ' + BOOSTY,
    },
    'end': {
        'en': '⏳ **The month is almost over.** Check your Boosty subscription — without renewal the role and VIP access go away. '
              'Renewed? LYLA adores you 💗 ' + BOOSTY,
        'ru': '⏳ **Месяц почти закончился.** Проверь подписку на Бусти — без продления роль и доступ к VIP пропадут. '
              'Продлил? LYLA тебя обожает 💗 ' + BOOSTY,
        'es': '⏳ **El mes casi termina.** Revisa tu suscripción en Boosty — sin renovarla, el rol y el acceso VIP desaparecen. '
              '¿Renovaste? LYLA te adora 💗 ' + BOOSTY,
        'pt': '⏳ **O mês está acabando.** Confira sua assinatura no Boosty — sem renovar, o cargo e o acesso VIP somem. '
              'Renovou? A LYLA te adora 💗 ' + BOOSTY,
    },
}

# ---------------------------------------------------------------- live bot lines
WELCOME = {
    'en': '👋 {who}, welcome to the **English Web**! I\'m LYLA, the city AI. Start at {start}, news in {news}, bugs go to {bugs}. '
          'Want builds first? {boosty} 💗',
    'ru': '👋 {who}, добро пожаловать в **Русскую паутину**! Я LYLA, ИИ этого города. Начни с {start}, новости — {news}, баги — {bugs}. '
          'Сборки раньше всех — на Бусти: {boosty} 💗',
    'es': '👋 {who}, ¡bienvenido a la **Telaraña española**! Soy LYLA, la IA de la ciudad. Empieza en {start}, noticias en {news}, '
          'bugs en {bugs}. ¿Versiones antes que nadie? {boosty} 💗',
    'pt': '👋 {who}, bem-vindo à **Teia brasileira**! Eu sou a LYLA, a IA da cidade. Comece em {start}, notícias em {news}, '
          'bugs em {bugs}. Quer as versões primeiro? {boosty} 💗',
}
THANKS = ('💎 {who} теперь **{tier}**! Спасибо, что держишь Нуэва-Йорк 2099 на плаву 💗\n'
          '💎 {who} is now **{tier}** — thank you for supporting Genry! Want the same? {boosty}')
DOWNLOAD = {
    'en': '⬇️ **Where to download:**\n🕷️ Project 2099 (Spider-Man EOT PC): https://github.com/GenryTheFox0/Project-2099/releases\n'
          '🥊 Project Iron 6 (Tekken 6 PC): https://github.com/GenryTheFox0/Project-Iron-6/releases\n'
          '🏕️ GenryBL: https://github.com/GenryTheFox0/GenryBL/releases\n'
          '💗 GenryDDLC and early builds: ' + BOOSTY + '\nYou need your own copy of the game — no ISO links here 🏴‍☠️🚫',
    'ru': '⬇️ **Где скачать:**\n🕷️ Project 2099 (Spider-Man EOT на ПК): https://github.com/GenryTheFox0/Project-2099/releases\n'
          '🥊 Project Iron 6 (Tekken 6 на ПК): https://github.com/GenryTheFox0/Project-Iron-6/releases\n'
          '🏕️ GenryBL: https://github.com/GenryTheFox0/GenryBL/releases\n'
          '💗 GenryDDLC и ранние сборки: ' + BOOSTY + '\nНужна своя копия игры — ссылок на ISO тут нет 🏴‍☠️🚫',
    'es': '⬇️ **Dónde descargar:**\n🕷️ Project 2099: https://github.com/GenryTheFox0/Project-2099/releases\n'
          '🥊 Project Iron 6: https://github.com/GenryTheFox0/Project-Iron-6/releases\n'
          '🏕️ GenryBL: https://github.com/GenryTheFox0/GenryBL/releases\n'
          '💗 GenryDDLC y versiones tempranas: ' + BOOSTY + '\nNecesitas tu propia copia del juego — aquí no hay ISO 🏴‍☠️🚫',
    'pt': '⬇️ **Onde baixar:**\n🕷️ Project 2099: https://github.com/GenryTheFox0/Project-2099/releases\n'
          '🥊 Project Iron 6: https://github.com/GenryTheFox0/Project-Iron-6/releases\n'
          '🏕️ GenryBL: https://github.com/GenryTheFox0/GenryBL/releases\n'
          '💗 GenryDDLC e versões antecipadas: ' + BOOSTY + '\nVocê precisa da sua cópia do jogo — aqui não tem ISO 🏴‍☠️🚫',
}
SUPPORT = {
    'en': '💎 **Support Genry:** monthly on Boosty {boosty} (roles + VIP lounge) · one-off: ' + ALERTS + ' · ' + DONATEPAY,
    'ru': '💎 **Поддержать Генри:** подписка на Бусти {boosty} (роль + VIP-лаунж) · разово: ' + ALERTS + ' · ' + DONATEPAY,
    'es': '💎 **Apoya a Genry:** mensual en Boosty {boosty} (rol + VIP lounge) · única vez: ' + ALERTS + ' · ' + DONATEPAY,
    'pt': '💎 **Apoie o Genry:** mensal no Boosty {boosty} (cargo + VIP lounge) · uma vez: ' + ALERTS + ' · ' + DONATEPAY,
}
CHAT = {
    'en': ['Yes, spider? 🕷️ I\'m listening.', 'LYLA online. Nueva York 2099 is stable… mostly 😏', 'Need builds? Type /download. Need love? Type /boosty 💗',
           'I see everything, but I only judge a little 👁️', 'Genry is probably porting something right now. As always 🌙'],
    'ru': ['Да, паучок? 🕷️ Слушаю.', 'LYLA на связи. Нуэва-Йорк 2099 стабилен… почти 😏', 'Нужны сборки — /download. Нужна любовь — /boosty 💗',
           'Я всё вижу, но осуждаю совсем чуть-чуть 👁️', 'Генри сейчас наверняка что-то портирует. Как обычно 🌙'],
    'es': ['¿Sí, arañita? 🕷️ Te escucho.', 'LYLA en línea. Nueva York 2099 está estable… casi 😏', '¿Versiones? /download. ¿Amor? /boosty 💗',
           'Lo veo todo, pero juzgo solo un poquito 👁️', 'Genry seguro está portando algo ahora mismo 🌙'],
    'pt': ['Sim, aranhinha? 🕷️ Tô ouvindo.', 'LYLA online. Nova York 2099 está estável… quase 😏', 'Versões? /download. Carinho? /boosty 💗',
           'Eu vejo tudo, mas só julgo um pouquinho 👁️', 'O Genry com certeza está portando algo agora 🌙'],
}
DOWNLOAD_WORDS = ['где скачать', 'как скачать', 'ссылку на', 'how to download', 'where to download', 'download link', 'dónde descargar',
                  'donde descargar', 'como descargar', 'onde baixar', 'como baixar', 'link para baixar']
SUPPORT_WORDS = ['как поддержать', 'как задонатить', 'how to support', 'how can i support', 'how to donate', 'cómo apoyar', 'como apoyar',
                 'como apoiar', 'como doar']
STATUSES = ['Nueva York 2099 🕷️', 'your bug reports 🐞', 'boosty.to/genrythefox 💎', 'Genry porting games 🌙', 'нового паучка 👋']


def pick(lines, seed=None):
    return random.Random(seed).choice(lines) if seed is not None else random.choice(lines)


def translate(text, target, source='ru'):
    """Free MyMemory translation; brand names are shielded. Returns the original on any failure."""
    if target == source:
        return text
    shield = {'Бусти': 'Boosty', 'Генри': 'Genry', 'Нуэва-Йорк': 'Nueva York', 'ЛАЙЛА': 'LYLA'}
    for a, b in shield.items():
        text = text.replace(a, b)
    # names the translator likes to "translate" travel as placeholders
    keep = ['Project Iron 6', 'Project 2099', 'Edge of Time', 'GenryDDLC', 'GenryBL', 'GenryTheFox', 'Boosty', 'Spider-Man', 'Genry', 'LYLA']
    marks = {}
    for i, name in enumerate(keep):
        if name in text:
            marks['ZQ%dQZ' % i] = name
            text = text.replace(name, 'ZQ%dQZ' % i)
    out = []
    for chunk in [text[i:i + 450] for i in range(0, len(text), 450)]:
        url = 'https://api.mymemory.translated.net/get?' + urllib.parse.urlencode({'q': chunk, 'langpair': '%s|%s' % (source, target)})
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'LYLA-2099'}), timeout=20) as r:
                data = json.loads(r.read())
            tr = data.get('responseData', {}).get('translatedText') or chunk
            out.append(chunk if 'MYMEMORY WARNING' in tr.upper() else tr)
        except Exception:
            out.append(chunk)
    result = ''.join(out)
    for mark, name in marks.items():
        result = result.replace(mark, name).replace(mark.lower(), name)
    return result.replace('Busty', 'Boosty').replace('Бусти', 'Boosty')
