import yaml


def config_loader(conf_file: str):
	with open(f'configs/{conf_file}.yaml', encoding='utf-8') as file:
		return yaml.safe_load(file)

