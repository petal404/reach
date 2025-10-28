import yaml
import os

def load_config():
    """Loads settings and criteria from YAML config files."""
    base_path = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(base_path, '..', 'config', 'settings.yml')
    criteria_path = os.path.join(base_path, '..', 'config', 'criteria.yml')

    with open(settings_path, 'r') as f:
        settings = yaml.safe_load(f)
    with open(criteria_path, 'r') as f:
        criteria = yaml.safe_load(f)
    return settings, criteria
