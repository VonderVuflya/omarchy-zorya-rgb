#!/usr/bin/env python3
"""Validate QML against the installed Omarchy shell imports."""
from pathlib import Path
import shutil
import subprocess
import tempfile

root=Path(__file__).resolve().parent.parent
binary=shutil.which('qmllint') or '/usr/lib/qt6/bin/qmllint'
shell=Path('/usr/share/omarchy/shell')
if not Path(binary).is_file() or not shell.is_dir():
    raise SystemExit('Qt6 qmllint and an installed Omarchy shell are required')
with tempfile.TemporaryDirectory(prefix='zorya-qml-') as temporary:
    (Path(temporary)/'qs').symlink_to(shell,target_is_directory=True)
    raise SystemExit(subprocess.run([binary,'-I',temporary,*[str(root/name) for name in ('BarWidget.qml','Panel.qml','Service.qml','ColorWheel.qml')]]).returncode)
