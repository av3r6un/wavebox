import discord
from functions import config_loader
from discord.ext import commands
from discord.utils import get
from config import Config
import yt_dlp as ydl
import asyncio


ffmpeg_options = {
	'options': '-vn',
	'before_options': '-loglevel quiet -y'
}

ytdl = ydl.YoutubeDL(config_loader('ytdl_config'))


class YTDLSource(discord.PCMVolumeTransformer):
	def __init__(self, source, *, data, volume=0.4):
		super().__init__(source, volume)
		self.data = data
		self.title = data.get('title')
		self.url = data.get('url')

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
				player = await YTDLSource.from_url(url, loop=self.bot.loop)
				ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
			await ctx.send(f'Now playing: {player.title}')
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
		await ctx.voice_client.stop()

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

