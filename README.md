# IsMySiteUpBot

Pretty poorly written Telegram bot that checks if a site is up. Sadly, the
concept does not work well in practice, and the bot became really prone to
abuse.

Just putting it up on Github so you can learn from my mistakes.

## Installation

* Make sure you have Python 3.5 or newer.
* `git clone` the thing.
* Run `virtualenv venv -p python3`. If it doesn't venv, run `pip3 install venv` then try again.
* Activate your `venv` thing with `. venv/bin/activate`.
* Install things this thing depends on with `pip install -r requirements.txt`.
* Create an `urls.json` with just `{}` so json can do its thing.
* Beg [@BotFather](https://t.me/BotFather) for an API token.
* Run the thing with `API_TOKEN=<token> python IsMySiteUpBot.py`.

Have fun!
