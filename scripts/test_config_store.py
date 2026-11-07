import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config_store


class ConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.config=self.root/'config.json'
        (self.root/'config.example.json').write_text('{"model":null,"project_root":null}')

    def test_missing_config_is_initialized_without_account_paths(self):
        value=config_store.load_config(self.config)
        self.assertEqual(value,{'model':None,'project_root':None})
        self.assertTrue(self.config.is_file())
        self.assertFalse(config_store.state_path(self.config).exists())

    def test_existing_settings_are_never_replaced_by_example(self):
        self.config.write_text('{"model":"mine","custom":1}')
        self.assertEqual(config_store.load_config(self.config),{'model':'mine','custom':1})

    def test_legacy_state_is_backed_up_and_migrated_without_losing_settings(self):
        original={'model':'mine','custom':{'keep':True},'active_project':'電路.kicad_pro',
                  'accepted_projects':{'example':{'revision':'A'}}}
        self.config.write_text(json.dumps(original),encoding='utf-8')
        value=config_store.load_config(self.config)
        self.assertEqual(value,{'model':'mine','custom':{'keep':True}})
        self.assertEqual(config_store.read_object(config_store.backup_path(self.config)),original)
        self.assertEqual(config_store.load_runtime(self.config)['active_project'],'電路.kicad_pro')
        state_before=config_store.state_path(self.config).read_bytes()
        config_store.load_config(self.config)
        self.assertEqual(config_store.state_path(self.config).read_bytes(),state_before)

    def test_existing_state_wins_and_cannot_override_static_settings(self):
        self.config.write_text('{"model":"mine","active_project":"old"}')
        config_store.atomic_write(config_store.state_path(self.config),{'active_project':'new','model':'injected'})
        config_store.load_config(self.config)
        runtime=config_store.load_runtime(self.config)
        self.assertEqual(runtime['active_project'],'new')
        self.assertEqual(runtime['model'],'mine')
        self.assertEqual(config_store.read_object(config_store.backup_path(self.config))['active_project'],'old')

    def test_corrupt_state_keeps_original_legacy_config(self):
        self.config.write_text('{"active_project":"old"}')
        config_store.state_path(self.config).write_text('broken')
        with self.assertRaises(ValueError):
            config_store.load_config(self.config)
        self.assertEqual(self.config.read_text(),'{"active_project":"old"}')

    def test_atomic_write_failure_preserves_previous_file(self):
        self.config.write_text('{"model":"old"}')
        with patch.object(config_store.os,'replace',side_effect=OSError('denied')):
            with self.assertRaises(OSError):
                config_store.save_config(self.config,{'model':'new'})
        self.assertEqual(self.config.read_text(),'{"model":"old"}')
        self.assertEqual(list(self.root.glob('*.tmp')),[])

    def test_static_writer_refuses_project_state(self):
        with self.assertRaises(ValueError):
            config_store.save_config(self.config,{'active_project':'board'})

    def test_custom_configs_get_separate_state_files(self):
        self.assertNotEqual(config_store.state_path(self.config),config_store.state_path(self.root/'other.json'))


if __name__=='__main__':
    unittest.main()
