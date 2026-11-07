"""Portable configuration initialization and lossless legacy project-state migration."""
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_KEYS = {'active_project', 'active_pcb', 'active_revision', 'active_project_status',
              'accepted_projects', 'accepted_revision', 'project_display_name'}


def read_object(path):
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError(f'{Path(path).name} 必須是 JSON 物件。')
    return value


def state_path(config_path):
    config_path = Path(config_path)
    return config_path.with_name('.pcb_state.json' if config_path.name == 'config.json'
                                 else '.' + config_path.stem + '_state.json')


def backup_path(config_path):
    return Path(config_path).with_name('.' + Path(config_path).stem + '.pre-state-migration.json')


def atomic_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                         dir=path.parent, prefix='.' + path.name, suffix='.tmp', delete=False) as file:
            temporary = file.name
            json.dump(value, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary and Path(temporary).exists():
            Path(temporary).unlink()


def initialize(config_path):
    config_path = Path(config_path)
    if not config_path.exists():
        template = config_path.with_name('config.example.json')
        if not template.is_file():
            template = ROOT / 'config.example.json'
        defaults = read_object(template)
        defaults = {key: value for key, value in defaults.items() if key not in STATE_KEYS}
        config_path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation never overwrites an existing user's config, even on a race.
        try:
            with config_path.open('x', encoding='utf-8', newline='\n') as file:
                json.dump(defaults, file, ensure_ascii=False, indent=2, allow_nan=False)
                file.write('\n')
        except FileExistsError:
            pass
    return config_path


def load_state(config_path):
    path = state_path(config_path)
    return read_object(path) if path.is_file() else {}


def load_config(config_path):
    config_path = initialize(config_path)
    raw = read_object(config_path)
    legacy = {key: raw[key] for key in STATE_KEYS if key in raw}
    if legacy:
        # Write state first. If interrupted, the old config still contains all original data.
        existing = load_state(config_path)
        merged = dict(legacy, **existing)
        backup = backup_path(config_path)
        if not backup.exists():
            with backup.open('x', encoding='utf-8', newline='\n') as file:
                json.dump(raw, file, ensure_ascii=False, indent=2, allow_nan=False)
                file.write('\n')
        atomic_write(state_path(config_path), merged)
        raw = {key: value for key, value in raw.items() if key not in STATE_KEYS}
        atomic_write(config_path, raw)
    return raw


def save_config(config_path, value):
    if STATE_KEYS & value.keys():
        raise ValueError('動態專案欄位請使用 save_state，不寫入環境設定。')
    atomic_write(config_path, value)


def save_state(config_path, state):
    current = load_state(config_path)
    current.update(state)
    atomic_write(state_path(config_path), current)


def load_runtime(config_path):
    settings = load_config(config_path)
    # State cannot override the endpoint, model, paths or other static settings.
    settings.update({key: value for key, value in load_state(config_path).items() if key in STATE_KEYS})
    return settings
