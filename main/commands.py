from main.functions import ErrorWatcher
from datetime import datetime as dt
from discord.ext import commands
from discord.utils import get
import discord
import random


class Commands:
	def __init__(self, bot: commands.Bot, settings):
		self.bot = bot
		self.s = settings
		self.guild = discord.Object(id=self.s.guild_with_commands)
		self.secondary_guild = discord.Object(id=self.s.secondary_guild)
		self.create_commands()

	def create_commands(self):
		@self.bot.tree.command(description="Return info about this channel")
		@discord.app_commands.describe(
			timedelta="Time delta to print errors. 0 - last, 1 - this day, 2 - the whole list. Default 0"
		)
		async def audit(interaction: discord.Interaction, timedelta: int = 0):
			await interaction.response.send_message(embed=self.create_embed_for_errors(timedelta), ephemeral=True)

		@self.bot.tree.command(description="Flips the coin", guild=self.secondary_guild)
		async def coinflip(interaction: discord.Interaction):
			coinsides = ['eagle_coin', 'tails_coin']
			emoji_ids = {'tails_coin': 1141893746879909909, 'eagle_coin': 1141893802181791894}
			coin_sides = {'eagle_coin': 'Орёл', 'tails_coin': 'Решка'}
			choice = random.choice(coinsides)
			message = f'<:{choice}:{emoji_ids[choice]}> (`{coin_sides[choice]}`)'
			await interaction.response.send_message(message)

		@self.bot.tree.command(description="Rolls the dice", guild=self.secondary_guild)
		@discord.app_commands.describe(
			dice_range="Maximum value that can be. Default 6"
		)
		async def roll(interaction: discord.Interaction, dice_range: int = 6):
			number = random.randint(1, dice_range)
			choice = '{:0>3d}'.format(number)
			await interaction.response.send_message(f'> `{choice}`')

	def create_embed_for_errors(self, timedelta):
		watcher = ErrorWatcher()
		watcher.start()
		watcher.join()
		errors = watcher.result if watcher.completed else []
		if errors:
			if timedelta == 0:
				embed_title = 'Последняя ошибка'
				current_error = [errors[-1]]
			elif timedelta == 1:
				embed_title = 'Ошибки за сегодня'
				current_error = [
					error if dt.strptime(error['timestamp'], '%d-%m-%Y %H:%M:%S').day == dt.now().day else None for error in errors
				]
			else:
				embed_title = 'Ошибки WaveBox с момента запуска'
				current_error = errors
			embed = discord.Embed(color=self.s.embed_color, title=embed_title)
			for error in current_error:
				embed.add_field(name="Время", value=error['timestamp'])
				embed.add_field(name="Модуль", value=error['name'])
				embed.add_field(name="Ошибка", value=error['message'])
				embed.add_field(name="", value="", inline=False)
				embed.add_field(name="", value="", inline=False)
		else:
			dt_now = dt.now()
			embed = discord.Embed(color=self.s.embed_color, title="Ошибок не обнаружено")
			embed.add_field(name="Дата", value=dt_now.strftime("%d.%m.%Y"))
			embed.add_field(name="Время", value=dt_now.strftime("%H:%M"))
		return embed
