# first-discord-bot
My first discord bot

Very WIP

## About
Database is SQLite accessed through aiosqlite.
All commands are limited to configurable 'bot channels' so the bot is only usable in specified channels (my design choice, may change this)
(small) Multi server functionality (bots in many servers do not, and should not, use SQLite).

## Current cogs and their features

| Cog name | Feature |
|--|--|
| musicquiz| (The coolest one) A [binb](https://github.com/lpinca/binb) clone in discord based on spotify.
| notes | Return text from an associated key phrase |
| decide | Randomly select items from a group |
| dad | Respond to "I'm..." with "Hi...I'm [bot name]"
| moderation | Configure prefix and bot channels per-server
| botconfig | Load/unload/reload cogs and rename bot

## Running the bot
Download source cd to directory and install requirements

    python3 -m pip install -r requirements.txt
Then run the bot

    python3 bot.py
