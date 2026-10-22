#!/usr/bin/env python3
"""Fail when release version fields disagree, or a pushed tag does not match them."""
from pathlib import Path
import json
import os
import re
import sys
import tomllib

root=Path(__file__).resolve().parent.parent
lock=json.loads((root/'package-lock.json').read_text())
versions={
 'manifest.json':json.loads((root/'manifest.json').read_text())['version'],
 'pyproject.toml':tomllib.loads((root/'pyproject.toml').read_text())['project']['version'],
 'zorya_rgb/__init__.py':re.search(r"__version__\s*=\s*'([^']+)'",(root/'zorya_rgb/__init__.py').read_text()).group(1),
 'package.json':json.loads((root/'package.json').read_text())['version'],
 'package-lock.json':lock['version'],
 'package-lock.json packages[""]':lock['packages']['']['version'],
}
tag=sys.argv[1] if len(sys.argv)>1 else (os.environ.get('GITHUB_REF_NAME','') if os.environ.get('GITHUB_REF_TYPE')=='tag' else '')
if tag: versions['tag '+tag]=tag.removeprefix('v')
if len(set(versions.values()))!=1:
    raise SystemExit('Version mismatch:\n'+'\n'.join(f'  {name}: {value}' for name,value in versions.items()))
print('Version '+next(iter(versions.values()))+' is consistent')
