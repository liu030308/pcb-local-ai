import json
import tempfile
import unittest
from pathlib import Path

import board_audit
import schema_checks

FIXTURES=Path(__file__).resolve().parents[1]/'examples/fixtures'


class BoardAuditTests(unittest.TestCase):
    def test_native_fixture_keeps_unicode_and_parentheses_inside_strings(self):
        board=board_audit.parse_board((FIXTURES/'minimal.kicad_pcb').read_text(encoding='utf-8'))
        self.assertIn('地線 (GND)',[n[2] for n in board_audit.children(board,'net')])

    def test_escaped_quotes_and_backslashes_are_preserved(self):
        text='quote " and slash \\ and (bracket)'
        board=board_audit.parse_board('(kicad_pcb (property "note" '+json.dumps(text)+'))')
        self.assertEqual(board_audit.field(board,'property')[1],text)

    def test_malformed_tokens_and_roots_are_rejected(self):
        for text in ['(kicad_pcb (net 1 "unterminated))','(kicad_pcb))','(kicad_pcb',
                     '(kicad_sch)','(kicad_pcb)(kicad_pcb)','outside (kicad_pcb)']:
            with self.subTest(text=text),self.assertRaises(ValueError):
                board_audit.parse_board(text)

    def test_fixture_track_measurements_and_per_net_rules(self):
        result=board_audit.audit(FIXTURES/'minimal.kicad_pcb',{'per_net_min_width_mm':{'地線 (GND)':0.5}})
        self.assertEqual(result['status'],'fail')
        self.assertEqual(result['tracks'][0]['width_mm'],0.3)

    def test_complex_edge_cuts_do_not_get_a_false_pass(self):
        result=board_audit.audit(FIXTURES/'complex-outline.kicad_pcb',{'outline_size_mm':[15,10]})
        self.assertEqual(result['status'],'needs_review')
        self.assertIsNone(result['rectangular_outline_size_mm'])

    def test_falsy_wrong_type_per_net_rules_are_rejected(self):
        for value in [False,0,[], '']:
            with self.subTest(value=value),self.assertRaises(ValueError):
                schema_checks.validate_rules({'per_net_min_width_mm':value})

    def test_nested_rule_values_and_unknown_fields_are_checked(self):
        for value in [{'per_net_min_width_mm':{'GND':False}}, {'allowed_track_layers':['']},
                      {'typo':1}, {'min_track_width_mm':float('inf')}]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                schema_checks.validate_rules(value)


if __name__=='__main__':
    unittest.main()
