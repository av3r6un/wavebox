from discord.ext import commands
from discord import Intents
from bot import WaveBox
from config import Config
import asyncio


intents = Intents.default()
intents.message_content = True

bot = commands.Bot(
	command_prefix=commands.when_mentioned_or('-'),
	description=Config.BOT_DESCR,
	intents=intents
)


@bot.event
async def on_ready():
	print(f'Logged in as {bot.user}!')
	print('-'*40)


async def main():
	async with bot:
		await bot.add_cog(WaveBox(bot))
		await bot.start(Config.TOKEN)


asyncio.run(main())