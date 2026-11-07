"""Run real KiCad CLI checks on temporary empty/invalid fixtures, never a production circuit."""
import json
import shutil
import tempfile
from pathlib import Path

import validate_project


def main():
    cli=shutil.which('kicad-cli')
    if not cli:
        raise SystemExit('KiCad CLI required for integration checks')
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary)
        project=root/'smoke.kicad_pro'
        project.write_text('{}',encoding='utf-8')
        project.with_suffix('.kicad_sch').write_text('(kicad_sch (version 20231120) (generator eeschema) (uuid 11111111-1111-4111-8111-111111111111) (paper "A4") (lib_symbols) (sheet_instances (path "/" (page "1"))))',encoding='utf-8')
        pcb='(kicad_pcb (version 20240108) (generator pcbnew) (general (thickness 1.6)) (paper "A4") (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (44 "Edge.Cuts" user)) (setup (pad_to_mask_clearance 0)) (net 0 "") (gr_rect (start 0 0) (end 20 20) (stroke (width 0.05) (type default)) (fill none) (layer "Edge.Cuts") (uuid 22222222-2222-4222-8222-222222222222)))'
        board=project.with_suffix('.kicad_pcb')
        board.write_text(pcb,encoding='utf-8')
        rules=root/'rules.json'
        rules.write_text(json.dumps({'max_vias':0,'outline_size_mm':[20,20]}),encoding='utf-8')
        result=validate_project.validate_project(project,{'kicad_cli':cli},root/'clean',rules)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        assert all(result['checks'][name]['status']=='pass' for name in ('erc','drc','schematic_parity','geometry')), 'Clean fixture checks must pass with real KiCad'
        assert result['inputs_unchanged'] and not result['engineering_release_approved']
        board.write_text(pcb[:-1]+' (segment (start 0 0) (end 10 10) (width 0.01) (layer "F.Cu") (net 0) (uuid 33333333-3333-4333-8333-333333333333)))',encoding='utf-8')
        invalid=validate_project.validate_project(project,{'kicad_cli':cli},root/'invalid',rules)
        print(json.dumps(invalid,ensure_ascii=False,indent=2))
        assert invalid['checks']['drc']['status']=='fail', 'Real DRC must reject the invalid fixture'
        assert invalid['status']=='fail'
        print('Real KiCad integration checks passed (empty/invalid fixtures; no functional circuit certification).')


if __name__=='__main__':
    main()
