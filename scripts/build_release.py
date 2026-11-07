"""Build a reproducible portable archive with clean configuration and checksums."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def build(root, output):
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    archive = output / 'pcb-local-ai.zip'
    root_files = {'README.md', 'SKILL.md', 'CHANGELOG.md', 'LICENSE', 'VERSION', 'start.bat',
                  'config.example.json', '.gitignore', '.gitattributes'}
    content = {}
    for file in root.rglob('*'):
        relative = file.relative_to(root)
        if not file.is_file() or file.is_symlink() or any(part in {'__pycache__', '.git', 'outputs', 'dist', '.venv'} for part in relative.parts):
            continue
        if relative.as_posix() in root_files or (relative.parts[0] in {'scripts', 'rules', 'examples', 'docs', '.github', 'schemas'}
                                                and file.suffix in {'.py', '.json', '.md', '.yml', '.kicad_pro', '.kicad_sch', '.kicad_pcb'}):
            data = file.read_bytes().replace(b'\r\n', b'\n')
            content[relative.as_posix()] = data.replace(b'\n', b'\r\n') if file.suffix == '.bat' else data
    for required in ('LICENSE', 'VERSION', 'config.example.json', 'start.bat', 'scripts/menu.py'):
        if required not in content:
            raise ValueError(f'發布缺少必要檔案：{required}')
    json.loads(content['config.example.json'])  # Validate template; each installation initializes its own config.
    with ZipFile(archive, 'w', ZIP_DEFLATED) as zipped:
        for name, data in sorted(content.items()):
            info = ZipInfo('pcb-local-ai/' + name, date_time=(1980,1,1,0,0,0))
            info.create_system = 3
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zipped.writestr(info, data)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output/'SHA256SUMS').write_text(f'{checksum}  {archive.name}\n', encoding='utf-8')
    return archive


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'dist')
    args=parser.parse_args()
    print(build(ROOT,args.output_dir))
