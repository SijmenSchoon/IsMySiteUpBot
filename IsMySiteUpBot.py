import os
from aiotg import Bot
import requests
import urllib
import socket
import json
import threading
import asyncio
import datetime
import aiocron
import re

DB_VERSION = '0.2'

bot = Bot(os.environ["API_TOKEN"])

def save_urls():
    dump = json.dumps(db)
    with open('urls.json', 'w') as f:
        f.write(dump)

def upgrade_db():
    obj = None
    with open('urls.json', 'r') as f:
        s = f.read()
        obj = json.loads(s)

    try:
        print(obj['db']['version'])
        if obj['db']['version'] == DB_VERSION:
            return False
    except:
        pass

    if 'db' not in obj and 'urls' not in obj and list(obj)[0].isdigit():
        # Upgrade 0.0 to 0.1
        db = { 'db': { 'version': '0.1' }, 'urls': obj }
        obj = db

    if obj['db']['version'] == '0.1':
        db = { 'db': { 'version': '0.2' }, 'users': {} }
        # Upgrade 0.1 to 0.2
        for user in obj['urls']:
            db['users'][user] = {}
            for url in obj['urls'][user]:
                db['users'][user][url] = { 'total': { 'tests': 0, 'tests_up': 0, 'tests_up_spree': 0 }, 'by_day': {} }
        obj = db

    if not obj['db']['version'] == DB_VERSION:
        raise Exception('db version not updated')

    with open('urls.json', 'w') as f:
        s = json.dumps(obj)
        f.write(s)
    return True

def load_urls():
    try:
        if upgrade_db():
            print('upgraded database to %s' % DB_VERSION)
    except Exception as e:
        print('couldn\'t upgrade database: %s' % e)

    try:
        with open('urls.json', 'r') as f:
            global db
            db = json.loads(f.read())
    except Exception as e:
        print('couldn\'t load database: %s' % e)
        return

@bot.command(r'/start')
def start(chat, match):
    print('%s: %s' % (chat.sender, match.string))
    return chat.send_text('''
Hi there! I'm here for checking if your sites are up.
Every fifteen minutes, I'll try loading your URLs, and if I don't succeed, I'll tell you.

To get started, add an url using /add_url <url>. If you want to list your URLs, send /urls.

If you want to trigger a test manually, send /test_urls!
        ''')

@bot.command(r'/add_url (.+)')
def add_url(chat, match):
    print('%s: %s' % (chat.sender, match.string))
    url = match.group(1)
    id = str(chat.id)
    if id not in db['users']:
        db['users'][id] = {}

    if not urllib.parse.urlparse(url).scheme:
        url = 'http://' + url

    regex = re.compile(
        r'^(?:http|ftp)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
        r'localhost|' #localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    if not regex.match(url):
        return chat.send_text('That URL is invalid!')

    if url in db['users'][id]:
        return chat.send_text('I\'m already tracking that URL!')

    if len(db['users'][id]) > 4:
        return chat.send_text('You can only make me track 5 URLs at maximum. Please remove an URL to add a new one (see /help).')

    db['users'][id][url] = { 'total': { 'tests': 0, 'tests_up': 0, 'tests_up_spree': 0 }, 'by_day': {} }

    return chat.send_text('Added the URL %s!' % url, disable_web_page_preview=True)

def test(url):
    try:
        resp = requests.head(url, allow_redirects=True)
        if not resp.ok:
            resp = requests.get(url, allow_redirects=True)
        return resp
    except requests.exceptions.ConnectionError as e:
        return 'connection error'
    except Exception as e:
        return 'unknown error'

@bot.command(r'/test_urls')
async def test_urls(chat, match):
    print('%s: %s' % (chat.sender, match.string))
    id = str(chat.id)
    broken_urls = []

    msg_id = (await chat.send_text('Testing...'))['result']['message_id']

    count = len(db['users'][id])
    curr = 0
    for url in db['users'][id]:
        await chat.edit_text(msg_id, 'Testing... (%.0f%%)' % (curr / count * 100))
        resp = test(url)
        if not resp.ok:
            broken_urls.append((url, resp.status_code, resp.reason))
        curr += 1
    await chat.edit_text(msg_id, 'Testing... (100%)')

    if len(broken_urls) > 0:
        msg = 'Houston, we\'ve had a problem. '
        msg += 'This URL doesn\'t work:\n' if len(broken_urls) == 1 else 'These URLs don\'t work:\n'

        for tup in broken_urls:
            msg += ' - %s (%d %s)\n' % tup
        await chat.send_text(msg, disable_web_page_preview=True)
    else:
        await chat.send_text('Everything went a-ok!')

@bot.command(r'/del_url (.+)')
def del_url_param(chat, match):
    print('%s: %s' % (chat.sender, match.string))
    id = str(chat.id)

    try:
        url = db['users'][id][match.group(1)]

        del(db['users'][id][match.group(1)])
        if url['total']['tests'] == 0:
            return chat.send_text('Successfully removed %s.' % match.group(1), disable_web_page_preview=True)
        else:
            uptime = url['total']['tests_up_spree'] * 0.25
            reliability = url['total']['tests_up'] / url['total']['tests']
            return chat.send_text('Successfully removed %s. Its highest recorded uptime was %d hours and its reliability was %.0f%%.' % (match.group(1), uptime, reliability * 100), disable_web_page_preview=True)

    except KeyError:
        return chat.send_text('I\'m not tracking that URL at the moment! Make sure you\'re entering the entire URL!')

@bot.command(r'/del_url')
def del_url(chat, match):
    print('%s: %s' % (chat.sender, match.string))
    id = str(chat.id)

    try:
        keyboard = { 'inline_keyboard': [] }
        for url in db['users'][id]:
            keyboard['inline_keyboard'].append([ {
                    'text': url,
                    'callback_data': json.dumps({ 'action': 'del_url', 'url': url })
                } ])
    except KeyError:
        return chat.send_text('I\'m currently not tracking any URLs for you. Use /add_url <url> to add one.')

    return chat.send_text('Select an URL to delete:', reply_markup=json.dumps(keyboard))

@bot.command(r'/urls')
def send_urls(chat, match):
    print('%s: %s' % (chat.sender, match.string))
    id = str(chat.id)
    if id not in db['users'] or len(db['users'][id]) == 0:
        return chat.send_text('I\'m currently not tracking any URLs for you. Use /add_url <url> to add one.')

    msg = 'I\'m tracking the following URLs for you:\n'
    for url in db['users'][id]:
        msg += ' - %s\n' % url
    return chat.send_text(msg, disable_web_page_preview=True)

@bot.command(r'/stop')
def stop(chat, match):
    print('%s: %s' % (chat.sender, match.string))
    id = str(chat.id)
    try:
        del db['users'][id]
    except IndexError:
        pass
    return chat.send_text('Okay, deleted all your data. See you!')

@bot.callback
async def callback(chat, cq):
    print('%s: callback: %s' % (chat.sender, cq.data))

    obj = {}
    try:
        obj = json.loads(cq.data)
    except Exception as e:
        print('error processing callback: %s' % e)

    try:
        action = obj['action']
        if action == 'del_url':
            keyboard = { 'inline_keyboard': [] }

            await del_url_param(chat, re.match('(.+)', obj['url']))
            for url in db['users'][str(chat.id)]:
                keyboard['inline_keyboard'].append([ {
                        'text': url,
                        'callback_data': json.dumps({ 'action': 'del_url', 'url': url })
                    } ])

                await chat.edit_text(chat.message['message_id'], 'Select an URL to delete:', markup=keyboard)

            await cq.answer()
    except KeyError as e:
        print('error processing callback: %r' % e)

async def hourly_test():
    while True:
        await aiocron.crontab('*/15 * * * *').next()
        print(datetime.datetime.now())
        for id in db['users']:
            broken_urls = []
            for url in db['users'][id]:
                resp = test(url)

                db['users'][id][url]['total']['tests'] += 1
                if not resp.ok:
                    broken_urls.append((url, resp.status_code, resp.reason))
                    db['users'][id][url]['total']['tests_up_spree'] = 0
                else:
                    db['users'][id][url]['total']['tests_up'] += 1
                    db['users'][id][url]['total']['tests_up_spree'] += 1

            if len(broken_urls) > 0:
                msg = 'Houston, we\'ve had a problem. '
                msg += 'This URL doesn\'t work:\n' if len(broken_urls) == 1 else 'These URLs don\'t work:\n'
                for tup in broken_urls:
                    msg += ' - %s (%d %s)\n' % tup
                await bot.send_message(id, msg, disable_web_page_preview=True)
                print('Something went wrong for %s' % id)

async def save_loop():
    while True:
        await aiocron.crontab('* * * * *').next()
        save_urls()

if __name__ == '__main__':
    load_urls()
    asyncio.ensure_future(hourly_test())
    asyncio.ensure_future(save_loop())
    bot.run()
