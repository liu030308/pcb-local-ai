"""Read-only KiCad CLI checks with auditable evidence; never engineering release approval."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import board_audit
import local_worker as worker


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_command(command, timeout=180):
    env = dict(os.environ, LC_ALL='C.UTF-8', LANG='C.UTF-8')
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=timeout, env=env, shell=False)
        return {'command': command, 'returncode': result.returncode,
                'stdout': result.stdout, 'stderr': result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'command': command, 'returncode': None, 'stdout': '', 'stderr': str(exc)}


def report_count(path, kind):
    report = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(report, dict) or not isinstance(report.get('kicad_version'), str):
        raise ValueError('報告缺少 KiCad 版本或不是物件。')
    if kind == 'erc':
        sheets = report.get('sheets')
        if not isinstance(sheets, list) or not sheets:
            raise ValueError('ERC 報告缺少 sheets。')
        groups = [sheet.get('violations') if isinstance(sheet, dict) else None for sheet in sheets]
    else:
        groups = [report.get(key) for key in ('violations', 'unconnected_items', 'schematic_parity')]
    if any(not isinstance(group, list) or any(not isinstance(v, dict) or 'severity' not in v for v in group) for group in groups):
        raise ValueError('報告違規欄位缺漏或格式錯誤，不能當作零錯誤。')
    return sum(len(group) for group in groups)


def validate_project(project, config, output_dir, rules_file=None):
    project = Path(project).resolve()
    if project.suffix != '.kicad_pro' or not project.is_file():
        raise ValueError('請指定存在的 .kicad_pro 專案檔。')
    output_dir = Path(output_dir).resolve()
    # A new evidence directory ensures a failed invocation cannot reuse an old report.
    output_dir.mkdir(parents=True, exist_ok=False)
    schematic, board = project.with_suffix('.kicad_sch'), project.with_suffix('.kicad_pcb')
    inputs = [project] + sorted(project.parent.rglob('*.kicad_sch'))
    inputs += [p for p in [board, project.with_suffix('.kicad_dru')] if p.is_file()]
    before = {str(p): digest(p) for p in inputs}
    checks = {}
    cli = config.get('kicad_cli')
    cli_exists = bool(cli and Path(cli).is_file())
    version = run_command([cli, 'version'], 10) if cli_exists else {'returncode': None, 'stderr': '未偵測到可用的 KiCad CLI。'}
    help_cache = {}
    for name, kind, source, extra in [('erc', 'sch', schematic, []),
                                       ('drc', 'pcb', board, []),
                                       ('schematic_parity', 'pcb', board, ['--schematic-parity'])]:
        if not source.is_file() or (extra and not schematic.is_file()):
            checks[name] = {'status': 'not_run', 'reason': '缺少對應的同名原理圖或 PCB。'}
            continue
        if not cli_exists or version.get('returncode') != 0:
            checks[name] = {'status': 'not_run', 'reason': 'KiCad CLI 或版本檢查不可用。'}
            continue
        subcommand = [kind, 'erc' if kind == 'sch' else 'drc']
        cache_key = tuple(subcommand)
        if cache_key not in help_cache:
            help_cache[cache_key] = run_command([cli] + subcommand + ['--help'], 10)
        help_result = help_cache[cache_key]
        required = ['--format', '--output', '--exit-code-violations', '--severity-error', '--severity-warning'] + extra
        if help_result['returncode'] != 0 or not all(flag in help_result['stdout'] for flag in required):
            checks[name] = {'status': 'not_run', 'reason': 'CLI 不支援必要的檢查參數。', 'capability_probe': help_result}
            continue
        report_path = output_dir / (name + '.json')
        command = [cli] + subcommand + ['--format', 'json', '--severity-error', '--severity-warning',
                                        '--exit-code-violations', '--output', str(report_path)] + extra + [str(source)]
        result = run_command(command)
        result['report_path'] = str(report_path)
        result['status'] = 'error'
        if report_path.is_file():
            result['report_sha256'] = digest(report_path)
            try:
                result['violation_count'] = report_count(report_path, 'erc' if kind == 'sch' else 'drc')
                diagnostic_failure = re.search(r"failed to|unable to|could not|cannot |couldn't|error loading|error:|not found", result['stdout'] + '\n' + result['stderr'], re.I)
                if result['returncode'] in {0, 5} and not diagnostic_failure:
                    result['status'] = 'fail' if result['violation_count'] or result['returncode'] == 5 else 'pass'
                else:
                    result['reason'] = '工具回傳執行錯誤、逾時或無法完成的診斷訊息。'
            except (OSError, ValueError, TypeError) as exc:
                result['reason'] = str(exc)
        else:
            result['reason'] = '工具未產生本次 JSON 報告。'
        checks[name] = result
    if rules_file and board.is_file():
        rule_path = Path(rules_file).resolve()
        try:
            rules = json.loads(rule_path.read_text(encoding='utf-8-sig'))
            checks['geometry'] = board_audit.audit(board, rules)
            checks['geometry'].update(rules_path=str(rule_path), rules_sha256=digest(rule_path))
        except (OSError, ValueError, TypeError, IndexError) as exc:
            checks['geometry'] = {'status': 'error', 'reason': str(exc)}
    else:
        checks['geometry'] = {'status': 'not_run', 'reason': '未提供幾何規則或缺少 PCB。'}
    after = {str(p): digest(p) if p.is_file() else None for p in inputs}
    unchanged = before == after
    states = [check['status'] for check in checks.values()]
    status = ('fail' if not unchanged or any(s in {'fail', 'error'} for s in states) else
              'checks_passed' if all(s == 'pass' for s in states) else 'needs_review')
    report_path = output_dir / 'summary.json'
    summary = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
               'status': status, 'engineering_release_approved': False,
               'project': str(project), 'tool_version': version, 'checks': checks,
               'inputs_before_sha256': before, 'inputs_after_sha256': after, 'inputs_unchanged': unchanged,
               'report_path': str(report_path),
               'still_required': ['獨立功能理論／模擬或量測', '完整 courtyard、板框與製造／實體銅層檢查',
                                  '板廠能力與 DFM 確認', '檢閱 KiCad 被忽略／排除的規則及專案設定',
                                  '走線方向不代表焊盤外連續轉彎符合要求'],
               'scope_note': 'checks_passed 僅表示本次已實作且有證據的檢查通過，不是電路或製造放行。'}
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=worker.CONFIG)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--rules-file', type=Path)
    args = parser.parse_args()
    try:
        config = worker.resolve_config(json.loads(args.config.read_text(encoding='utf-8-sig')), args.config.resolve().parent)
        output = args.output_dir or worker.CONFIG.parent / 'outputs' / ('validation-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        result = validate_project(args.project, config, output, args.rules_file)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['status'] == 'checks_passed' else 1 if result['status'] == 'fail' else 3
    except (OSError, ValueError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    sys.exit(main())
