"""LYLA without a PC: every robot run (15 min) she welcomes newcomers in their zone, thanks new Boosty supporters
and answers people who called her. Discord itself is the shared memory with the live bot on Genry's PC: if LYLA
already answered or welcomed someone there, the robot sees it and stays quiet.
"""
import hashlib
import hmac
import json
import os
import re
import time
import urllib.error
import urllib.request

import lyla_texts as T

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'server.json'), encoding='utf-8'))
API = 'https://discord.com/api/v10'
UA = 'DiscordBot (https://github.com/GenryTheFox0, 1.0)'
LANG_OF_ROLE = {v: k for k, v in CFG['lang_roles'].items()}
TIER_ROLES = CFG['tier_roles']               # name -> id
CYRILLIC = re.compile('[а-яё]', re.I)
SPANISH = re.compile(r'\b(hola|gracias|dónde|donde|cómo|como|descargar|qué|que tal|juego)\b', re.I)
PORTUGUESE = re.compile(r'\b(olá|ola|obrigad[oa]|onde|baixar|você|voce|jogo|tudo bem)\b', re.I)


def api(method, path, body=None):
    token = os.environ.get('DISCORD_BOT_TOKEN', '').strip()
    headers = {'Authorization': 'Bot ' + token, 'User-Agent': UA}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    for _ in range(5):
        req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raw = e.read()
            if e.code == 429:
                time.sleep(float(json.loads(raw or b'{}').get('retry_after', 1)) + 0.3)
                continue
            raise RuntimeError('%s %s -> %s %s' % (method, path, e.code, raw[:200]))
        except (urllib.error.URLError, OSError) as e:  # flaky network: wait and try again
            last_error = e
            time.sleep(2)
            continue
    raise RuntimeError('gave up on %s' % path)


def say(channel, text, mention=None, reply_to=None):
    body = {'content': text[:2000], 'allowed_mentions': {'parse': [], 'users': [mention] if mention else [], 'replied_user': bool(reply_to)}}
    if reply_to:
        body['message_reference'] = {'message_id': reply_to, 'channel_id': channel, 'fail_if_not_exists': False}
    return api('POST', '/channels/%s/messages' % channel, body)


def members():
    out, after = [], '0'
    while True:
        batch = api('GET', '/guilds/%s/members?limit=1000&after=%s' % (CFG['guild'], after))
        out += batch
        if len(batch) < 1000:
            return out
        after = batch[-1]['user']['id']


def lang_of(member=None, text=''):
    for r in (member or {}).get('roles', []):
        if r in LANG_OF_ROLE:
            return LANG_OF_ROLE[r]
    if CYRILLIC.search(text):
        return 'ru'
    if PORTUGUESE.search(text):
        return 'pt'
    if SPANISH.search(text):
        return 'es'
    return 'en'


def recent(channel, limit=50):
    try:
        return api('GET', '/channels/%s/messages?limit=%d' % (channel, limit))
    except Exception:
        return []


def tag(uid):
    """state.json lives in a public repo: members are kept as HMAC tags keyed by the bot token (a GitHub secret), never raw IDs."""
    key = os.environ.get('DISCORD_BOT_TOKEN', '').strip().encode()
    return hmac.new(key, str(uid).encode(), hashlib.sha256).hexdigest()[:16]


def remember_all(state, ms, why):
    state['welcomed'] = [tag(m['user']['id']) for m in ms]
    state['thanked'] = ['%s:%s' % (tag(m['user']['id']), r) for m in ms for r in m['roles'] if r in TIER_ROLES.values()]
    print('presence: remembered %d members (%s)' % (len(ms), why))


def welcomes_and_thanks(state, dry):
    bot = CFG['bot_id']
    ms = [m for m in members() if not m['user'].get('bot')]
    seen = state.get('welcomed')
    thanked = state.get('thanked')
    if seen is None or thanked is None:  # first run: everyone already here counts as greeted
        remember_all(state, ms, 'first run')
        return
    # old states kept raw IDs: convert them to tags in place
    seen = {tag(x) if x.isdigit() else x for x in seen}
    thanked = {('%s:%s' % (tag(x.split(':')[0]), x.split(':')[1])) if x.split(':')[0].isdigit() else x for x in thanked}
    fresh = [m for m in ms if tag(m['user']['id']) not in seen and any(r in LANG_OF_ROLE for r in m['roles'])]
    if len(fresh) > 15:  # nobody gets 15 newcomers in 15 minutes: the key changed, don't greet the whole server again
        remember_all(state, ms, 'key changed, %d unknown' % len(fresh))
        return
    zone_recent = {}
    for m in ms:
        uid = m['user']['id']
        lang = next((LANG_OF_ROLE[r] for r in m['roles'] if r in LANG_OF_ROLE), None)
        if tag(uid) not in seen and lang:
            zone = CFG['zones'][lang]
            if zone['chat'] not in zone_recent:
                zone_recent[zone['chat']] = recent(zone['chat'])
            if not any(x['author']['id'] == bot and uid in [u['id'] for u in x.get('mentions', [])] for x in zone_recent[zone['chat']]):
                text = T.WELCOME[lang].format(who='<@%s>' % uid, start='<#%s>' % CFG['start'], news='<#%s>' % zone['news'],
                                             bugs='<#%s>' % zone['bugs'], boosty=T.BOOSTY)
                print('presence: welcome', lang)          # Actions logs are public: no member IDs
                if not dry:
                    say(zone['chat'], text, mention=uid)
            seen.add(tag(uid))
        for name, rid in TIER_ROLES.items():
            key = '%s:%s' % (tag(uid), rid)
            if rid in m['roles'] and key not in thanked:
                print('presence: thanks', name)
                if not dry:
                    say(CFG['global'], T.THANKS.format(who='<@%s>' % uid, tier=name, boosty=T.BOOSTY), mention=uid)
                thanked.add(key)
    state['welcomed'] = sorted(seen)[-3000:]
    state['thanked'] = sorted(thanked)[-3000:]


def replies(state, dry):
    bot = CFG['bot_id']
    chats = [z['chat'] for z in CFG['zones'].values()] + [CFG['global']]
    last = state.setdefault('last_msg', {})
    cool = state.setdefault('cooldown', {})
    now = time.time()
    member_cache = {}
    for ch in chats:
        msgs = recent(ch)
        if not msgs:
            continue
        newest = msgs[0]['id']
        if ch not in last:  # first look at a channel: start from now, no replies to the past
            last[ch] = newest
            continue
        answered = {x['message_reference']['message_id'] for x in msgs if x['author']['id'] == bot and x.get('message_reference')}
        for msg in reversed([x for x in msgs if int(x['id']) > int(last[ch])]):
            if msg['author'].get('bot') or msg['id'] in answered:
                continue
            text = msg.get('content', '')
            low = text.lower()
            called = bot in [u['id'] for u in msg.get('mentions', [])] or (
                (msg.get('referenced_message') or {}).get('author', {}).get('id') == bot) or re.search(r'\b(lyla|лайла|лила)\b', low)
            want_dl = any(w in low for w in T.DOWNLOAD_WORDS)
            want_sup = any(w in low for w in T.SUPPORT_WORDS)
            if not (called or want_dl or want_sup):
                continue
            uid = msg['author']['id']
            if uid not in member_cache:
                try:
                    member_cache[uid] = api('GET', '/guilds/%s/members/%s' % (CFG['guild'], uid))
                except Exception:
                    member_cache[uid] = {}
            lang = lang_of(member_cache[uid], text)
            if want_dl:
                key, answer = 'dl:' + ch, T.DOWNLOAD[lang]
            elif want_sup:
                key, answer = 'sup:' + ch, T.SUPPORT[lang].format(boosty=T.BOOSTY)
            else:
                key, answer = None, T.pick(T.CHAT[lang], seed=msg['id'])
            if key and now - cool.get(key, 0) < 1800 and not called:
                continue
            print('presence: reply', ch, msg['id'], lang, key or 'chat')
            if not dry:
                say(ch, answer, reply_to=msg['id'])
            if key:
                cool[key] = now
        last[ch] = newest


def run(state, dry=False):
    if not os.environ.get('DISCORD_BOT_TOKEN') and not dry:
        print('presence: no bot token')
        return
    for step in (welcomes_and_thanks, replies):
        try:
            step(state, dry)
        except Exception as e:
            print('presence %s failed: %s' % (step.__name__, e))
