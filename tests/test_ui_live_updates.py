import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LiveColorTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is needed')
    def test_continuous_changes_send_before_drag_stops_and_keep_last_color(self):
        with tempfile.TemporaryDirectory(prefix='zorya-live-') as folder:
            root = Path(folder)
            (root/'bin').mkdir()
            shutil.copyfile(ROOT/'Service.qml', root/'Service.qml')
            command = root/'bin/zorya-rgb'
            command.write_text(textwrap.dedent('''\
                #!/usr/bin/env python3
                import json,pathlib,sys,time
                root=pathlib.Path(__file__).resolve().parents[1]
                args=sys.argv[1:]
                if args[0]=='set':
                    with (root/'writes').open('a') as stream:
                        stream.write(json.dumps([time.monotonic(),json.loads(args[2])])+'\\n')
                print(json.dumps({'connected':True} if args[0]=='status' else {}))
            '''))
            command.chmod(0o755)
            (root/'shell.qml').write_text(textwrap.dedent('''\
                import QtQuick
                import Quickshell
                ShellRoot {
                    property Service backend: Service {}
                    property int frames: 0
                    Timer {
                        interval: 30; running: true; repeat: true
                        onTriggered: {
                            frames++
                            backend.update({color: '#' + frames.toString(16).padStart(6, '0')})
                            if (frames === 30) stop()
                        }
                    }
                    Timer { interval: 1800; running: true; onTriggered: Qt.quit() }
                }
            '''))
            result = subprocess.run(
                ['quickshell', '--no-color', '-p', str(root/'shell.qml')],
                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                capture_output=True, text=True, timeout=8,
            )
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            writes = [json.loads(line) for line in (root/'writes').read_text().splitlines()]
            self.assertGreaterEqual(len(writes), 4, 'Color only sent after continuous motion stopped')
            self.assertGreater(writes[-1][0]-writes[0][0], .4)
            self.assertEqual(writes[-1][1]['color'], '#00001e')
            self.assertLessEqual(len(writes), 12, 'Motion must coalesce, not queue every frame')
