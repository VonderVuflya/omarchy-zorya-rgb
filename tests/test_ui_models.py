import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ColorModelTests(unittest.TestCase):
    def test_fusion_controls_render_readable_opaque_surfaces(self):
        runner = shutil.which("qmltestrunner") or "/usr/lib/qt6/bin/qmltestrunner"
        if not Path(runner).exists():
            self.skipTest("Qt Quick Test runner is unavailable")
        panel = (ROOT / "Panel.qml").read_text()
        palette = "\n".join(line.strip() for line in panel.splitlines() if line.strip().startswith("palette."))
        palette = palette.replace("Commons.Color.accent", "root.accent")
        blend = re.search(r"function controlFill\(amount\) \{.*?\n    \}", panel, re.DOTALL).group()
        fixture = '''import QtQuick
import QtQuick.Controls
import QtTest
TestCase {
    id: root
    name: "ZoryaContrast"
    width: 300; height: 200; visible: true; when: windowShown
    property color foreground: "#BEBEBE"
    property color surface: "#121212"
    property color accent: "#E68E0D"
    BLEND
    Pane {
        anchors.fill: parent
        PALETTE
        Button { id: button; x: 10; y: 10; width: 200; height: 35; text: "Readable button" }
        TabButton { id: tab; x: 10; y: 60; width: 200; height: 30; text: "Readable tab" }
        ComboBox { id: combo; x: 10; y: 105; width: 200; height: 35; model: ["Readable choice"] }
    }
    function test_background_contrast() {
        for (var control of [button, tab, combo]) {
            compare(control.palette.button.a, 1)
            compare(control.palette.window.a, 1)
            verify(control.palette.buttonText.r > 0.65)
            var image = grabImage(control)
            verify(image.red(6, 6) < 100 && image.green(6, 6) < 100 && image.blue(6, 6) < 100,
                   "Fusion chrome unexpectedly rendered a light background")
        }
    }
}
'''.replace("BLEND", blend).replace("PALETTE", palette)
        with tempfile.TemporaryDirectory(prefix="zorya-contrast-test-") as temporary:
            path = Path(temporary) / "tst_contrast.qml"
            path.write_text(fixture)
            result = subprocess.run(
                [runner, "-platform", "offscreen", "-input", str(temporary)],
                env=dict(os.environ, QT_QUICK_BACKEND="software", QT_QUICK_CONTROLS_STYLE="Fusion"),
                text=True, capture_output=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_color_wheel_pointer_and_keyboard(self):
        runner = shutil.which("qmltestrunner") or "/usr/lib/qt6/bin/qmltestrunner"
        if not Path(runner).exists():
            self.skipTest("Qt Quick Test runner is unavailable")
        with tempfile.TemporaryDirectory(prefix="zorya-wheel-test-") as temporary:
            directory = Path(temporary)
            fixture = directory / "tests"
            fixture.mkdir()
            for name in ("ColorWheel.qml", "ColorModel.js"):
                shutil.copyfile(ROOT / name, directory / name)
            shutil.copyfile(ROOT / "tests/test_ui_colorwheel.qml", fixture / "tst_colorwheel.qml")
            result = subprocess.run(
                [runner, "-platform", "offscreen", "-input", str(fixture)],
                env=dict(os.environ, QT_QUICK_BACKEND="software"),
                text=True, capture_output=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is needed for the JS color model")
    def test_color_round_trips_white_and_invalid_inputs(self):
        source = (ROOT / "ColorModel.js").read_text().replace(".pragma library", "")
        script = source + """
const assert = require('node:assert/strict');
assert.equal(normalizeHex('  abcdef '), '#ABCDEF');
assert.equal(normalizeHex('#123'), null);
assert.equal(normalizeHex('#GGGGGG'), null);
assert.equal(fromRgb(256,0,0), null);
assert.equal(fromHsv(0.3,0,1), '#FFFFFF');
assert.equal(pointColor(100,100,200), '#FFFFFF');
assert.equal(pointColor(200,100,200), '#FF0000');
assert.equal(fromHsv(-1,1,1), '#FF0000');
for (const hex of ['#FFFFFF','#000000','#FF0000','#808080','#B693EC','#0A71FE']) {
    const value = hsv(hex);
    assert.equal(fromHsv(value.h,value.s,value.v), hex);
}
"""
        subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    def test_manifest_uses_native_bar_widget(self):
        manifest = json.loads((ROOT / "manifest.json").read_text())
        self.assertEqual(manifest["id"], "vondervuflya.zorya-rgb")
        self.assertEqual(manifest["kinds"], ["bar-widget"])
        self.assertEqual(manifest["entryPoints"]["barWidget"], "BarWidget.qml")


class ServiceIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("quickshell"), "Quickshell is needed for process integration")
    def test_debounce_action_order_argv_and_stale_status(self):
        with tempfile.TemporaryDirectory(prefix="zorya-ui-test-") as temporary:
            directory = Path(temporary)
            (directory / "bin").mkdir()
            shutil.copyfile(ROOT / "Service.qml", directory / "Service.qml")
            mock = directory / "bin/zorya-rgb"
            mock.write_text(textwrap.dedent('''\
                #!/usr/bin/env python3
                import json, pathlib, sys, time
                root = pathlib.Path(__file__).resolve().parents[1]
                args = sys.argv[1:]
                with (root / 'commands.jsonl').open('a') as stream:
                    stream.write(json.dumps(args) + '\\n')
                path = root / 'state.json'
                state = json.loads(path.read_text()) if path.exists() else {'color':'#FFFFFF','brightness':100,'devices':[],'presets':[],'connected':True}
                if args[0] == 'status':
                    time.sleep(0.2)
                    print(json.dumps(state))
                elif args[0] == 'devices':
                    print(json.dumps({'devices': [], 'error': None}))
                elif args[0] == 'set':
                    state.update(json.loads(args[2]))
                    path.write_text(json.dumps(state))
                    print(json.dumps(state))
                elif args[0] == 'doctor':
                    print(json.dumps({'ok': True, 'components': {}, 'wireless_devices': [{'device_id':'wireless:test-device','name':'Test wireless device','is_unbound_wireless':True}]}))
                elif args[0] == 'pair':
                    print(json.dumps({'ok': True, 'error': None}))
                else:
                    print(json.dumps(state))
            '''))
            mock.chmod(0o755)
            name = 'Scene "quoted"; $(touch SHOULD_NOT_EXIST)'
            device_id = 'wireless:test-device "literal"; $(touch SHOULD_NOT_EXIST)'
            (directory / "shell.qml").write_text(textwrap.dedent(f'''\
                import QtQuick
                import Quickshell
                ShellRoot {{
                    property Service backend: Service {{}}
                    Timer {{
                        interval: 30; running: true
                        onTriggered: {{
                            backend.update({{color: "#1245AB"}})
                            backend.update({{brightness: 37}})
                        }}
                    }}
                    Timer {{
                        interval: 60; running: true
                        onTriggered: {{
                            backend.command(["preset", "save", {json.dumps(name)}])
                            backend.command(["pair", "--device", {json.dumps(device_id)}], "pair")
                            backend.command(["doctor"], "doctor")
                        }}
                    }}
                    Timer {{
                        interval: 1500; running: true
                        onTriggered: {{
                            if (backend.state.color !== "#1245AB" || backend.state.brightness !== 37 || backend.busy || !backend.diagnostics || !backend.diagnostics.ok) {{
                                console.error("ZORYA_TEST_FAILED", JSON.stringify(backend.state), backend.error)
                                Qt.exit(1)
                            }} else {{ console.log("ZORYA_TEST_OK"); Qt.quit() }}
                        }}
                    }}
                }}
            '''))
            environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
            process = subprocess.run(
                ["quickshell", "--no-color", "-p", str(directory / "shell.qml")],
                env=environment, capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            self.assertIn("ZORYA_TEST_OK", process.stdout + process.stderr)
            commands = [json.loads(line) for line in (directory / "commands.jsonl").read_text().splitlines()]
            writes = [command for command in commands if command[0] == "set"]
            self.assertEqual(len(writes), 1, commands)
            self.assertEqual(json.loads(writes[0][2]), {"color": "#1245AB", "brightness": 37})
            self.assertIn(["preset", "save", name], commands)
            pair = ["pair", "--device", device_id]
            self.assertIn(pair, commands)
            self.assertEqual(commands.count(["doctor"]), 2, "Successful pairing must refresh diagnostics automatically")
            self.assertLess(commands.index(pair), commands.index(["doctor"]))
            self.assertLess(commands.index(writes[0]), commands.index(["preset", "save", name]))
            self.assertFalse((directory / "SHOULD_NOT_EXIST").exists())


if __name__ == "__main__":
    unittest.main()
