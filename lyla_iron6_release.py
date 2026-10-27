"""Announce one published Project Iron 6 release with LYLA, without other feeds.

Runs from the existing genry-discord-feeds repository and shares its `feeds`
Actions concurrency group. Each checkpoint is committed and pushed immediately.
An interrupted or ambiguous POST is reconciled against Discord history; if the
result cannot be established, it stops instead of blindly posting a duplicate.
"""
import copy
import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import feeds
import lyla_texts

REPO = 'GenryTheFox0/Project-Iron-6'
GUILD = '1551354993330880673'
BOT = '1558145590238511304'
RELEASES_CHANNEL = '1558149362855714827'
EXPECTED_ZONES = {'en': '1551646593806110760', 'ru': '1551646634499117116',
                  'es': '1551648662646562937', 'pt': '1551648743462539294'}
ZONE_FIX_SUMMARIES = {
    'ru': 'Тестового спарринг-бота вырезал нахуй. В обычном онлайне тестовая подмена ввода заблокирована; язык лаунчера теперь меняется сразу.',
    'en': 'The test sparring bot is fucking gone. Scripted test input is blocked in normal online play; the launcher language now switches instantly.',
    'es': 'El bot de sparring de prueba se fue a la mierda. En el online normal se bloquea la sustitución de controles de prueba; el idioma del launcher cambia al instante.',
    'pt': 'O bot de sparring de teste foi pro caralho. No online normal, a substituição dos comandos de teste está bloqueada; o idioma do launcher muda na hora.',
}
STATE = Path(__file__).resolve().parent / 'state.json'
UA = 'DiscordBot (https://github.com/GenryTheFox0/genry-discord-feeds, 1.0)'
TOKEN_PATTERN = re.compile(r'^[A-Za-z0-9._-]+$')


class RequestError(RuntimeError):
    def __init__(self, context, status=None):
        self.status = status
        self.definitely_rejected = status is not None and 400 <= status < 500 and status != 408
        super().__init__('%s: %s' % (context, 'HTTP %s' % status if status else 'network error'))


def request(url, context, headers=None, body=None, method='GET'):
    merged = {'User-Agent': UA, **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        merged['Content-Type'] = 'application/json'
    for attempt in range(4):
        req = urllib.request.Request(url, data=data, method=method, headers=merged)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 3:
                try:
                    seconds = float(json.loads(exc.read() or b'{}').get('retry_after', 2))
                except (ValueError, TypeError):
                    seconds = 2
                time.sleep(min(max(seconds, 0), 15) + 0.5)
                continue
            raise RequestError(context, exc.code) from None
        except (urllib.error.URLError, OSError, TimeoutError):
            # POST may have reached Discord despite a timeout. Never retry here.
            raise RequestError(context) from None
    raise RequestError(context, 429)


def load_release(tag, github_token):
    if not TOKEN_PATTERN.fullmatch(tag):
        raise RuntimeError('Invalid release tag')
    # The zone summaries below describe this specific hotfix. Never reuse them
    # for a different release, where they would make a false announcement.
    if tag != 'v1.0.0-beta.2.0.1':
        raise RuntimeError('This announcement is limited to Iron 6 Beta 2.0.1')
    endpoint = ('https://api.github.com/repos/' + REPO + '/releases/tags/' +
                urllib.parse.quote(tag, safe=''))
    release = request(endpoint, 'GitHub release lookup',
                      headers={'Authorization': 'Bearer ' + github_token,
                               'Accept': 'application/vnd.github+json'})
    if release.get('draft') or not release.get('published_at') or release.get('tag_name') != tag:
        raise RuntimeError('The exact release must already be published')
    expected_url = 'https://github.com/' + REPO + '/releases/tag/' + tag
    if release.get('html_url') != expected_url:
        raise RuntimeError('Unexpected release URL')
    assets = release.get('assets') or []
    by_name = {a.get('name'): a for a in assets}
    expected = ['Iron6Installer-' + tag + '.exe', 'Iron6-PC-Payload-' + tag + '.zip']
    if any(name not in by_name or int(by_name[name].get('size') or 0) <= 0 or
           by_name[name].get('state') != 'uploaded' for name in expected):
        raise RuntimeError('The published release is missing one or both uploaded, nonempty assets')
    if not str(release.get('id', '')).isdigit():
        raise RuntimeError('Release has no numeric ID')
    return {'id': str(release['id']), 'repo': 'Project-Iron-6',
            'name': release.get('name') or tag, 'tag': tag, 'url': expected_url,
            'body': release.get('body') or '', 'pre': bool(release.get('prerelease')),
            'when': release['published_at'],
            'assets': [(a['name'], a['size'], a['browser_download_url']) for a in assets]}


class Discord:
    def __init__(self, bot_token, webhook):
        self.bot_token = bot_token
        self.webhook = webhook
        parsed = urllib.parse.urlsplit(webhook)
        if parsed.scheme != 'https' or parsed.netloc != 'discord.com' or parsed.query or parsed.fragment or not re.fullmatch(
                r'/api(?:/v\d+)?/webhooks/\d+/[A-Za-z0-9._-]+', parsed.path):
            raise RuntimeError('Invalid Discord release webhook')
        self.api = 'https://discord.com/api/v10'
        self.headers = {'Authorization': 'Bot ' + bot_token}

    def bot_get(self, path, context):
        return request(self.api + path, context, headers=self.headers)

    def bot_post(self, path, context, body):
        return request(self.api + path, context, headers=self.headers, body=body, method='POST')

    def preflight(self):
        wh = request(self.webhook, 'release webhook lookup')
        if str(wh.get('guild_id')) != GUILD or str(wh.get('channel_id')) != RELEASES_CHANNEL:
            raise RuntimeError('Release webhook points to a different server or channel')
        self.webhook_id = str(wh.get('id') or '')
        if not self.webhook_id.isdigit():
            raise RuntimeError('Webhook has no numeric identity')
        me = self.bot_get('/users/@me', 'LYLA identity lookup')
        if str(me.get('id')) != BOT or not me.get('bot'):
            raise RuntimeError('Discord token is not the expected LYLA bot')
        self.types = {}
        for channel in [RELEASES_CHANNEL] + list(EXPECTED_ZONES.values()):
            ch = self.bot_get('/channels/' + channel, 'channel lookup ' + channel)
            if str(ch.get('guild_id')) != GUILD:
                raise RuntimeError('Channel is not in the expected Discord server')
            self.types[channel] = ch.get('type')
            # Fail before posting if LYLA cannot inspect message history for recovery.
            self.bot_get('/channels/' + channel + '/messages?limit=1', 'history access ' + channel)

    def find_prior(self, channel, kind, url):
        messages = self.bot_get('/channels/' + channel + '/messages?limit=100', 'recovery history ' + channel)
        matches = []
        for message in messages:
            if kind == 'webhook':
                identity = str(message.get('webhook_id') or '') == self.webhook_id
                references = any(e.get('url') == url or url in (e.get('description') or '')
                                 for e in message.get('embeds', []))
            else:
                identity = str((message.get('author') or {}).get('id') or '') == BOT
                references = url in (message.get('content') or '')
            if identity and references and str(message.get('id', '')).isdigit():
                matches.append(str(message['id']))
        if len(matches) > 1:
            raise RuntimeError('More than one prior announcement found in channel ' + channel)
        return matches[0] if matches else None

    def post_webhook(self, payload):
        return request(self.webhook + '?wait=true', 'release webhook post', body=payload, method='POST')

    def post_zone(self, channel, text):
        return self.bot_post('/channels/' + channel + '/messages', 'LYLA zone post ' + channel,
                             {'content': text, 'allowed_mentions': {'parse': []}})

    def message(self, channel, message_id):
        return self.bot_get('/channels/%s/messages/%s' % (channel, message_id), 'announcement lookup')

    def crosspost(self, channel, message_id):
        return self.bot_post('/channels/%s/messages/%s/crosspost' % (channel, message_id),
                             'announcement crosspost', {})


def save_git_state(state):
    temporary = STATE.with_name('state.json.lyla-iron6.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    os.replace(str(temporary), str(STATE))
    commands = [
        ['git', 'add', '--', str(STATE)],
        ['git', 'commit', '--only', '-m', 'feeds: checkpoint targeted Iron 6 announcement', '--', str(STATE)],
        ['git', 'push', 'origin', 'HEAD:main'],
    ]
    for command in commands:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode:
            # Do not print git output, which can include authenticated remote details.
            raise RuntimeError('Git checkpoint failed at %s (exit %s)' % (command[1], result.returncode))


def save_step(state, persist, slot, value):
    slot.clear()
    slot.update(value)
    persist(state)


def ensure_post(state, persist, discord, record, key, channel, kind, url, send):
    slot = record.setdefault('messages', {}).setdefault(key, {})
    if slot.get('status') == 'sent':
        print('already recorded:', key, channel, slot['id'])
        return slot['id']
    if slot.get('status') == 'pending':
        prior = discord.find_prior(channel, kind, url)
        if not prior:
            raise RuntimeError('Ambiguous pending post in channel %s; inspect Discord before retry' % channel)
        save_step(state, persist, slot, {'status': 'sent', 'channel': channel, 'id': prior})
        print('recovered:', key, channel, prior)
        return prior
    save_step(state, persist, slot, {'status': 'pending', 'channel': channel,
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    try:
        message = send()
    except RequestError as exc:
        if exc.definitely_rejected:
            save_step(state, persist, slot, {'status': 'rejected', 'channel': channel, 'http_status': exc.status})
        raise
    message_id = str(message.get('id') or '')
    if not message_id.isdigit() or str(message.get('channel_id') or '') != channel:
        # POST may already have succeeded. Leave durable pending marker for reconciliation.
        raise RuntimeError('Discord response did not prove the message identity for ' + channel)
    save_step(state, persist, slot, {'status': 'sent', 'channel': channel, 'id': message_id})
    print('posted:', key, channel, message_id)
    return message_id


def run_one(release, config, state, discord, persist):
    if str(config.get('guild')) != GUILD or str(config.get('bot_id')) != BOT:
        raise RuntimeError('Unexpected LYLA server configuration')
    if {lang: str(config['zones'][lang]['news']) for lang in EXPECTED_ZONES} != EXPECTED_ZONES:
        raise RuntimeError('Unexpected LYLA news channels')
    discord.preflight()
    rid = release['id']
    existing = state.get('lyla_iron6_targeted', {}).get(rid)
    seen = state.setdefault('releases', [])
    if existing is None and rid in [str(value) for value in seen]:
        print('Release already recorded by existing feed; no announcement sent:', rid)
        return 'already_seen'
    if existing is None:
        existing = {'tag': release['tag'], 'url': release['url'], 'messages': {}}
        state.setdefault('lyla_iron6_targeted', {})[rid] = existing
        seen.append(rid)
        # Claim before any POST so the normal scheduled feed cannot duplicate it.
        persist(state)
        print('claimed:', rid, release['tag'])
    elif existing.get('tag') != release['tag'] or existing.get('url') != release['url']:
        raise RuntimeError('Saved release metadata does not match')
    elif rid not in [str(value) for value in seen]:
        # Restore the claim if a later state trim removed it while this run was partial.
        seen.append(rid)
        persist(state)

    main_id = ensure_post(state, persist, discord, existing, 'main', RELEASES_CHANNEL, 'webhook', release['url'],
                          lambda: discord.post_webhook(feeds.msg_release(release)))
    cross = existing.setdefault('crosspost', {})
    if discord.types[RELEASES_CHANNEL] == 5 and cross.get('status') != 'sent':
        # A previous successful crosspost can be reconciled from the message flag.
        message = discord.message(RELEASES_CHANNEL, main_id)
        if int(message.get('flags', 0)) & 1:
            save_step(state, persist, cross, {'status': 'sent', 'message_id': main_id})
        else:
            save_step(state, persist, cross, {'status': 'pending', 'message_id': main_id})
            discord.crosspost(RELEASES_CHANNEL, main_id)
            save_step(state, persist, cross, {'status': 'sent', 'message_id': main_id})
        print('crossposted:', RELEASES_CHANNEL, main_id)
    elif discord.types[RELEASES_CHANNEL] != 5 and cross.get('status') != 'not_applicable':
        save_step(state, persist, cross, {'status': 'not_applicable'})

    fields = {'title': release['name'], 'url': release['url'], 'repo': release['repo'], 'name': release['name']}
    for lang, channel in EXPECTED_ZONES.items():
        text = lyla_texts.ZONE_NEWS['release'][lang].format(**fields) + '\n\n' + ZONE_FIX_SUMMARIES[lang]
        if len(text) > 2000:
            raise RuntimeError('Zone announcement exceeds Discord length limit: ' + lang)
        ensure_post(state, persist, discord, existing, 'zone_' + lang, channel, 'bot', release['url'],
                    lambda channel=channel, text=text: discord.post_zone(channel, text))
    if existing.get('complete') is not True:
        existing['complete'] = True
        persist(state)
    print('complete:', rid, release['tag'])
    return 'complete'


def main():
    secrets = {name: os.environ.get(name, '').strip()
               for name in ('TARGET_TAG', 'GITHUB_TOKEN', 'WEBHOOK_RELEASES', 'DISCORD_BOT_TOKEN')}
    missing = [name for name, value in secrets.items() if not value]
    if missing:
        raise RuntimeError('Missing required environment variables: ' + ', '.join(missing))
    if os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise RuntimeError('Dispatch the workflow on the main branch')
    config = json.loads((STATE.parent / 'server.json').read_text(encoding='utf-8'))
    state = json.loads(STATE.read_text(encoding='utf-8'))
    release = load_release(secrets['TARGET_TAG'], secrets['GITHUB_TOKEN'])
    discord = Discord(secrets['DISCORD_BOT_TOKEN'], secrets['WEBHOOK_RELEASES'])
    run_one(release, config, state, discord, save_git_state)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('LYLA announcement stopped:', str(exc), file=sys.stderr)
        sys.exit(1)

