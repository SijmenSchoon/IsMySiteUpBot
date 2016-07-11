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

bot = Bot(os.environ["API_TOKEN"])

urls = {}

def save_urls():
    with open('urls.json', 'w') as f:
        f.write(json.dumps(urls) + '\n')

def load_urls():
    try:
        with open('urls.json', 'r') as f:
            s = f.read()
            global urls
            urls = json.loads(s)
    except FileNotFoundError as e:
        pass

@bot.command(r'/start')
def start(chat, match):
    return chat.send_text('''
Hi there! I'm here for checking if your sites are up.
Every hour, I'll try loading your URLs, and if I don't succeed, I'll tell you.

To get started, add an url using /add_url <url>. If you want to list your URLs, send /urls.

If you want to trigger a test manually, send /test_urls!
        ''')

@bot.command(r'/add_url (.+)')
def add_url(chat, match):
    url = match.group(1)
    id = str(chat.id)
    if id not in urls:
        urls[id] = []

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

    if url in urls[id]:
        return chat.send_text('I\'m already tracking that URL!')

    if len(urls[id]) > 4:
        return chat.send_text('You can only make me track 5 URLs at maximum. Please remove an URL to add a new one (see /help).')

    urls[id].append(url)
    #save_urls()

    print('%s added the url %s' % (chat.sender, url))
    return chat.send_text('Added the URL %s!' % url, disable_web_page_preview=True)

def test(url):
    try:
        resp = requests.head(url, allow_redirects=True)
        return resp.status_code
    except requests.exceptions.ConnectionError as e:
        return 'connection error'
    except Exception as e:
        return 'unknown error'

@bot.command(r'/test_urls')
async def test_urls(chat, match):
    id = str(chat.id)
    broken_urls = []

    print('%s requested a test of his URLs' % chat.sender)

    msg_id = (await chat.send_text('Testing...'))['result']['message_id']
    for i in range(len(urls[id])):
        url = urls[id][i]
        await chat.edit_text(msg_id, 'Testing... (%.0f%%)' % ((i) / len(urls[id]) * 100))
        resp = test(url)
        if resp != 200:
            broken_urls.append((url, resp))
    await chat.edit_text(msg_id, 'Testing... (100%)')

    if len(broken_urls) > 0:
        msg = 'Houston, we\'ve had a problem. '
        msg += 'This URL doesn\'t work:\n' if len(broken_urls) == 1 else 'These URLs don\'t work:\n'

        for tup in broken_urls:
            msg += ' - %s (%s)\n' % tup
        await chat.send_text(msg, disable_web_page_preview=True)
    else:
        await chat.send_text('Everything went a-ok!')

@bot.command(r'/urls')
def send_urls(chat, match):
    id = str(chat.id)
    if id not in urls or len(urls[id]) == 0:
        return chat.send_text('I\'m currently not tracking any URLs for you. Use /add_url <url> to add one.')

    msg = 'I\'m tracking the following URLs for you:\n'
    for i in range(len(urls[id])):
        url = urls[id][i]
        msg += ' - %s (/del_%d, /test_%d)\n' % (url, i, i)
    return chat.send_text(msg, disable_web_page_preview=True)

@bot.command(r'/del_(.+)')
def del_url_id(chat, match):
    id = str(chat.id)
    try:
        url = urls[id][int(match.group(1))]
        del urls[id][int(match.group(1))]
        #save_urls()
        return chat.send_text('Deleted %s' % url)
    except IndexError:
        pass

@bot.command(r'/test_(.+)')
def test_url_id(chat, match):
    id = str(chat.id)
    url = urls[id][int(match.group(1))]
    return chat.send_text('Got a %s!' % test(url))

@bot.command(r'/stop')
def stop(chat, match):
    id = str(chat.id)
    try:
        del urls[id]
    except IndexError:
        pass
    return chat.send_text('Okay, deleted all your data. See you!')

async def hourly_test():
    while True:
        await aiocron.crontab('*/15 * * * *').next()
        print(datetime.datetime.now())
        for id in urls:
            broken_urls = []
            for url in urls[id]:
                resp = test(url)
                if resp != 200:
                    broken_urls.append((url, resp))

            if len(broken_urls) > 0:
                msg = 'Houston, we\'ve had a problem. '
                msg += 'This URL doesn\'t work:\n' if len(broken_urls) == 1 else 'These URLs don\'t work:\n'
                for tup in broken_urls:
                    msg += ' - %s (%s)\n' % tup
                await bot.send_message(id, msg, disable_web_page_preview=True)
                print('Something went wrong for %s' % id)

async def save_loop():
    while True:
        await aiocron.crontab('* * * * *').next()
        print('Saving...')
        save_urls()
        print('Done.')

if __name__ == '__main__':
    load_urls()
    asyncio.ensure_future(hourly_test())
    asyncio.ensure_future(save_loop())
    bot.run()
