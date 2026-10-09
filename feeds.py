"""GenryTheFox -> Discord: new YouTube videos, GitHub releases and Boosty posts, through channel webhooks.

Runs every 15 minutes on GitHub Actions. state.json remembers what was already posted; the very first run of a
feed only remembers (no flood). Env: WEBHOOK_VIDEOS, WEBHOOK_RELEASES, WEBHOOK_NEWS (a feed without its webhook
is only remembered), optional PING_VIDEOS / PING_RELEASES / PING_NEWS (role ids), GITHUB_TOKEN.
    python feeds.py            # normal run
    python feeds.py --dry      # print what would be posted, change nothing
    python feeds.py --latest   # post the newest item of every feed once (to fill empty channels)
"""
import datetime
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state.json')
YT_CHANNEL = 'UCwi3GVh3ieHT9YzUpGX5pPg'
GH_USER = 'GenryTheFox0'
BOOSTY = 'genrythefox'
AVATAR = 'https://github.com/GenryTheFox0.png'
DRY = '--dry' in sys.argv
LATEST = '--latest' in sys.argv
UA = {'User-Agent': 'genry-discord-feeds/1.0 (+https://github.com/GenryTheFox0)'}


def get(url, headers=None, raw=False):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    return data if raw else json.loads(data)


def crosspost(msg):
    """Publish a message in an announcement channel, so servers following it get it too (needs the bot token)."""
    token = os.environ.get('DISCORD_BOT_TOKEN', '').strip()
    if not token or not msg or not msg.get('id'):
        return
    req = urllib.request.Request('https://discord.com/api/v10/channels/%s/messages/%s/crosspost' % (msg['channel_id'], msg['id']),
                                 data=b'', method='POST', headers={**UA, 'Authorization': 'Bot ' + token})
    try:
        urllib.request.urlopen(req, timeout=30).read()
    except urllib.error.HTTPError as e:
        print('  crosspost failed:', e.code, e.read()[:200])


def post(webhook, payload):
    if DRY or not webhook:
        print('  [dry]' if DRY else '  [no webhook]', json.dumps(payload, ensure_ascii=False)[:300])
        return
    body = json.dumps(payload).encode()
    for _ in range(5):
        req = urllib.request.Request(webhook + '?wait=true', data=body, headers={**UA, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                crosspost(json.loads(r.read() or b'{}'))
                return
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(json.loads(e.read() or b'{}').get('retry_after', 2)) + 0.5)
                continue
            raise
    raise RuntimeError('discord kept rate limiting')


# LYLA, the Nueva York 2099 AI, announces everything; the line is picked by the item id so reruns say the same
LINES = {
    'video': ['📺 **LYLA:** Генри выпустил новое видео — бросай всё и смотри! | Genry just dropped a new video, drop everything!',
              '🎬 **LYLA:** Свежий ролик с канала GenryTheFox. Лайк сам себя не поставит 😏 | Fresh video — that like won\'t click itself.',
              '🍿 **LYLA:** Попкорн готов? Новое видео уже здесь! | Popcorn ready? New video is up!'],
    'short': ['⚡ **LYLA:** Новый шортс, 60 секунд безумия! | New short — 60 seconds of madness!',
              '⚡ **LYLA:** Короткий, но мощный. Новый шортс! | Short but deadly. New short!'],
    'release': ['🛠️ **LYLA:** Свежая сборка прямо из лаборатории Генри! | Fresh build straight from Genry\'s lab!',
                '📦 **LYLA:** Новый релиз! Качаем, тестим, кидаем баги в 🐞-каналы. | New release — download, test, report bugs!',
                '🚀 **LYLA:** Обновление прилетело с GitHub. Алхимакс в шоке. | Update just landed. Alchemax is shaking.'],
    'boosty': ['🗞️ **Daily Bugle 2099:** Новый пост на Бусти! | New Boosty post!',
               '🗞️ **Daily Bugle 2099:** Экстренный выпуск — Генри опубликовал новое! | Breaking: Genry posted something new!'],
}


def line(kind, item_id):
    options = LINES[kind]
    return options[sum(map(ord, str(item_id))) % len(options)]


def ping(name):
    role = os.environ.get('PING_' + name, '').strip()
    return ('<@&%s> ' % role) if role else ''


def mentions(name):
    role = os.environ.get('PING_' + name, '').strip()
    return {'parse': [], 'roles': [role] if role else []}


# --- feeds: each returns items newest first, every item has a stable 'id' ---------------------------------------

def youtube():
    ns = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015',
          'media': 'http://search.yahoo.com/mrss/'}
    root = ET.fromstring(get('https://www.youtube.com/feeds/videos.xml?channel_id=' + YT_CHANNEL, raw=True))
    out = []
    for e in root.findall('a:entry', ns):
        vid = e.findtext('yt:videoId', '', ns)
        out.append({'id': vid, 'title': e.findtext('a:title', '', ns), 'url': 'https://www.youtube.com/watch?v=' + vid,
                    'shorts': '#shorts' in e.findtext('a:title', '', ns).lower()})
    return out


def releases():
    h = {'Accept': 'application/vnd.github+json'}
    if os.environ.get('GITHUB_TOKEN'):
        h['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    out = []
    for repo in get('https://api.github.com/users/%s/repos?per_page=100&type=owner' % GH_USER, h):
        if repo.get('fork') or repo.get('archived') or repo.get('private'):
            continue
        for r in get('https://api.github.com/repos/%s/releases?per_page=5' % repo['full_name'], h):
            if r.get('draft') or not r.get('published_at'):
                continue
            out.append({'id': str(r['id']), 'repo': repo['name'], 'name': r.get('name') or r['tag_name'],
                        'tag': r['tag_name'], 'url': r['html_url'], 'body': r.get('body') or '',
                        'pre': r.get('prerelease'), 'when': r['published_at'],
                        'assets': [(a['name'], a['size'], a['browser_download_url']) for a in r.get('assets', [])]})
    return sorted(out, key=lambda x: x['when'], reverse=True)


def boosty():
    out = []
    for p in get('https://api.boosty.to/v1/blog/%s/post/?limit=10' % BOOSTY).get('data', []):
        text, image = [], None
        for b in p.get('teaser', []) + p.get('data', []):
            if b.get('type') == 'text' and b.get('content'):
                try:
                    text.append(json.loads(b['content'])[0])
                except (ValueError, IndexError, TypeError):
                    pass
            if b.get('type') == 'image' and not image:
                image = b.get('url')
        level = (p.get('subscriptionLevel') or {})
        if p.get('price'):
            access = 'от %s ₽ подписки или %s ₽ разово' % (level.get('price'), p['price']) if level else '%s ₽' % p['price']
        elif level:
            access = 'подписка от %s ₽' % level.get('price')
        else:
            access = 'бесплатно для всех'
        out.append({'id': p['id'], 'title': p.get('title') or 'Новый пост', 'url': 'https://boosty.to/%s/posts/%s' % (BOOSTY, p['id']),
                    'text': ' '.join(t for t in text if t.strip())[:500], 'image': image, 'access': access,
                    'when': p.get('publishTime')})
    return out


# --- messages -----------------------------------------------------------------------------------------------------

def msg_video(v):
    return {'allowed_mentions': mentions('VIDEOS'),
            'content': '%s%s\n%s' % (ping('VIDEOS'), line('short' if v['shorts'] else 'video', v['id']), v['url'])}


def msg_release(r):
    body = re.sub(r'\n{3,}', '\n\n', r['body']).strip()
    body = re.sub(r'^#\s+.*\n+', '', body)  # the release notes often repeat the release name as a heading
    if len(body) > 700:
        body = body[:700].rsplit('\n', 1)[0] + '\n…'
    lines = [body] if body else []
    for name, size, url in r['assets'][:4]:
        lines.append('⬇️ [%s](%s) — %.1f MB' % (name, url, size / 1048576))
    lines.append('🔗 [Страница релиза | Release page](%s)' % r['url'])
    embed = {'title': '📦 %s — %s' % (r['repo'], r['name'])[:250], 'url': r['url'], 'description': '\n'.join(lines)[:3900],
             'color': 0xF0A030 if r['pre'] else 0x3FB950, 'timestamp': r['when'],
             'footer': {'text': 'GitHub • %s%s • LYLA 2099' % (r['tag'], ' • beta' if r['pre'] else '')}}
    return {'allowed_mentions': mentions('RELEASES'),
            'content': '%s%s' % (ping('RELEASES'), line('release', r['id'])), 'embeds': [embed]}


def msg_boosty(p):
    embed = {'title': p['title'][:250], 'url': p['url'], 'description': (p['text'] + '\n\n' if p['text'] else '') +
             '🔑 Доступ: %s\n👉 [Читать на Бусти | Open on Boosty](%s)' % (p['access'], p['url']),
             'color': 0xF15F2C, 'footer': {'text': 'Daily Bugle 2099 • boosty.to/%s' % BOOSTY}}
    if p['when']:
        embed['timestamp'] = datetime.datetime.fromtimestamp(p['when'], datetime.timezone.utc).isoformat()
    if p['image']:
        embed['image'] = {'url': p['image']}
    return {'allowed_mentions': mentions('NEWS'),
            'content': '%s%s' % (ping('NEWS'), line('boosty', p['id'])), 'embeds': [embed]}


FEEDS = [('youtube', youtube, msg_video, 'WEBHOOK_VIDEOS'),
         ('releases', releases, msg_release, 'WEBHOOK_RELEASES'),
         ('boosty', boosty, msg_boosty, 'WEBHOOK_NEWS')]
ZONE_KIND = {'youtube': 'video', 'releases': 'release', 'boosty': 'boosty'}


def main():
    state = json.load(open(STATE, encoding='utf-8')) if os.path.exists(STATE) else {}
    for key, fetch, make, hook_env in FEEDS:
        try:
            items = fetch()
        except Exception as e:  # one dead source must not stop the others
            print('%s: fetch failed: %s' % (key, e))
            continue
        hook = os.environ.get(hook_env, '').strip()
        seen = state.get(key)
        if LATEST and items:
            print('%s: posting the newest: %s' % (key, items[0]['id']))
            post(hook, make(items[0]))
            seen = list(dict.fromkeys((seen or []) + [i['id'] for i in items]))
        elif seen is None or not hook:
            print('%s: remembering %d items, nothing posted' % (key, len(items)))
            seen = [i['id'] for i in items] if seen is None else list(dict.fromkeys(seen + [i['id'] for i in items]))
        else:
            fresh = [i for i in items if i['id'] not in seen]
            for item in reversed(fresh):  # oldest first, so the channel reads in order
                print('%s: new %s' % (key, item['id']))
                post(hook, make(item))
                if not DRY:
                    try:
                        import lyla_schedule
                        lyla_schedule.zone_news(ZONE_KIND[key], item)
                    except Exception as e:  # the zones are a bonus; the main channel already has it
                        print('  zones failed:', e)
                seen.append(item['id'])
                time.sleep(1)
            if not fresh:
                print('%s: nothing new' % key)
        if not DRY:
            state[key] = seen[-300:]
    try:
        import lyla_schedule
        lyla_schedule.run(state, dry=DRY)
    except Exception as e:
        print('lyla schedule failed:', e)
    # a monthly touch keeps GitHub from switching the schedule off in a quiet repo
    month = datetime.date.today().strftime('%Y-%m')
    if not DRY and state.get('heartbeat') != month:
        state['heartbeat'] = month
    if not DRY:
        json.dump(state, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
