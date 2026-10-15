"""Render the production inline controls and exercise their Qt semantics."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RoundedControlsTests(unittest.TestCase):
    def test_rounded_controls_keep_pointer_keyboard_and_selection_behavior(self):
        runner = shutil.which("qmltestrunner") or "/usr/lib/qt6/bin/qmltestrunner"
        if not Path(runner).exists():
            self.skipTest("Qt Quick Test runner is unavailable")
        source = (ROOT / "Panel.qml").read_text()
        controls = source[source.index("    component RoundedButton:"):source.index("    Ui.KeyboardPanel {")]
        controls = controls.replace("Commons.Color.accent", "root.accent")
        blend = re.search(r"function controlFill\(amount\) \{.*?\n    \}", source, re.DOTALL).group()
        fixture = '''pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtTest
TestCase {
    id: root
    name: "ZoryaRoundedControls"
    width: 500; height: 260; visible: true; when: windowShown
    property color foreground: "#BEBEBE"
    property color surface: "#121212"
    property color accent: "#E68E0D"
    BLEND
    COMPONENTS
    RoundedButton { id: button; x: 10; y: 10; width: 130; height: 30; text: "Action" }
    RoundedTabButton { id: tab; x: 160; y: 10; width: 130; height: 30; text: "Devices" }
    RoundedComboBox { id: combo; x: 10; y: 60; width: 180; model: ["Static", "Pulse"] }
    RoundedTextField { id: field; x: 10; y: 105; width: 180; text: "#FFFFFF" }
    RoundedSpinBox { id: spin; x: 10; y: 150; width: 100; from: 0; to: 255; value: 30 }
    SignalSpy { id: clicked; target: button; signalName: "clicked" }
    function test_rounded_surfaces() {
        for (var control of [button, tab, combo, field, spin]) {
            verify(control.background.radius >= 8)
            compare(control.background.color.a, 1)
        }
        verify(spin.up.indicator.radius > 0)
        verify(spin.down.indicator.radius > 0)
    }
    function test_button_hover_press_and_keyboard_focus() {
        mouseMove(root, 450, 230)
        wait(110)
        var idle = button.background.color.toString()
        mouseMove(button, 20, 15)
        wait(110)
        verify(button.hovered)
        verify(button.background.color.toString() !== idle)
        mousePress(button, 20, 15)
        verify(button.down)
        mouseRelease(button, 20, 15)
        compare(clicked.count, 1)
        field.forceActiveFocus(Qt.TabFocusReason)
        button.forceActiveFocus(Qt.TabFocusReason)
        verify(button.visualFocus)
        compare(button.background.border.color, root.accent)
        keyClick(Qt.Key_Space)
        compare(clicked.count, 2)
    }
    function test_tab_selection_and_spin_buttons() {
        mouseClick(tab, 20, 15)
        verify(tab.checked)
        mouseClick(spin.up.indicator, 10, 5)
        compare(spin.value, 31)
        mouseClick(spin.down.indicator, 10, 5)
        compare(spin.value, 30)
        combo.forceActiveFocus()
        keyClick(Qt.Key_Down)
        compare(combo.currentIndex, 1)
    }
}
'''.replace("BLEND", blend).replace("COMPONENTS", controls)
        with tempfile.TemporaryDirectory(prefix="zorya-rounded-test-") as temporary:
            (Path(temporary) / "tst_rounded.qml").write_text(fixture)
            result = subprocess.run(
                [runner, "-platform", "offscreen", "-input", temporary],
                env=dict(os.environ, QT_QUICK_BACKEND="software", QT_QUICK_CONTROLS_STYLE="Fusion"),
                text=True, capture_output=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
