from main.functions import config_loader
from discord.ext import commands
from threading import Thread
from config import Config
import yt_dlp as ydl
import discord
import asyncio
import time
import yaml
import os


ffmpeg_options = {
	'options': '-vn',
	'before_options': '-loglevel quiet -y'
}

ytdl = ydl.YoutubeDL(config_loader('ytdl_config').content)


class YTDLSource(discord.PCMVolumeTransformer):
	def __init__(self, source, *, data, volume=0.4):
		super().__init__(source, volume)
		self.data = data
		self.title = data.get('title')
		self.url = data.get('url')

	def get_filename(self):
		return ytdl.prepare_filename(self.data)

	@classmethod
	async def from_url(cls, url, *, loop=None, stream=False):
		loop = loop or asyncio.get_event_loop()
		data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
		if 'entries' in data:
			data = data['entries'][0]
		filename = data['url'] if stream else ytdl.prepare_filename(data)
		return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class WaveBox(commands.Cog):
	def __init__(self, b):
		self.bot = b
		self.welcome_message = dict()
		self.files_conf = config_loader('files')
		self.player = None
		self.now_playing = None

	def prettify_info(self, attachment: list):
		if len(attachment) > 1:
			raise ValueError('Too much files in one attachment.')
		given_fn = attachment[0].filename
		if given_fn in self.files_conf.content.keys():
			raise FileExistsError(f'File {given_fn} already exists.')
		return attachment[0], given_fn

	def save_conf(self, name):
		conf_file = self.__dict__[name]
		with open(f'configs/{conf_file.filename}.yaml', 'w', encoding='utf-8') as file:
			yaml.safe_dump(conf_file.content, file, encoding='utf-8', allow_unicode=True)

	@staticmethod
	def end_playing(ctx, e=None):
		if ctx.voice_client:
			ctx.voice_client.resume()
		# asyncio.run_coroutine_threadsafe(self.leave_channel(ctx), self.bot.loop)
		if e:
			print(e)

	@staticmethod
	def remove_file(filename):
		time.sleep(10)
		try:
			os.remove(filename)
		except FileNotFoundError:
			pass

	def end_player(self, e=None):
		filename = self.player.get_filename()
		asyncio.run_coroutine_threadsafe(self.now_playing.delete(), self.bot.loop)
		Thread(target=self.remove_file, args=(filename,)).start()
		if e:
			print(e)

	@staticmethod
	async def leave_channel(ctx):
		await ctx.voice_client.disconnect()

	@staticmethod
	def error_embed(text):
		embed = discord.Embed(color=0xff0000, title="Ошибка")
		embed.add_field(name="Причина", value=text)
		return embed

	@commands.Cog.listener()
	async def on_voice_state_update(self, member, before, after):
		if after.channel:
			if after.channel.id in Config.CHANNELS and member.id != Config.BOT_ID:
				self.welcome_message[member.id] = await after.channel.send(
					f'Welcome, <@{member.id}>!\nTo discover bot function send -help.'
				)
		if before.channel is not None and after.channel is None and member.id != Config.BOT_ID:
			if member.id in self.welcome_message.keys():
				await self.welcome_message[member.id].delete()
				del self.welcome_message[member.id]

	@commands.command(name='voice', help='Starts creating a new voice', aliases=['vc', 'vo'])
	async def voice(self, ctx):
		await ctx.message.delete()
		embed = discord.Embed(color=0x22b1f7, title='Правила добавления голосового файла')
		embed.add_field(name='Размер', value='Не более 512кб', inline=True)
		embed.add_field(name='Продолжительность', value='Не более 5 секунд', inline=True)
		embed.add_field(name='Формат', value='mp3', inline=True)
		embed.add_field(name='Название', value='Указывается в тексте сообщения с файлом', inline=True)
		await ctx.send('Добавить новый файл?', embed=embed)
		attachment_m = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.attachments)
		try:
			content, filename = self.prettify_info(attachment_m.attachments)
			await content.save(fp=f'main/static/voices/{filename}')
			self.files_conf.content[filename] = attachment_m.content
			self.save_conf('files_conf')
			await ctx.send('Файл успешно загружен!')
		except Exception as _ex:
			await ctx.send(embed=self.error_embed(str(_ex)))

	@commands.command(name='panel', help='Plays pre-downloaded sounds.', aliases=['pn', 'k'])
	async def panel(self, ctx, *, sound_name=None):
		await ctx.message.delete()
		if sound_name:
			if ctx.voice_client is None:
				if ctx.author.voice:
					await ctx.author.voice.channel.connect()
				else:
					await ctx.send("You are not connected to a voice channel.")
			elif ctx.voice_client.is_playing():
				ctx.voice_client.pause()
			if sound_name in self.files_conf.content.values():
				for filename, sound in self.files_conf.content.items():
					if sound_name == sound:
						ctx.voice_client.play(discord.FFmpegPCMAudio(f'main/static/voices/{filename}', **ffmpeg_options),
											  after=lambda e: self.end_playing(ctx, e))
						await ctx.send(f'Проигрываю: {sound}', delete_after=5.0)
			else:
				await ctx.send('Звук не найден!', delete_after=5.0)
		else:
			await ctx.send('Укажите название файла. Доступные файлы сейчас:\n' + "\n - ".join(self.files_conf.content.values()))

	@commands.command(name='join', help='Bot joins current voice channel.', aliases=['j'])
	async def join(self, ctx):
		channel = ctx.message.author.voice.channel
		if ctx.voice_client is not None:
			return await ctx.voice_client.move_to(channel)
		await channel.connect()
		if self.welcome_message[ctx.author.id]:
			await self.welcome_message[ctx.author.id].delete()

	@commands.command(name='play', help='(url) Plays given url in voice channel.', aliases=['p'])
	async def play(self, ctx, *, url=None):
		await ctx.message.delete()
		if url:
			async with ctx.typing():
				self.player = await YTDLSource.from_url(url, loop=self.bot.loop)
				ctx.voice_client.play(self.player, after=lambda e: self.end_player(e))
			self.now_playing = await ctx.send(f'Now playing: {self.player.title}')
		else:
			if ctx.voice_client is not None:
				ctx.voice_client.resume()

	@commands.command(name='stream', help='Streams given url', aliases=['s'])
	async def stream(self, ctx, *, url):
		await ctx.message.delete()
		async with ctx.typing():
			player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
			ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
		await ctx.send(f'Now playing: {player.title}')

	@commands.command(name='volume', help='(0-100) Bot sets volume.', aliases=['v', 'vol'])
	async def volume(self, ctx, *, user_volume: int):
		await ctx.message.delete()
		if ctx.voice_client is None:
			return await ctx.send('Not connected to a voice channel.')
		volume = user_volume / 100
		ctx.voice_client.source.volume = volume
		await ctx.send(f'Changed volume to {user_volume}%', delete_after=4.0)

	@commands.command(name='pause', help='Pauses current track', aliases=['ps'])
	async def pause(self, ctx):
		await ctx.message.delete()
		if ctx.voice_client is not None:
			ctx.voice_client.pause()

	@commands.command(name='stop', help='Stops playing.', aliases=['st'])
	async def stop(self, ctx):
		await ctx.message.delete()
		if ctx.voice_client is not None:
			ctx.voice_client.stop()
		else:
			print('Voice client empty!')
		self.end_player()

	@commands.command(name='clear', help='Clears chat from all message (limit=100).', hidden=True, aliases=['cl'])
	async def clear(self, ctx):
		if ctx.channel.id in Config.CHANNELS:
			deleted = await ctx.channel.purge(limit=100)
			await ctx.send(f'<@{ctx.author.id}> deleted {len(deleted)} messages.', delete_after=4.0)

	@commands.command(name='leave', help='Bot leaves current voice channel.', aliases=['l'])
	async def leave(self, ctx):
		await ctx.message.delete()
		await ctx.voice_client.disconnect()
		await ctx.send('Bye!', delete_after=4.0)

	@play.before_invoke
	@stream.before_invoke
	async def ensure_voice(self, ctx):
		if ctx.voice_client is None:
			if ctx.author.voice:
				await ctx.author.voice.channel.connect()
			else:
				await ctx.send("You are not connected to a voice channel.")
		elif ctx.voice_client.is_playing():
			ctx.voice_client.stop()

