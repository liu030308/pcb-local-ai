import json
import shutil
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

import build_release


class BuildTests(unittest.TestCase):
    def test_archive_uses_template_not_personal_config_and_excludes_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'source'
            root.mkdir()
            for name in ['LICENSE','VERSION','config.example.json','start.bat']:
                shutil.copy2(build_release.ROOT/name,root/name)
            (root/'scripts').mkdir()
            shutil.copy2(build_release.ROOT/'scripts/menu.py',root/'scripts/menu.py')
            (root/'config.json').write_text('{"private":"must-not-leak"}')
            (root/'outputs').mkdir()
            (root/'outputs/task.json').write_text('private task')
            (root/'scripts/__pycache__').mkdir()
            (root/'scripts/__pycache__/cache.pyc').write_bytes(b'cache')
            archive=build_release.build(root,Path(temporary)/'dist')
            with ZipFile(archive) as zipped:
                config=json.loads(zipped.read('pcb-local-ai/config.json'))
                self.assertIsNone(config['project_root'])
                self.assertNotIn('private',config)
                self.assertFalse(any('outputs' in n or '__pycache__' in n for n in zipped.namelist()))
            self.assertTrue((archive.parent/'SHA256SUMS').is_file())

    def test_repeated_builds_are_identical(self):
        with tempfile.TemporaryDirectory() as temporary:
            a=build_release.build(build_release.ROOT,Path(temporary)/'one').read_bytes()
            b=build_release.build(build_release.ROOT,Path(temporary)/'two').read_bytes()
            self.assertEqual(a,b)

    def test_missing_required_source_prevents_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'root'
            root.mkdir()
            with self.assertRaises(ValueError):
                build_release.build(root,Path(temporary)/'dist')


if __name__=='__main__':
    unittest.main()
