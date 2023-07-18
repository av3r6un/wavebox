from munch import DefaultMunch
import ruamel.yaml
import yaml
import sys
import os


class Settings:
	FFMPEG_OPTIONS = None
	MESSAGES = None

	def __init__(self):
		self.existing_settings = None
		self._read_settings()

	def _read_settings(self):
		if os.path.exists('configs/settings.yaml'):
			with open('configs/settings.yaml', 'r', encoding='utf-8') as file:
				setts = yaml.safe_load(file)
			self.existing_settings = setts
			self.__dict__.update(DefaultMunch.fromDict(setts, default=object()))
			self.MESSAGES = DefaultMunch.fromDict(setts['messages'], default=object())
		else:
			print('Settings.yaml not found')
			sys.exit(1)

	def set_settings(self, new_settings: dict):
		self.__dict__.update(new_settings)
		with open('configs/settings.yaml', 'w', encoding='utf-8') as file:
			yaml_data = dumper.load(self.__dict__)
			dumper.dump(yaml_data, file)
