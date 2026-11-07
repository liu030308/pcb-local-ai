import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import local_worker as worker
import menu


class MenuTests(unittest.TestCase):
    def test_multiline_conversation_task_creates_text_and_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / 'config.json'
            config.write_text(json.dumps({'routine_work_provider': 'local', 'project_root': None}))
            # mode, role, input source, two task lines, end marker
            answers = ['2', '5', '1', '分析偏壓', '待提供零件值', '.']
            with patch('builtins.input', side_effect=answers), patch.object(menu, 'ROOT', root), \
                 patch.object(worker, 'request_json') as network, contextlib.redirect_stdout(io.StringIO()):
                text, record = menu.create_task(config)
                network.assert_not_called()
            result = json.loads(record.read_text(encoding='utf-8'))
            self.assertEqual(text.read_text(encoding='utf-8'), result['prompt'] + '\n')
            self.assertIn('分析偏壓\n待提供零件值', result['prompt'])
            self.assertEqual(result['role'], 'theory')
            raw = json.loads(config.read_text(encoding='utf-8'))
            self.assertIsNone(raw['project_root'])
            self.assertEqual(raw['routine_work_provider'], 'conversation')

    def test_quoted_task_file_and_repeated_exports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / 'config.json'
            config.write_text(json.dumps({'routine_work_provider': 'conversation'}))
            task = root / '中文 任務.txt'
            task.write_text('檢查輸出負載', encoding='utf-8-sig')
            results = []
            for _ in range(2):
                with patch('builtins.input', side_effect=['', '', '2', f'"{task}"']), \
                     patch.object(menu, 'ROOT', root), patch.object(worker, 'request_json') as network, \
                     contextlib.redirect_stdout(io.StringIO()):
                    results.append(menu.create_task(config))
                    network.assert_not_called()
            self.assertNotEqual(results[0], results[1])
            self.assertIn('檢查輸出負載', results[1][0].read_text(encoding='utf-8'))

    def test_empty_task_does_not_call_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / 'config.json'
            config.write_text('{}')
            with patch('builtins.input', side_effect=['2', '', '', '.']), \
                 patch.object(worker, 'request_json') as network, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ValueError):
                    menu.create_task(config)
                network.assert_not_called()

    def test_menu_can_start_from_another_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run([sys.executable, '-B', str(Path(menu.__file__).resolve())],
                                    cwd=temporary, input='0\n', text=True, encoding='utf-8',
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('主選單', result.stdout)


if __name__ == '__main__':
    unittest.main()
