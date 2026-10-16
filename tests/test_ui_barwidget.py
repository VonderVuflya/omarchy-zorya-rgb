"""Exercise the production bar widget across QML URL/type boundaries."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BarWidgetUiTests(unittest.TestCase):
    def test_loader_panel_works_across_component_url_identity(self):
        runner = shutil.which('qmltestrunner') or '/usr/lib/qt6/bin/qmltestrunner'
        if not Path(runner).exists():
            self.skipTest('Qt Quick Test runner is unavailable')
        with tempfile.TemporaryDirectory(prefix='zorya-barwidget-') as folder:
            root = Path(folder)
            ui = root / 'imports/qs/Ui'
            ui.mkdir(parents=True)
            (ui / 'qmldir').write_text('module qs.Ui\nBarWidget 1.0 BarWidget.qml\nBarIconButton 1.0 BarIconButton.qml\n')
            (ui / 'BarWidget.qml').write_text('''import QtQuick
Item {
    property string moduleName: ""
    property var bar: null
    property var settings: null
}
''')
            (ui / 'BarIconButton.qml').write_text('''import QtQuick
Item {
    property var bar: null
    property string text: ""
    property string tooltipText: ""
    signal pressed(int mouseButton)
    implicitWidth: 32
    implicitHeight: 28
}
''')
            panel = '''import QtQuick
Item {
    property bool opened: false
    property bool popoutSwitchClosing: false
    property var bar: null
    property var settings: null
    property var anchorItem: null
    property var hostWidget: null
    property QtObject backend: QtObject {
        property bool updateAvailable: false
        property var updateInfo: ({latest_version: "1.1.0"})
    }
    function open() { opened = true }
    function close() { opened = false }
    function closeForPopoutSwitch() { popoutSwitchClosing = true; close() }
}
'''
            # Equal panel APIs loaded from different URLs have different QML
            # component types, as with Omarchy's qs imports versus file URLs.
            (root / 'Panel.qml').write_text(panel)
            (root / 'alternate').mkdir()
            (root / 'alternate/Panel.qml').write_text(panel)
            source = (ROOT / 'BarWidget.qml').read_text()
            self.assertIn('source: Qt.resolvedUrl("Panel.qml")', source)
            (root / 'BarWidget.qml').write_text(source.replace(
                'source: Qt.resolvedUrl("Panel.qml")',
                'source: Qt.resolvedUrl("alternate/Panel.qml")'))
            (root / 'tst_barwidget.qml').write_text('''import QtQuick
import QtTest
import "." as Zorya
TestCase {
    id: test
    name: "ZoryaBarWidgetUrlIdentity"
    width: 400; height: 200; visible: true; when: windowShown
    Zorya.BarWidget {
        id: widget
        bar: ({fixture: "bar"})
        settings: ({fixture: "settings"})
    }
    function test_panel_actions_and_update_indicator() {
        tryVerify(function() { return widget.panel !== null }, 1000,
                  "Loader item was rejected because its URL has a different QML type identity")
        compare(widget.panel.bar, widget.bar)
        compare(widget.panel.settings, widget.settings)
        compare(widget.panel.hostWidget, widget)
        var button = widget.panel.anchorItem
        verify(button !== null)
        verify(widget.implicitWidth > 0)
        verify(widget.implicitHeight > 0)
        compare(widget.opened, false)
        widget.open()
        compare(widget.opened, true)
        widget.close()
        compare(widget.opened, false)
        button.pressed(Qt.LeftButton)
        compare(widget.opened, true)
        button.pressed(Qt.LeftButton)
        compare(widget.opened, false)
        widget.open()
        widget.closeForPopoutSwitch()
        compare(widget.opened, false)
        compare(widget.popoutSwitchClosing, true)
        compare(button.tooltipText, "ZoryaRGB")
        verify(button.text !== "↑")
        widget.panel.backend.updateAvailable = true
        compare(button.text, "↑")
        compare(button.tooltipText, "ZoryaRGB · Update to 1.1.0")
        widget.panel.backend.updateAvailable = false
        compare(button.tooltipText, "ZoryaRGB")
        verify(button.text !== "↑")
    }
}
''')
            result = subprocess.run(
                [runner, '-platform', 'offscreen', '-import', str(root / 'imports'), '-input', str(root)],
                env=dict(os.environ, PATH='/usr/bin:/bin', QT_QUICK_BACKEND='software'),
                text=True, capture_output=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
