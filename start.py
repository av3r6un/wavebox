from main import WaveBox, Commands
from discord.ext import commands
from configs import Settings
from config import Config
import asyncio
import discord
import logging

formatter = logging.Formatter('[{asctime}] [{levelname:<5}] {name}: {message}', '%d-%m-%Y %H:%M:%S', style='{')
handler = logging.FileHandler(filename='discord-error.log', encoding='utf-8', mode='w')

settings = Settings()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(
	command_prefix=commands.when_mentioned_or('-'),
	description=Config.BOT_DESCR,
	intents=intents,
)


@bot.event
async def on_ready():
	print(f'Logged in as {bot.user}! (id: {bot.user.id})')
	print('-'*40)
	cmds = Commands(bot, settings)
	bot.tree.copy_global_to(guild=cmds.guild)
	await bot.tree.sync(guild=cmds.guild)


async def main():
	async with bot:
		await bot.add_cog(WaveBox(bot, settings))
		await bot.start(Config.TOKEN, )


discord.utils.setup_logging(handler=handler, level=logging.ERROR, formatter=formatter)


asyncio.run(main())
