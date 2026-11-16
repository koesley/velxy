"""Read-only multi-language triage command."""
import argparse
import json
import os
from pathlib import Path
from polyglot import inventory

def main():
    parser = argparse.ArgumentParser(description='PATCHWORK polyglot static repository triage')
    parser.add_argument('repository')
    parser.add_argument('--output', required=True, help='New JSON report path')
    parser.add_argument('--max-files', type=int, default=2000)
    args = parser.parse_args()
    report = inventory(args.repository, max_files=args.max_files)
    destination = Path(args.output).expanduser().absolute()
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps({'output': str(destination), 'files_inspected': report['files_inspected'],
                      'findings': len(report['findings']), 'truncated': report['truncated']}))

if __name__ == '__main__':
    main()
