import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import environment_setup as setup
import local_worker as worker


class SetupTests(unittest.TestCase):
    def test_conversation_diagnostics_never_probe_network(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(worker, 'request_json') as network:
            config=worker.resolve_config({'routine_work_provider':'conversation','kicad_cli':'missing.exe'}, Path(temporary))
            report=setup.inspect_environment(config, probe_local=True)
            network.assert_not_called()
        self.assertEqual(report['kicad']['status'], 'configured_path_missing')
        self.assertEqual(report['local_service']['status'], 'not_required')

    def test_local_service_failure_keeps_tool_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(worker, 'request_json', side_effect=OSError('offline')):
            config=worker.resolve_config({'routine_work_provider':'local'}, Path(temporary))
            report=setup.inspect_environment(config, probe_local=True)
        self.assertEqual(report['local_service']['status'],'unreachable')
        self.assertIn('python',report)
        self.assertFalse(report['inference_tested'])

    def test_wizard_preserves_auto_paths_and_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            config=Path(temporary)/'config.json'
            config.write_text(json.dumps({'project_root':None,'custom':'keep'}))
            with patch('builtins.input',side_effect=['2','','','','','n']), \
                 patch.object(setup,'inspect_environment',return_value={'eda_tested':False}), \
                 contextlib.redirect_stdout(io.StringIO()):
                setup.wizard(config)
            raw=json.loads(config.read_text())
            self.assertIsNone(raw['project_root'])
            self.assertEqual(raw['custom'],'keep')
            self.assertEqual(raw['routine_work_provider'],'conversation')
            self.assertTrue(raw['setup_completed'])

    def test_cancelled_setup_does_not_change_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            config=Path(temporary)/'config.json'
            config.write_text('{}')
            with patch('builtins.input',side_effect=['2','','','','n']), \
                 patch.object(setup,'inspect_environment',return_value={}), contextlib.redirect_stdout(io.StringIO()):
                setup.wizard(config)
            self.assertEqual(config.read_text(),'{}')

    def test_remote_endpoint_rejected_without_network(self):
        with self.assertRaises(ValueError):
            worker.validate_base_url('https://example.com/v1')


if __name__ == '__main__':
    unittest.main()
