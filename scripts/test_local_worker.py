import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import local_worker as worker


class WorkerTests(unittest.TestCase):
    def test_gpt_work_preserves_rules_without_network(self):
        with patch.object(worker, 'request_json') as network:
            result = worker.work({'routine_work_provider': 'gpt'}, '檢查我的電路', 'theory')
            network.assert_not_called()
        self.assertEqual(result['status'], 'needs_gpt_work')
        self.assertIn('檢查我的電路', result['prompt'])
        self.assertIn(worker.ROLES['theory'], result['prompt'])
        self.assertIn('required_evidence', result['prompt'])
        self.assertFalse(result['executed'])
        self.assertFalse(result['cloud_called'])

    def test_configure_persists_only_provider(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / 'config.json'
            config.write_text(json.dumps({'project_root': None, 'routine_work_provider': 'local'}))
            args = ['worker', 'configure', '--config', str(config)]
            with patch('sys.argv', args), patch('builtins.input', return_value='2'), \
                 patch.object(worker, 'request_json') as network, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(worker.main(), 0)
                network.assert_not_called()
            self.assertEqual(json.loads(config.read_text()),
                             {'project_root': None, 'routine_work_provider': 'gpt'})

    def test_gpt_doctor_and_work_exit_codes(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / 'config.json'
            config.write_text(json.dumps({'routine_work_provider': 'local'}))
            task = Path(temporary) / 'task.txt'
            task.write_text('task')
            for command, code in [('doctor', 0), ('work', 3)]:
                args = ['worker', command, '--config', str(config), '--provider', 'gpt',
                        '--task-file', str(task)]
                with self.subTest(command=command), patch('sys.argv', args), \
                     patch.object(worker, 'request_json') as network, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(worker.main(), code)
                    network.assert_not_called()
            self.assertEqual(json.loads(config.read_text())['routine_work_provider'], 'local')

    def test_auto_paths_follow_current_user(self):
        for account in ('person-one', 'person-two'):
            with self.subTest(account=account), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary) / account
                with patch.object(worker.Path, 'home', return_value=home), \
                     patch.object(worker.shutil, 'which', return_value=None):
                    config = worker.resolve_config({}, Path(temporary))
                self.assertEqual(config['project_root'], str(home / 'PCB-Projects'))
                self.assertEqual(config['component_library_index'],
                                 str(home / 'Datasheet/index/library-index.json'))
                self.assertFalse(home.exists())

    def test_custom_roots_and_relative_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cli = root / 'KiCad/11.0/bin/kicad-cli.exe'
            builtin = cli.parent.parent / 'share/kicad'
            builtin.mkdir(parents=True)
            with patch.object(worker.shutil, 'which', return_value=str(cli)):
                config = worker.resolve_config({'component_library_root': 'library',
                                                 'active_pcb': 'board/demo.kicad_pcb'}, root)
            self.assertEqual(config['personal_symbols'], str(root / 'library/KiCad/symbols'))
            self.assertEqual(config['active_pcb'], str(root / 'board/demo.kicad_pcb'))
            self.assertEqual(config['builtin_library_root'], str(builtin))

    def test_latest_installed_kicad_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for version in ('9.0', '10.0'):
                cli = root / version / 'bin/kicad-cli.exe'
                cli.parent.mkdir(parents=True)
                cli.touch()
            with patch.object(worker.shutil, 'which', return_value=None):
                config = worker.resolve_config({'kicad_root': str(root)}, root)
            self.assertEqual(config['kicad_cli'], str(root / '10.0/bin/kicad-cli.exe'))

    def test_auto_model_requires_unique_loaded_model(self):
        self.assertEqual(worker.choose_model({'model': None}, {'data': [{'id': 'loaded'}]}), 'loaded')
        for ids in ([], [{'id': 'a'}, {'id': 'b'}]):
            with self.assertRaises(ValueError):
                worker.choose_model({'model': None}, {'data': ids})

    def test_paths_command_is_offline(self):
        config = Path(__file__).resolve().parents[1] / 'config.json'
        args = ['worker', 'paths', '--config', str(config)]
        with patch('sys.argv', args), patch.object(worker, 'request_json') as network:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(worker.main(), 0)
            network.assert_not_called()
        self.assertIsNone(json.loads(output.getvalue())['active_project'])

    def test_remote_endpoint_rejected_before_network(self):
        with patch('urllib.request.build_opener') as network:
            with self.assertRaises(ValueError):
                worker.request_json({'base_url': 'https://example.com/v1'}, '/models')
            network.assert_not_called()

    def test_no_model_substitution(self):
        with self.assertRaises(ValueError):
            worker.choose_model({'model': 'expected'}, {'data': [{'id': 'other'}]})

    def test_normal_work(self):
        responses = [{'data': [{'id': 'local'}]}, {'choices': [{
            'finish_reason': 'stop', 'message': {'content': '草稿'}}]}]
        with patch.object(worker, 'request_json', side_effect=responses) as request:
            result = worker.work({'model': 'local'}, '整理資料')
            self.assertEqual(result['content'], '草稿')
            self.assertFalse(result['executed'])
            self.assertEqual(request.call_count, 2)

    def test_truncated_reply_rejected(self):
        responses = [{'data': [{'id': 'local'}]}, {'choices': [{
            'finish_reason': 'length', 'message': {'content': 'incomplete'}}]}]
        with patch.object(worker, 'request_json', side_effect=responses):
            with self.assertRaises(ValueError):
                worker.work({'model': 'local'}, 'task')

    def test_role_contexts_are_separate(self):
        for role in worker.ROLES:
            responses = [{'data': [{'id': 'local'}]}, {'choices': [{
                'finish_reason': 'stop', 'message': {'content': '草稿'}}]}]
            with self.subTest(role=role), patch.object(worker, 'request_json', side_effect=responses) as request:
                result = worker.work({'model': 'local'}, 'task', role)
                system = request.call_args.args[2]['messages'][0]['content']
                self.assertEqual(result['role'], role)
                self.assertIn(worker.ROLES[role], system)
                for other in worker.ROLES:
                    if other != role:
                        self.assertNotIn(worker.ROLES[other], system)

    def test_unknown_role_never_calls_network(self):
        with patch.object(worker, 'request_json') as request:
            with self.assertRaises(ValueError):
                worker.work({}, 'task', 'unknown')
            request.assert_not_called()

    def test_missing_required_policy_stops_professional_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing=Path(temporary)/'missing-policy.json'
            with patch.object(worker,'RULES',missing), patch.object(worker,'request_json') as request:
                with self.assertRaises(OSError):
                    worker.work({},'route PCB','layout')
                request.assert_not_called()

    def test_decision_never_calls_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary) / 'task.txt'
            output = Path(temporary) / 'decision.json'
            task.write_text('方案 A 或 B？', encoding='utf-8')
            args = ['worker', 'decision', '--task-file', str(task), '--output', str(output)]
            with patch('sys.argv', args), patch.object(worker, 'request_json') as network:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(worker.main(), 3)
                network.assert_not_called()
            self.assertFalse(json.loads(output.read_text(encoding='utf-8'))['cloud_called'])

    def test_local_failure_does_not_fallback(self):
        with patch.object(worker, 'request_json', side_effect=OSError('offline')) as request:
            with self.assertRaises(OSError):
                worker.work({'model': 'local'}, 'task')
            self.assertEqual(request.call_count, 1)


if __name__ == '__main__':
    unittest.main()
