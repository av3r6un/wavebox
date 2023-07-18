from threading import Thread
import yaml
import os
import re


class ErrorWatcher(Thread):
	def __init__(self):
		super(ErrorWatcher, self).__init__()
		self.completed = False
		self.result = None

	def extract_error_info(self):
		error_info = []
		result = []
		pattern = r'^\[\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2}\].*\n$'
		with open('discord-error.log', 'r', encoding='utf-8') as file:
			content = file.readlines()
		for line in content:
			match = re.match(pattern, line)
			if match:
				error_info.append(match.group().strip())
		for error in error_info:
			patt = r'\[(\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2})\] \[([A-Z]+)\] (.*?): (.*)$'
			match = re.match(patt, error)
			if match:
				result.append({
					'timestamp': match.group(1),
					'name': match.group(3),
					'message': match.group(4),
				})
		self.result = result
		self.completed = True

	def run(self):
		self.extract_error_info()


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


if __name__ == '__main__':
	print(extract_error_info())
