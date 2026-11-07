"""First-run configuration and explicit environment diagnostics."""
import json
import subprocess
import sys
from pathlib import Path

import local_worker as worker


def inspect_environment(config, probe_local=False):
    cli = config.get('kicad_cli')
    cli_path = Path(cli) if cli else None
    kicad = {'path': cli, 'status': 'not_detected',
             'hint': '未偵測到 KiCad CLI；可能未安裝或位於非標準位置，請手動指定。'}
    if cli_path:
        kicad['status'] = 'configured_path_missing'
        kicad['hint'] = '設定的 KiCad CLI 路徑不存在，請修正或清空後重新偵測。'
        if cli_path.is_file():
            try:
                reply = subprocess.run([str(cli_path), 'version'], capture_output=True, text=True,
                                       encoding='utf-8', errors='replace', timeout=10)
                kicad.update(status='available' if reply.returncode == 0 else 'version_check_failed',
                             version=reply.stdout.strip(), stderr=reply.stderr.strip(),
                             hint='路徑存在且版本檢查通過。' if reply.returncode == 0 else '執行檔存在，但版本檢查失敗。')
            except (OSError, subprocess.TimeoutExpired) as exc:
                kicad.update(status='version_check_failed', hint=str(exc))
    local = {'status': 'not_required' if config['routine_work_provider'] == 'conversation' else 'not_checked'}
    if config['routine_work_provider'] == 'local' and probe_local:
        try:
            models = worker.request_json(dict(config, timeout_seconds=5), '/models')
            ids = [m.get('id') for m in models.get('data', []) if m.get('id')]
            local.update(status='reachable', loaded_models=ids)
            try:
                local['model'] = worker.choose_model(config, models)
            except ValueError as exc:
                local.update(status='model_selection_required', hint=str(exc))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            local.update(status='unreachable', hint=str(exc))
    return {'python': {'status': 'available' if sys.version_info >= (3, 10) else 'unsupported',
                       'version': sys.version.split()[0], 'executable': sys.executable},
            'kicad': kicad, 'local_service': local,
            'paths': {key: {'path': config[key], 'status': 'exists' if Path(config[key]).is_dir() else 'not_created'}
                      for key in ('project_root', 'component_library_root')},
            'inference_tested': False, 'eda_tested': False}


def wizard(config_path):
    raw = json.loads(config_path.read_text(encoding='utf-8-sig'))
    print('\n首次環境設定：Enter 保留原值；路徑輸入 :auto 恢復自動偵測。')
    current = worker.normalize_provider(raw.get('routine_work_provider', 'local'))
    while True:
        choice = input('AI 模式：1 本地模型／2 其他 AI（Enter 保留）：').strip()
        if choice in {'', '1', '2'}:
            break
        print('請輸入 1 或 2。')
    raw['routine_work_provider'] = {'1': 'local', '2': 'conversation'}.get(choice, current)
    for key, label in [('kicad_cli', 'KiCad CLI 路徑'), ('project_root', '專案根目錄'),
                       ('component_library_root', '元件庫根目錄')]:
        answer = input(f'{label} [{raw.get(key) or "自動"}]：').strip().strip('"')
        if answer:
            raw[key] = None if answer == ':auto' else answer
    if raw['routine_work_provider'] == 'local':
        answer = input(f'本地服務位址 [{raw.get("base_url", "http://127.0.0.1:8686/v1")}]：').strip()
        raw['base_url'] = worker.validate_base_url(answer or raw.get('base_url', 'http://127.0.0.1:8686/v1'))
        answer = input(f'模型 ID [{raw.get("model") or "自動選唯一模型"}]（:auto 清空）：').strip()
        if answer:
            raw['model'] = None if answer == ':auto' else answer
    resolved = worker.resolve_config(raw, config_path.parent)
    report = inspect_environment(resolved, probe_local=True)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if input('儲存上述設定？[Y/n]：').strip().lower() not in {'', 'y', 'yes'}:
        print('已取消，設定未修改。')
        return report
    raw['setup_completed'] = True
    config_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if input('建立尚不存在的專案／元件庫根目錄？[y/N]：').strip().lower() in {'y', 'yes'}:
        for key in ('project_root', 'component_library_root'):
            Path(resolved[key]).mkdir(parents=True, exist_ok=True)
    print('設定已儲存。缺少的工具仍需安裝或修正路徑；設定完成不代表工程驗證通過。')
    return report
