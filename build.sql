CREATE TABLE IF NOT EXISTS prefixes (
	guild_id integer PRIMARY KEY,
	prefix text DEFAULT "!"
);

CREATE TABLE IF NOT EXISTS bot_channels (
	channel_id integer PRIMARY KEY,
	guild_id integer DEFAULT NULL
);