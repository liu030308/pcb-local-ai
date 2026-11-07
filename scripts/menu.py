"""Interactive Windows launcher; all paths are independent of the current directory."""
import json
import sys
from datetime import datetime
from pathlib import Path

import local_worker as worker

ROOT = Path(__file__).resolve().parents[1]
ROLE_OPTIONS = [('general', '通用助理'), ('parts', '零件助理'),
                ('schematic', '原理圖助理'), ('layout', 'PCB 布局助理'),
                ('theory', '獨立理論檢查')]


def choose(title, options, default=None):
    print('\n' + title)
    for key, label in options.items():
        print(f'  {key}. {label}')
    while True:
        answer = input('請輸入選項' + (f'（Enter={default}）' if default is not None else '') + '：').strip()
        if not answer and default is not None:
            return default
        if answer in options:
            return answer
        print('請輸入上面列出的選項。')


def load_config(config_path):
    return json.loads(config_path.read_text(encoding='utf-8-sig'))


def configure(config_path):
    raw = load_config(config_path)
    current = worker.normalize_provider(raw.get('routine_work_provider', 'local'))
    choice = choose('選擇 AI 模式', {'1': '有本地模型', '2': '其他 AI（無本地模型）'},
                    '1' if current == 'local' else '2')
    raw['routine_work_provider'] = {'1': 'local', '2': 'conversation'}[choice]
    config_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('已記住模式：' + ('本地模型' if choice == '1' else '其他 AI'))


def create_task(config_path):
    configure(config_path)
    config = worker.resolve_config(load_config(config_path), config_path.parent)
    selection = choose('選擇工作角色',
                       {str(i): label for i, (_, label) in enumerate(ROLE_OPTIONS, 1)}, '1')
    role = ROLE_OPTIONS[int(selection) - 1][0]
    source = choose('任務內容從哪裡來？', {'1': '直接輸入需求', '2': '讀取 UTF-8 文字任務檔'}, '1')
    if source == '2':
        task_path = Path(input('輸入或拖入任務檔路徑：').strip().strip('"')).expanduser()
        if not task_path.is_absolute():
            task_path = config_path.parent / task_path
        task = task_path.read_text(encoding='utf-8-sig').strip()
    else:
        print('輸入需求，可分多行；最後單獨輸入一個 . 結束。')
        lines = []
        while True:
            line = input()
            if line.strip() == '.':
                break
            lines.append(line)
        task = '\n'.join(lines).strip()
    if not task:
        raise ValueError('任務不得空白。')
    if config['routine_work_provider'] == 'local':
        print('正在等待本地模型；失敗時不會自動改用其他 AI。')
    result = worker.work(config, task, role)
    output_dir = ROOT / 'outputs'
    stem = datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-' + role
    text_path, json_path = output_dir / (stem + '.txt'), output_dir / (stem + '.json')
    worker.emit(result, text_path, 'text', quiet=True)
    worker.emit(result, json_path, quiet=True)
    print(f'\n文字檔：{text_path}\n紀錄檔：{json_path}')
    if result['status'] == 'needs_ai_work':
        print('請開啟文字檔，複製全文到你選用的 AI 對話；任務尚待 AI 處理。')
    else:
        print('已取得本地模型草稿；仍需實際工具驗證。')
    return text_path, json_path


def main():
    if sys.version_info < (3, 10):
        print('需要 Python 3.10 或以上。')
        return 1
    print('PCB AI 助理 — 有本地模型／其他 AI 都可使用')
    if sys.stdin.isatty() and not load_config(worker.CONFIG).get('setup_completed'):
        from environment_setup import wizard
        try:
            wizard(worker.CONFIG)
        except (EOFError, KeyboardInterrupt):
            return 0
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f'設定未完成：{exc}；可由主選單重新執行。')
    while True:
        try:
            choice = choose('主選單', {'1': '建立任務', '2': '切換預設 AI 模式',
                                      '3': '查看自動路徑', '4': '檢查環境',
                                      '5': '環境設定精靈', '6': '執行 KiCad 工程檢查', '0': '離開'})
            if choice == '0':
                return 0
            if choice == '1':
                create_task(worker.CONFIG)
            elif choice == '2':
                configure(worker.CONFIG)
            elif choice == '5':
                from environment_setup import wizard
                wizard(worker.CONFIG)
            elif choice == '6':
                from validate_project import validate_project
                project = Path(input('輸入或拖入 .kicad_pro 路徑：').strip().strip('"')).expanduser()
                if not project.is_absolute():
                    project = worker.CONFIG.parent / project
                rule_text = input('專案幾何規則 JSON 路徑（Enter 不指定）：').strip().strip('"')
                rules = Path(rule_text).expanduser() if rule_text else None
                if rules and not rules.is_absolute():
                    rules = worker.CONFIG.parent / rules
                config = worker.resolve_config(load_config(worker.CONFIG), worker.CONFIG.parent)
                report = validate_project(project, config, ROOT / 'outputs' / ('validation-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f')), rules)
                print('檢查結果：' + report['status'] + '\n報告：' + report['report_path'])
            else:
                config = worker.resolve_config(load_config(worker.CONFIG), worker.CONFIG.parent)
                if choice == '3':
                    worker.emit(config, None)
                else:
                    print('本地模式會連線設定中的本機服務；其他 AI 模式不需模型服務。')
                    from environment_setup import inspect_environment
                    worker.emit(inspect_environment(config, probe_local=True), None)
        except (EOFError, KeyboardInterrupt):
            print('\n已離開。')
            return 0
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f'無法完成：{exc}\n請檢查設定或任務檔後重試。')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    sys.exit(main())
