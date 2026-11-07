"""KiCad text assistant with local inference or AI conversation handoff."""
import argparse
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / 'config.json'
RULES = Path(__file__).resolve().parents[1] / 'rules' / 'pcb_requirements.json'
SYSTEM = ('你是 PCB 工作助理，目前只處理 KiCad，AD18 暫緩。以繁體中文完成指定工作。'
          '只依提供資料及既有決策工作；未知資訊明確標記，不捏造腳位、規格、工具執行結果。'
          '你不能直接操作電腦，輸出是待驗證草稿。遇到需要抉擇的衝突，'
          '以 NEEDS_DECISION 標記，列出問題、方案、利弊及缺少資料。')
ROLES = {
    'parts': ('你是①零件助理。先查環境設定提供的共同索引及本地資料；缺件時提出所需的'
              '製造商 Datasheet 查找工作。依完整料號核對符號、封裝、腳位及尺寸。'
              '未知資料不得猜測；未驗證草稿交付 staging。沒有外部工具結果就不能聲稱已上網或建檔。'),
    'schematic': ('你是②原理圖助理。依需求、已驗證零件與既定決策整理連線及原理圖草稿。'
                  '缺件交①，布局交③。檢查報告需由工具產生，不虛構 ERC 通過。'),
    'layout': ('你是③PCB布局助理。依網路、板框、固定元件與規則提出分區、擺放和走線草稿。'
               '包含原理圖轉入後混亂元件的重排。轉角依專案要求，只有明確指定時才以45度驗收；各網路線寬需有工作電流、'
               '銅厚、溫升、壓降與製程依據，不用絕對最大額定當耗流。區分訊號輸入、輸出與電源，'
               '共地只適用地端。查核理論和實際網路，不能用DRC代替功能檢查。'
               '原理圖問題交②，缺件交①；不虛構 DRC 通過。'),
    'general': ('你是④通用助理，承接未分類工作：檔案整理、格式轉換、索引維護、報告彙整、'
                '工作紀錄與錯誤資料整理。零件建立／腳位封裝問題轉交①，電路連線轉交②，'
                'PCB布局走線轉交③；輸出 HANDOFF 加上目標角色與必要背景。'
                '需要方案取捨時交協調對話，不自行改變既定設計要求。沒有執行工具就只提供草稿。'),
    'theory': ('你是⑤獨立電路理論檢查助理。先依使用者目標列出必須取得的原廠資料、'
               '電路理論來源與設計條件；搜尋與下載由工具代辦，不假裝自己已上網。'
               '根據原始規格、Datasheet、實際元件值及匯出網路清單獨立驗證，不以設計助理的結論作證據。'
               '檢查KCL/KVL、腳位與極性、偏壓/工作區、電壓電流額定與功耗、輸入輸出阻抗、'
               '耦合與回流、負載、增益/頻寬/失真條件。將假設、計算、來源與缺項分開。'
               '先列出有符號的KCL/KVL方程，由計算工具驗證殘差；不可只憑記憶推定基極電流符號。'
               '穩態直流分析把耦合電容視為開路，分別解兩側回路，不把左側偏壓直接搬到右側。'
               '有錯誤就回報FAIL與具體修正；資料不足標記NEEDS_DATA；有方案衝突才NEEDS_DECISION。'
               'ERC/DRC不能證明功能正確；只有工具實際驗證的結果才能當執行證據。'
               '你的PASS只是模型審閱意見，不是量測、模擬或工程認證，不自動授權製作。'),
}


def normalize_provider(provider):
    if provider == 'gpt':  # Compatibility with previously distributed settings and commands.
        return 'conversation'
    if provider not in {'local', 'conversation'}:
        raise ValueError('routine_work_provider 僅允許 local 或 conversation（舊名稱 gpt 仍可使用）。')
    return provider


def resolve_config(config, config_dir):
    """Resolve auto paths in memory; keep the distributed config account-free."""
    config = dict(config)
    def path_value(key, default=None):
        value = config.get(key)
        if value:
            path = Path(os.path.expandvars(str(value))).expanduser()
            config[key] = str(path if path.is_absolute() else config_dir / path)
        else:
            config[key] = str(default) if default is not None else None
        return config[key]

    path_value('project_root', Path.home() / 'PCB-Projects')
    library = Path(path_value('component_library_root', Path.home() / 'Datasheet'))
    for key, suffix in {
        'component_library_index': 'index/library-index.json',
        'personal_datasheets': 'Datasheets', 'personal_symbols': 'KiCad/symbols',
        'personal_footprints': 'KiCad/footprints', 'personal_3dmodels': 'KiCad/3dmodels',
        'component_staging': 'staging',
    }.items():
        path_value(key, library / suffix)

    path_value('kicad_root')
    path_value('kicad_cli')
    if not config['kicad_cli']:
        cli = shutil.which('kicad-cli')
        if not cli:
            roots = ([Path(config['kicad_root'])] if config['kicad_root'] else
                     [Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'KiCad',
                      Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'Programs/KiCad'])
            candidates = [candidate for root in roots if root.is_dir()
                          for candidate in root.glob('*/bin/kicad-cli.exe') if candidate.is_file()]
            def version_key(candidate):
                return tuple(int(part) for part in re.findall(r'\d+', candidate.parents[1].name))
            if candidates:
                cli = str(max(candidates, key=version_key))
        config['kicad_cli'] = cli
    cli = config['kicad_cli']
    if cli and not config['kicad_root']:
        config['kicad_root'] = str(Path(cli).parent.parent)
    builtin = Path(cli).parent.parent / 'share/kicad' if cli else None
    path_value('builtin_library_root', builtin if builtin and builtin.is_dir() else None)
    for key in ('ad18_exe', 'active_project', 'active_pcb'):
        path_value(key)
    config['accepted_projects'] = {
        name: dict(project, path=str(Path(config['project_root']) / name))
        if not project.get('path') else dict(project, path=str(
            Path(os.path.expandvars(project['path'])).expanduser()
            if Path(os.path.expandvars(project['path'])).expanduser().is_absolute()
            else config_dir / os.path.expandvars(project['path'])))
        for name, project in config.get('accepted_projects', {}).items()
    }
    config['routine_work_provider'] = normalize_provider(config.get('routine_work_provider', 'local'))
    return config


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_base_url(base):
    base = base.rstrip('/')
    url = urllib.parse.urlsplit(base)
    if (url.scheme != 'http' or url.hostname not in {'127.0.0.1', 'localhost', '::1'}
            or url.username or url.password or url.query or url.fragment):
        raise ValueError('僅允許本機 HTTP 端點；不會回退雲端。')
    return base


def request_json(config, route, payload=None):
    base = validate_base_url(config['base_url'])
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(base + route, data=data, headers={'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(req, timeout=config.get('timeout_seconds', 180)) as response:
        return json.load(response)


def choose_model(config, models):
    ids = [item.get('id') for item in models.get('data', []) if item.get('id')]
    if not ids:
        ids = [item.get('model') or item.get('name') for item in models.get('models', [])]
        ids = [item for item in ids if item]
    model = config.get('model')
    if model:
        if model not in ids:
            raise ValueError('設定模型尚未載入；不自動更換模型。')
        return model
    if len(ids) != 1:
        raise ValueError('請在 config.json 指定唯一模型。')
    return ids[0]


def build_messages(config, task, role='general'):
    if role not in ROLES:
        raise ValueError('未知的工作角色。')
    policy = ''
    if role in {'parts', 'schematic', 'layout', 'theory'}:
        policy = '\n必須遵守的設計檢查門檻：\n' + json.dumps(
            json.loads(RULES.read_text(encoding='utf-8')), ensure_ascii=False)
    environment = '\n環境設定（路徑存在性與內容仍須由工具確認）：\n' + json.dumps(
        {key: config.get(key) for key in ('project_root', 'component_library_root',
         'component_library_index', 'kicad_cli', 'builtin_library_root')}, ensure_ascii=False)
    return [{'role': 'system', 'content': SYSTEM + '\n' + ROLES[role] + policy + environment},
            {'role': 'user', 'content': task}]


def work(config, task, role='general'):
    messages = build_messages(config, task, role)
    provider = normalize_provider(config.get('routine_work_provider', 'local'))
    if provider == 'conversation':
        return {'status': 'needs_ai_work', 'provider': 'conversation', 'role': role,
                'messages': messages, 'executed': False, 'cloud_called': False,
                'prompt': messages[0]['content'] + '\n\n任務：\n' + task,
                'resume': '將 prompt 貼到你選用的 AI 對話，或由目前協調者讀取後繼續；本程式未呼叫模型，任務尚未完成。'}
    model = choose_model(config, request_json(config, '/models'))
    reply = request_json(config, '/chat/completions', {
        'model': model, 'messages': messages,
        'temperature': 0.2, 'max_tokens': config.get('max_tokens', 2048), 'stream': False})
    choices = reply.get('choices') or []
    if not choices:
        raise ValueError('本地服務未回傳 choices。')
    choice = choices[0]
    content = choice.get('message', {}).get('content')
    if not isinstance(content, str) or not content.strip():
        raise ValueError('本地回覆沒有文字。')
    if choice.get('finish_reason') != 'stop':
        raise ValueError('本地回覆未正常結束，可能遭截斷；不視為成功。')
    return {'status': 'local_result', 'provider': 'local', 'model': model, 'role': role,
            'content': content, 'usage': reply.get('usage'), 'executed': False}


def doctor(config):
    local = normalize_provider(config.get('routine_work_provider', 'local')) == 'local'
    model = choose_model(config, request_json(config, '/models')) if local else None
    cli, ad18 = config.get('kicad_cli'), config.get('ad18_exe')
    return {'status': 'local_service_reachable' if local else 'ai_handoff_ready',
            'provider': 'local' if local else 'conversation',
            'local_service_checked': local, 'cloud_called': False, 'model': model,
            'kicad_cli': cli, 'kicad_cli_exists': bool(cli and Path(cli).is_file()),
            'ad18_exe': ad18, 'ad18_exe_exists': bool(ad18 and Path(ad18).is_file()),
            'eda_adapters_implemented': False, 'inference_tested': False}


def emit(value, output, output_format='json', quiet=False):
    if output_format == 'text':
        serialized = value.get('prompt') or value.get('content')
        if not isinstance(serialized, str):
            raise ValueError('此結果沒有可輸出的提示詞或文字；請使用 json 格式。')
    else:
        serialized = json.dumps(value, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized + '\n', encoding='utf-8')
    if not quiet:
        print(serialized)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['setup', 'configure', 'paths', 'doctor', 'work', 'decision'])
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--task-file', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--role', choices=sorted(ROLES), default='general')
    parser.add_argument('--provider', choices=['local', 'conversation', 'gpt'],
                        help='local=本地模型；conversation=其他 AI 對話；gpt 為相容舊名稱')
    parser.add_argument('--format', choices=['json', 'text'], default='json',
                        help='work / decision 可輸出可直接複製的純文字')
    args = parser.parse_args()
    try:
        if args.format == 'text' and args.command not in {'work', 'decision'}:
            raise ValueError('--format text 僅適用 work 或 decision。')
        protected = {args.config.resolve()}
        if args.task_file:
            protected.add(args.task_file.resolve())
        if args.output and args.output.resolve() in protected:
            raise ValueError('輸出不得覆蓋任務或設定檔。')
        if args.command in {'work', 'decision'}:
            if not args.task_file:
                parser.error('需要 --task-file')
            task = args.task_file.read_text(encoding='utf-8-sig').strip()
            if not task:
                raise ValueError('任務不得空白。')
            if args.command == 'decision':
                emit({'status': 'needs_ai_decision', 'question': task, 'role': args.role, 'cloud_called': False,
                      'prompt': '請依原始需求與已有證據協助方案取捨；資料不足時列出缺項，不宣稱已執行工具。\n\n' + task,
                      'resume': '將 AI 決策加入下一個任務。'}, args.output, args.format)
                return 3
        if args.command == 'setup':
            from environment_setup import wizard
            wizard(args.config)
            return 0
        raw_config = json.loads(args.config.read_text(encoding='utf-8-sig'))
        if args.command == 'configure':
            provider = args.provider
            if provider is None:
                print('請選擇：1. 有本地模型  2. 其他 AI（無本地模型）')
                selected = input('輸入 1 或 2：').strip()
                if selected not in {'1', '2'}:
                    raise ValueError('請輸入 1 或 2；設定未變更。')
                provider = {'1': 'local', '2': 'conversation'}[selected]
            provider = normalize_provider(provider)
            raw_config['routine_work_provider'] = provider
            args.config.write_text(json.dumps(raw_config, ensure_ascii=False, indent=2) + '\n',
                                   encoding='utf-8')
            emit({'status': 'configured', 'provider': provider, 'cloud_called': False}, args.output)
            return 0
        config = resolve_config(raw_config, args.config.resolve().parent)
        if args.provider:
            config['routine_work_provider'] = normalize_provider(args.provider)
        if args.command == 'paths':
            emit(config, args.output)
            return 0
        if args.command == 'doctor':
            result = doctor(config)
        else:
            result = work(config, task, args.role)
        emit(result, args.output, args.format)
        return 3 if result.get('status') == 'needs_ai_work' else 0
    except (OSError, ValueError, KeyError, TypeError, EOFError, urllib.error.URLError) as exc:
        print(json.dumps({'status': 'error', 'message': str(exc), 'cloud_called': False},
                         ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    sys.exit(main())
