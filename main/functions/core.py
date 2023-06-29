import yaml
import os


class ConfigLoader:
	def __init__(self, conf_file: str):
		self.filename = conf_file
		self.content = self.config_loader()

	def config_loader(self):
		if os.path.exists(f'configs/{self.filename}.yaml'):
			with open(f'configs/{self.filename}.yaml', 'r', encoding='utf-8') as file:
				return yaml.safe_load(file)
		else:
			return dict()


def config_loader(conf_file):
	return ConfigLoader(conf_file)
