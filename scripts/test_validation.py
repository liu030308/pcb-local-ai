import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import board_audit
import validate_project as validation

BOARD = '(kicad_pcb (net 0 "") (net 1 "GND") (segment (start 1 1) (end 2 2) (width 0.3) (layer "B.Cu") (net 1)) (gr_rect (start 0 0) (end 40 40) (layer "Edge.Cuts")))'


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / '中文 板.kicad_pro'
        self.project.write_text('{}')
        self.project.with_suffix('.kicad_sch').write_text('(kicad_sch)')
        self.project.with_suffix('.kicad_pcb').write_text(BOARD)
        self.cli = self.root / 'kicad-cli'
        self.cli.touch()
        self.config = {'kicad_cli': str(self.cli)}
        self.rules = self.root / 'rules.json'
        self.rules.write_text(json.dumps({'min_track_width_mm': 0.25, 'max_vias': 0,
                                         'allowed_track_layers': ['B.Cu'],
                                         'allowed_segment_headings_deg': [0,45,90,135],
                                         'outline_size_mm': [40,40]}))

    def fake_command(self, command, timeout=180):
        result = {'command': command, 'returncode': 0, 'stdout': '', 'stderr': ''}
        if 'version' in command:
            result['stdout'] = '10.0.0'
        elif '--help' in command:
            result['stdout'] = '--format --output --exit-code-violations --severity-error --severity-warning --schematic-parity'
        else:
            path = Path(command[command.index('--output') + 1])
            report = {'kicad_version': '10.0.0', 'source':command[-1], 'date':'2026-11-07T00:00:00Z'}
            report.update({'sheets': [{'path':'/', 'uuid_path':'/test', 'violations': []}]} if 'erc' in command else
                          {'violations': [], 'unconnected_items': [], 'schematic_parity': []})
            path.write_text(json.dumps(report))
        return result

    def run_validation(self, side_effect=None, rules=True):
        with patch.object(validation, 'run_command', side_effect=side_effect or self.fake_command):
            return validation.validate_project(self.project, self.config, self.root/'evidence', self.rules if rules else None)

    def test_evidence_and_read_only_commands(self):
        result = self.run_validation()
        self.assertEqual(result['status'], 'checks_passed')
        self.assertFalse(result['engineering_release_approved'])
        self.assertTrue(result['inputs_unchanged'])
        self.assertIn('--schematic-parity', result['checks']['schematic_parity']['command'])
        self.assertNotIn('--save-board', result['checks']['drc']['command'])
        self.assertEqual(len(result['checks']['erc']['report_sha256']), 64)
        self.assertTrue(Path(result['report_path']).is_file())

    def test_unsupported_cli_is_marked_not_run(self):
        calls=[]
        def old_cli(command, timeout=180):
            calls.append(command)
            result=self.fake_command(command,timeout)
            if '--help' in command:
                result.update(returncode=1,stdout='Usage: sch {export}')
            return result
        result=self.run_validation(old_cli)
        self.assertEqual(result['status'],'needs_review')
        self.assertEqual(result['checks']['erc']['status'],'not_run')
        self.assertFalse(any('--output' in command for command in calls))

    def test_missing_report_never_passes(self):
        def missing(command, timeout=180):
            result = self.fake_command(command, timeout)
            if '--output' in command:
                Path(command[command.index('--output')+1]).unlink()
            return result
        self.assertEqual(self.run_validation(missing)['status'], 'fail')

    def test_unconnected_items_are_failures_even_if_exit_zero(self):
        def unconnected(command, timeout=180):
            result = self.fake_command(command, timeout)
            if 'drc' in command and '--output' in command:
                path = Path(command[command.index('--output')+1])
                report = json.loads(path.read_text())
                report['unconnected_items'] = [{'type':'unconnected_items','description':'test','severity':'error','items':[]}]
                path.write_text(json.dumps(report))
            return result
        self.assertEqual(self.run_validation(unconnected)['status'], 'fail')

    def test_failed_parity_diagnostic_is_error_with_empty_report(self):
        def failure(command, timeout=180):
            result = self.fake_command(command, timeout)
            if '--schematic-parity' in command and '--output' in command:
                result['stderr'] = 'Failed to fetch schematic netlist for parity tests'
            return result
        result = self.run_validation(failure)
        self.assertEqual(result['checks']['schematic_parity']['status'], 'error')

    def test_missing_schema_does_not_mean_zero_violations(self):
        path = self.root/'bad.json'
        path.write_text('{"kicad_version":"10.0"}')
        with self.assertRaises(ValueError):
            validation.report_count(path, 'drc')

    def test_nested_erc_violations_are_counted(self):
        path = self.root/'erc.json'
        path.write_text(json.dumps({'kicad_version':'10.0', 'source':'test.kicad_sch','date':'2026-11-07','sheets':[
            {'path':'/','uuid_path':'/a','violations': []}, {'path':'/child','uuid_path':'/a/b','violations': [{'type':'pin_not_connected','description':'test','severity':'warning','items':[]}]}]}))
        self.assertEqual(validation.report_count(path, 'erc'), 1)

    def test_missing_cli_and_rules_are_review_not_success(self):
        with patch.object(validation, 'run_command') as command:
            result = validation.validate_project(self.project, {}, self.root/'evidence')
            command.assert_not_called()
        self.assertEqual(result['status'], 'needs_review')

    def test_inputs_modified_during_run_are_rejected(self):
        def modifying(command, timeout=180):
            result = self.fake_command(command, timeout)
            if 'erc' in command and '--output' in command:
                self.project.write_text('{"changed":true}')
            return result
        result = self.run_validation(modifying)
        self.assertFalse(result['inputs_unchanged'])
        self.assertEqual(result['status'], 'fail')

    def test_existing_evidence_directory_cannot_be_reused(self):
        evidence=self.root/'evidence'
        evidence.mkdir()
        (evidence/'erc.json').write_text('{}')
        with self.assertRaises(FileExistsError):
            self.run_validation()

    def test_invalid_rules_stop_before_any_tool_execution(self):
        self.rules.write_text('{"per_net_min_width_mm":false}')
        with patch.object(validation,'run_command') as command:
            result=validation.validate_project(self.project,self.config,self.root/'evidence',self.rules)
            command.assert_not_called()
        self.assertEqual(result['status'],'fail')
        self.assertEqual(result['checks']['erc']['status'],'not_run')

    def test_report_items_and_severities_are_validated(self):
        path=self.root/'bad-report.json'
        base={'kicad_version':'10.0','source':'board.kicad_pcb','date':'2026-11-07',
              'violations':[],'unconnected_items':[],'schematic_parity':[]}
        for bad in [{'type':'test','description':'test','severity':None,'items':[]},
                    {'type':'test','description':'test','severity':'error','items':[{'uuid':'x'}]}]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                path.write_text(json.dumps(dict(base,violations=[bad])))
                validation.report_count(path,'drc')

    def test_invalid_geometry_rules_fail(self):
        self.rules.write_text('{"min_track_width_mm":-1}')
        self.assertEqual(self.run_validation()['checks']['geometry']['status'], 'error')

    def test_width_layer_heading_and_vias_are_enforced(self):
        board = self.project.with_suffix('.kicad_pcb')
        result = board_audit.audit(board, {'min_track_width_mm':0.5, 'allowed_track_layers':['F.Cu'],
                                          'allowed_segment_headings_deg':[0,90]})
        self.assertEqual(result['status'], 'fail')
        self.assertEqual(len(result['failures']), 3)
        board.write_text(BOARD[:-1]+' (via (at 1 1) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net 1)))')
        self.assertEqual(board_audit.audit(board, {'max_vias':0})['status'], 'fail')

    def test_unknown_and_nonfinite_constraints_rejected(self):
        for rules in ({'min_width': 0.2}, {'min_track_width_mm':float('nan')},
                      {'outline_size_mm':[40]}, {'max_vias':True}):
            with self.subTest(rules=rules), self.assertRaises(ValueError):
                board_audit.audit(self.project.with_suffix('.kicad_pcb'), rules)

    def test_non_rectangular_outline_needs_review(self):
        board=self.project.with_suffix('.kicad_pcb')
        board.write_text(BOARD.replace('gr_rect','gr_line'))
        self.assertEqual(board_audit.audit(board, {'outline_size_mm':[40,40]})['status'], 'needs_review')

    def test_unrouted_board_does_not_pass_width_check(self):
        board=self.project.with_suffix('.kicad_pcb')
        board.write_text('(kicad_pcb (net 0 ""))')
        self.assertEqual(board_audit.audit(board, {'min_track_width_mm':0.25})['status'], 'needs_review')


if __name__ == '__main__':
    unittest.main()
