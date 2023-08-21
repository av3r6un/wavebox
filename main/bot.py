from main.functions import config_loader
from discord.ext import commands, tasks
from datetime import datetime as dt
from threading import Thread
from config import Config
import yt_dlp as ydl
import discord
import asyncio
import time
import yaml
import os


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
	async def from_url(cls, url, ffmpeg_options, loop=None, stream=False, volume=0.4):
		loop = loop or asyncio.get_event_loop()
		data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
		if 'entries' in data:
			data = data['entries'][0]
		filename = data['url'] if stream else ytdl.prepare_filename(data)
		return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, volume=volume)


class WaveBox(commands.Cog):
	def __init__(self, b, settings):
		self.bot = b
		self.s = settings
		self.welcome_message = dict()
		self.last_action = dict()
		self.files_conf = config_loader('files')
		self.source = None
		self.player_type = None
		self.now_playing = None
		self.bye_message = None
		self.warn_message = None

	async def _set_source(self, url):
		player = await YTDLSource.from_url(url, self.s.FFMPEG_OPTIONS, volume=self.s.initial_volume)
		return player

	@tasks.loop(minutes=1)
	async def watcher(self):
		if self.last_action.get('time'):
			delta = int(dt.now().timestamp()) - int(self.last_action.get('time'))
			if delta >= self.s.slack_time:
				ctx = await self.bot.get_context(self.now_playing)
				if ctx.voice_client is not None:
					self.bye_message = await ctx.send(self.s.MESSAGES.slack_message)
					await ctx.voice_client.disconnect()
					self.end_player()
					await self.now_playing.delete()
					self.watcher.cancel()
					del self.last_action['time']

	@watcher.before_loop
	async def before_watcher(self):
		await self.bot.wait_until_ready()

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

	async def cleanup_player(self, filename):
		if self.source:
			self.source.cleanup()
		await self.now_playing.delete()
		self.now_playing = None
		try:
			os.remove(filename)
		except FileNotFoundError:
			pass

	def end_player(self, e=None):
		if e:
			print(e)
		if self.player_type == 'main':
			filename = self.source.get_filename()
			asyncio.run_coroutine_threadsafe(self.cleanup_player(filename), self.bot.loop)
		else:
			self.source.cleanup()

	@staticmethod
	def error_embed(text):
		embed = discord.Embed(color=0xff0000, title="Ошибка")
		embed.add_field(name="Причина", value=text)
		return embed

	def clear_static(self):
		files = os.listdir(f'{self.s.STORAGE}/music')
		for file in files:
			os.remove(f'{self.s.STORAGE}/music/{file}')

	@commands.Cog.listener()
	async def on_voice_state_update(self, member, before, after):
		if after.channel:
			if after.channel.id in self.s.channels and not member.bot and before.channel is None:
				message = self.s.MESSAGES.welcome_message.replace('<username>', f'<@{member.id}>')
				mess = await after.channel.send(message, delete_after=self.s.welcome_message_lifetime)
				self.welcome_message.update({f'{member.id}': mess})
		if before.channel is not None and after.channel is None and not member.bot:
			if member.id in self.welcome_message.keys():
				await self.welcome_message[f'{member.id}'].delete()
				del self.welcome_message[f'{member.id}']

	@commands.command(name='voice', help='Starts creating a new voice', aliases=['vc', 'vo'])
	async def voice(self, ctx):
		await ctx.message.delete()
		embed = discord.Embed(color=self.s.embed_color, title='Правила добавления голосового файла')
		embed.add_field(name='Размер', value='Не более 512кб', inline=True)
		embed.add_field(name='Продолжительность', value='Не более 5 секунд', inline=True)
		embed.add_field(name='Формат', value='mp3', inline=True)
		embed.add_field(name='Название', value='Указывается в тексте сообщения с файлом', inline=True)
		await ctx.send(self.s.MESSAGES.voice_new_file, embed=embed)
		attachment_m = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.attachments)
		try:
			content, filename = self.prettify_info(attachment_m.attachments)
			await content.save(fp=f'main/static/voices/{filename}')
			self.files_conf.content[filename] = attachment_m.content
			self.save_conf('files_conf')
			await ctx.send(self.s.MESSAGES.voice_file_uploaded)
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
					await ctx.send(self.s.MESSAGES.not_connected_user)
			elif ctx.voice_client.is_playing():
				ctx.voice_client.pause()
			if sound_name in self.files_conf.content.values():
				for filename, sound in self.files_conf.content.items():
					if sound_name == sound:
						self.player_type = 'voice'
						ctx.voice_client.play(discord.FFmpegPCMAudio(f'main/static/voices/{filename}', **self.s.FFMPEG_OPTIONS),
											  after=lambda e: self.end_player(e) if e else None)
						await ctx.send(self.s.MESSAGES.now_playing.replace('<track>', sound),
									   delete_after=self.s.system_message_lifetime)
			else:
				await ctx.send(self.s.MESSAGES.voice_not_found.replace('<sound>', sound_name),
							   delete_after=self.s.system_message_lifetime)
		else:
			await ctx.send('Укажите название файла. Доступные файлы сейчас:\n' + "\n - ".join(self.files_conf.content.values()))

	@commands.command(name='join', help='Bot joins current voice channel.', aliases=['j'])
	async def join(self, ctx):
		await ctx.message.delete()
		if self.bye_message:
			await self.bye_message.delete()
			self.bye_message = None
		if self.warn_message:
			await self.warn_message.delete()
			self.warn_message = None
		channel = ctx.message.author.voice.channel
		if ctx.voice_client is not None:
			return await ctx.voice_client.move_to(channel)
		await channel.connect()
		self.watcher.start()

	@commands.command(name='play', help='(url) Plays given url in voice channel.', aliases=['p'])
	async def play(self, ctx, *, url=None):
		await ctx.message.delete()
		self.player_type = 'main'
		self.last_action['time'] = dt.now().timestamp()
		if url:
			async with ctx.typing():
				try:
					self.source = await self._set_source(url)
					ctx.voice_client.play(self.source, after=lambda e: self.end_player(e))
					self.now_playing = await ctx.send(self.s.MESSAGES.now_playing.replace('<track>', self.source.title))
				except ydl.DownloadError:
					self.now_playing = None
					await ctx.send('Ошибка скачивания файла')
		else:
			if ctx.voice_client is not None:
				ctx.voice_client.resume()

	@commands.command(name='stream', help='Streams given url', aliases=['s'])
	async def stream(self, ctx, *, url):
		await ctx.message.delete()
		self.player_type = 'stream'
		self.last_action['time'] = dt.now().timestamp()
		async with ctx.typing():
			self.source = await self._set_source(url)
			ctx.voice_client.play(self.source, after=lambda e: self.end_player(e))
		self.now_playing = await ctx.send(self.s.MESSAGES.now_playing.replace('<track>', self.source.title))

	@commands.command(name='volume', help='(0-100) Bot sets volume.', aliases=['v', 'vol'])
	async def volume(self, ctx, *, user_volume: int):
		await ctx.message.delete()
		self.last_action['time'] = dt.now().timestamp()
		if ctx.voice_client is None:
			return await ctx.send(self.s.MESSAGES.not_connected_bot)
		volume = user_volume / 100
		ctx.voice_client.source.volume = volume
		await ctx.send(self.s.MESSAGES.volume_change.replace('<volume>', str(user_volume)),
					   delete_after=self.s.system_message_lifetime)

	@commands.command(name='pause', help='Pauses current track', aliases=['ps'])
	async def pause(self, ctx):
		await ctx.message.delete()
		self.last_action['time'] = dt.now().timestamp()
		if ctx.voice_client is not None:
			ctx.voice_client.pause()

	@commands.command(name='stop', help='Stops playing.', aliases=['st'])
	async def stop(self, ctx):
		await ctx.message.delete()
		self.last_action['time'] = dt.now().timestamp()
		if ctx.voice_client is not None:
			ctx.voice_client.stop()
		else:
			print('Voice client empty!')
		self.end_player()

	@commands.command(name='clear', help='Clears chat from all message (limit=100).', hidden=True, aliases=['cl'])
	async def clear(self, ctx):
		if ctx.channel.id in self.s.channels:
			deleted = await ctx.channel.purge(limit=100)
			await ctx.send(f'<@{ctx.author.id}> deleted {len(deleted)} messages.', delete_after=self.s.system_message_lifetime)

	@commands.command(name='emoji', hidden=True)
	async def emoji(self, ctx, *, emoji):
		await ctx.send(f'{emoji}')

	@commands.command(name='leave', help='Bot leaves current voice channel.', aliases=['l'])
	async def leave(self, ctx):
		await ctx.message.delete()
		await ctx.voice_client.disconnect()
		await ctx.send(self.s.MESSAGES.farewell_message, delete_after=self.s.system_message_lifetime)
		self.clear_static()
		self.end_player()
		self.watcher.stop()

	@play.before_invoke
	@stream.before_invoke
	async def ensure_voice(self, ctx):
		if ctx.voice_client is None:
			if ctx.author.voice:
				self.warn_message = await ctx.send(self.s.MESSAGES.not_connected_bot)
			else:
				self.warn_message = await ctx.send(self.s.MESSAGES.not_connected_user)
		elif ctx.voice_client.is_playing():
			ctx.voice_client.stop()

