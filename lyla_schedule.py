"""LYLA's timetable, run by the robot every 15 minutes (GitHub Actions, so it works with Genry's PC off):
Boosty promo in the four zone chats on Mondays and Thursdays, renewal news on the 1st and the 27th,
and every new video / release / Boosty post repeated in the four zone news channels in their language.
"""
import datetime
import json
import os
import urllib.error
import urllib.request

import lyla_texts as T

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'server.json'), encoding='utf-8'))
UA = {'User-Agent': 'DiscordBot (https://github.com/GenryTheFox0, 1.0)'}
PROMO_DAYS = {0, 3}          # Monday, Thursday
PROMO_HOUR = 16              # 16:00 UTC = 19:00 Moscow
RENEW_DAYS = {1: 'start', 27: 'end'}
RENEW_HOUR = 9               # 12:00 Moscow
WINDOW = datetime.timedelta(hours=3)


def bot_post(channel, content, publish=False):
    token = os.environ.get('DISCORD_BOT_TOKEN', '').strip()
    if not token:
        print('  [no bot token]', channel, content[:80])
        return
    body = json.dumps({'content': content[:2000], 'allowed_mentions': {'parse': []}}).encode()
    req = urllib.request.Request('https://discord.com/api/v10/channels/%s/messages' % channel, data=body, method='POST',
                                 headers={**UA, 'Authorization': 'Bot ' + token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            msg = json.loads(r.read())
        if publish:
            req = urllib.request.Request('https://discord.com/api/v10/channels/%s/messages/%s/crosspost' % (channel, msg['id']),
                                         data=b'', method='POST', headers={**UA, 'Authorization': 'Bot ' + token})
            urllib.request.urlopen(req, timeout=30).read()
    except urllib.error.HTTPError as e:
        print('  post failed', channel, e.code, e.read()[:200])


def zone_news(kind, item):
    """Repeat one feed item in every zone's news channel, in that zone's language."""
    fields = {'title': item.get('title') or item.get('name', ''), 'url': item.get('url', ''), 'repo': item.get('repo', ''),
              'name': item.get('name', '')}
    for lang, zone in CFG['zones'].items():
        bot_post(zone['news'], T.ZONE_NEWS[kind][lang].format(**fields), publish=False)


def due(now, slot):
    return slot <= now < slot + WINDOW


def run(state, dry=False):
    now = datetime.datetime.now(datetime.timezone.utc)
    done = state.setdefault('lyla', [])
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    jobs = []
    if now.weekday() in PROMO_DAYS:
        jobs.append(('promo-' + today.strftime('%Y-%m-%d'), today.replace(hour=PROMO_HOUR), 'promo'))
    if now.day in RENEW_DAYS:
        jobs.append(('renew-' + today.strftime('%Y-%m-%d'), today.replace(hour=RENEW_HOUR), RENEW_DAYS[now.day]))
    for key, slot, what in jobs:
        if key in done or not due(now, slot):
            continue
        print('lyla:', key)
        if not dry:
            if what == 'promo':
                week = now.isocalendar()[1] * 2 + (now.weekday() == 3)
                for lang, zone in CFG['zones'].items():
                    bot_post(zone['chat'], T.PROMO[lang][week % len(T.PROMO[lang])])
            else:
                for lang, zone in CFG['zones'].items():
                    bot_post(zone['news'], T.RENEW[what][lang])
                bot_post(CFG['bugle'], T.RENEW[what]['ru'] + '\n\n' + T.RENEW[what]['en'], publish=True)
        done.append(key)
    state['lyla'] = done[-60:]


if __name__ == '__main__':
    st = {}
    run(st, dry=True)
    print('jobs remembered:', st)
