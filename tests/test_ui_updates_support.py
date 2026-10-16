"""Offscreen process contracts for explicit updates and private support previews."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is needed')
class UpdatesSupportUiTests(unittest.TestCase):
    def scenario(self, body, markers=()):
        with tempfile.TemporaryDirectory(prefix='zorya-support-ui-') as folder:
            root = Path(folder)
            (root / 'bin').mkdir()
            shutil.copyfile(ROOT / 'Service.qml', root / 'Service.qml')
            cli = root / 'bin/zorya-rgb'
            cli.write_text(textwrap.dedent('''\
                #!PYTHON
                import json,pathlib,sys,time
                root=pathlib.Path(__file__).resolve().parents[1]
                args=sys.argv[1:]
                with (root/'calls').open('a') as out: out.write(json.dumps(args)+'\\n')
                if args[:2]==['updates','check']:
                    if (root/'failed-check').exists():
                        print(json.dumps(dict(ok=False,error='GitHub temporarily unavailable')))
                        sys.exit(1)
                    print(json.dumps(dict(ok=True,installed_version='1.0.0',latest_version='1.1.0',update_available=not (root/'current').exists(),tag='v1.1.0',release_url='https://github.com/example/project/releases/tag/v1.1.0')))
                elif args[:2]==['updates','apply']:
                    if (root/'successful-update').exists():
                        import atexit
                        atexit.register(lambda: (root/'apply-finished').touch())
                        print(json.dumps(dict(ok=True,reload_required=True)),flush=True)
                        time.sleep(.12)
                        sys.exit(0)
                    print(json.dumps(dict(ok=False,error='Update download failed')))
                    sys.exit(1)
                elif args[:2]==['support','report']:
                    if (root/'failed-report').exists():
                        (root/'failed-report').unlink()
                        print(json.dumps(dict(ok=False,error='Report storage unavailable')))
                        sys.exit(1)
                    print(json.dumps(dict(ok=True,title='ZoryaRGB failure',body='## Error\\nUSB unavailable\\n\\n## Diagnostics\\nVersion: 1.0.0',issue_url='https://github.com/example/project/issues/new?title=ZoryaRGB',fingerprint='fixture',submit_available=(root/'submit-available').exists())))
                elif args[:2]==['support','submit']:
                    time.sleep(.15)
                    if (root/'failed-submit').exists():
                        (root/'failed-submit').unlink()
                        print(json.dumps(dict(ok=False,error='GitHub authorization failed')))
                        sys.exit(1)
                    print(json.dumps(dict(ok=True,issue_url='https://github.com/example/project/issues/123')))
                elif args==['support','copy']: print(json.dumps(dict(ok=True)))
                elif args==['onboarding','plan']:
                    steps=[dict(id='runtime',label='Runtime',description='Install runtime',status='needed',required=True)] if (root/'setup').exists() else []
                    print(json.dumps(dict(ok=True,ready=not steps,steps=steps,summary='Ready')))
                elif args[:2]==['onboarding','run']:
                    time.sleep(.12)
                    print(json.dumps(dict(ok=True,devices=[])))
                elif args[0]=='set':
                    time.sleep(.2)
                    print(json.dumps(dict(ok=True)))
                elif args==['status']:
                    print(json.dumps(dict(connected=True,color='#123456',error=None,last_error=dict(message='USB unavailable',operation='restore',at='fixture-event'))))
                else: print(json.dumps(dict(devices=[],error=None)))
            ''').replace('#!PYTHON', '#!' + sys.executable))
            cli.chmod(0o755)
            for name in ('omarchy-shell', 'xdg-open', 'gio'):
                helper = root / 'bin' / name
                helper.write_text(textwrap.dedent('''\
                    #!PYTHON
                    import json,pathlib,sys,time
                    root=pathlib.Path(__file__).resolve().parents[1]
                    name=pathlib.Path(__file__).name
                    with (root/'calls').open('a') as out:
                        out.write(json.dumps([name]+sys.argv[1:])+'\\n')
                    if name=='omarchy-shell':
                        if not (root/'apply-finished').exists(): sys.exit(9)
                        time.sleep(.12)
                ''').replace('#!PYTHON', '#!' + sys.executable))
                helper.chmod(0o755)
            for marker in markers:
                (root / marker).touch()
            (root / 'shell.qml').write_text('''import QtQuick
import Quickshell
ShellRoot {
    property Service backend: Service { active: true }
    property int phase: 0
    property int ticks: 0
    property bool jsonAccepted: false
    property bool updateExited: false
    property bool rescanStarted: false
    property bool rescanFinished: false
    Connections {
        target: backend
        function onUpdateMessageChanged() {
            if (backend.updateMessage === "Update installed.") {
                jsonAccepted = true
                console.log("UPDATE_JSON_ACCEPTED")
            }
        }
    }
    Connections {
        target: backend.action
        function onExited(code) {
            if (backend.operation === "update" && code === 0) {
                updateExited = true
                console.log("UPDATE_PROCESS_EXITED")
            }
        }
    }
    Connections {
        target: backend.pluginReload
        function onRunningChanged() {
            if (backend.pluginReload.running) {
                if (!jsonAccepted || !updateExited || backend.action.running || backend.updateAvailable)
                    fail("rescan started before successful update completed")
                rescanStarted = true
                console.log("PLUGIN_RESCAN_STARTED")
            }
        }
        function onExited(code) {
            if (code !== 0) fail("mock rescan failed")
            rescanFinished = true
        }
    }
    function fail(message) { console.log("TEST_FAILURE " + message); Qt.quit() }
    function pass() { console.log("TEST_PASSED"); Qt.quit() }
    Timer {
        interval: 30; running: true; repeat: true
        onTriggered: {
            ticks++
''' + textwrap.indent(body, '            ') + '''
            if (ticks > 150) { fail("timeout") }
        }
    }
}
''')
            result = subprocess.run(
                ['quickshell', '--no-color', '-p', str(root / 'shell.qml')],
                env=dict(os.environ, QT_QPA_PLATFORM='offscreen', PATH=str(root / 'bin') + ':/usr/bin:/bin', BROWSER=str(root / 'bin' / 'xdg-open')),
                capture_output=True, text=True, timeout=8,
            )
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertNotIn('TEST_FAILURE', output)
            self.assertIn('TEST_PASSED', output)
            if 'successful-update' in markers:
                self.assertLess(output.index('UPDATE_JSON_ACCEPTED'), output.index('PLUGIN_RESCAN_STARTED'), output)
                self.assertLess(output.index('UPDATE_PROCESS_EXITED'), output.index('PLUGIN_RESCAN_STARTED'), output)
            return [json.loads(line) for line in (root / 'calls').read_text().splitlines()]

    def test_first_open_checks_only_and_arrow_follows_boolean(self):
        for markers, available in [((), True), (('current',), False)]:
            with self.subTest(available=available):
                calls = self.scenario('''if (backend.updateInfo && !backend.updateChecking) {
    if (backend.updateAvailable !== EXPECTED) fail("wrong arrow visibility")
    else pass()
}'''.replace('EXPECTED', str(available).lower()), markers)
                self.assertEqual(calls.count(['updates', 'check']), 1)
                self.assertFalse(any(args[0] in ('set', 'setup', 'pair') or args[:2] == ['updates', 'apply'] for args in calls))
                self.assertFalse(any(args[0] == 'support' for args in calls))

    def test_failed_check_preserves_lighting_and_sticky_backend_error(self):
        calls = self.scenario('''if (!backend.updateChecking && backend.updateError && backend.state.color === "#123456" && !backend.busy) {
    if (backend.updateAvailable || backend.updateInfo !== null) fail("failed check announced update")
    else if (!backend.lastError) fail("missing sticky error")
    else if (phase === 0) { backend.refresh(); phase = 1 }
    else if (ticks > 15) pass()
}''', ('failed-check',))
        self.assertFalse(any(args[:2] == ['updates', 'apply'] for args in calls))

    def test_error_report_requires_click_retry_and_preview_never_opens_browser(self):
        calls = self.scenario('''if (phase === 0 && backend.lastError === "USB unavailable" && !backend.busy) {
    backend.refresh()
    phase = 1
} else if (phase === 1 && ticks > 12) {
    if (backend.lastError !== "USB unavailable" || backend.lastErrorOperation !== "restore") fail("error lost on polling")
    else { backend.prepareReport(); phase = 2 }
} else if (phase === 2 && backend.reportError) {
    if (backend.reportBusy || backend.supportReport) fail("failed report not retryable")
    else { backend.prepareReport(); phase = 3 }
} else if (phase === 3 && backend.supportReport && !backend.reportBusy) {
    if (backend.supportReport.body.indexOf("## Diagnostics") < 0 || !backend.supportReport.issue_url) fail("missing preview")
    else { backend.copyReport(); phase = 4 }
} else if (phase === 4 && backend.supportMessage) pass()
''', ('failed-report',))
        reports = [args for args in calls if args[:2] == ['support', 'report']]
        self.assertEqual(len(reports), 2)
        self.assertEqual(reports[0][2:], ['--error=USB unavailable', '--operation=restore'])
        self.assertIn(['support', 'copy'], calls)
        panel = (ROOT / 'Panel.qml').read_text()
        self.assertIn('textFormat: TextEdit.MarkdownText', panel)
        self.assertIn('onClicked: Qt.openUrlExternally(root.backend.supportReport.issue_url)', panel)
        self.assertNotIn('openUrlExternally', (ROOT / 'Service.qml').read_text())
        self.assertNotIn('JSON.stringify(root.backend.diagnostics', panel)

    def test_full_report_submit_is_explicit_retryable_and_never_opens_browser(self):
        calls = self.scenario('''if (phase === 0 && backend.lastError && !backend.busy) {
    backend.prepareReport(); phase = 1
} else if (phase === 1 && backend.supportReport && !backend.reportBusy && ticks > 12) {
    if (!backend.supportReport.submit_available || backend.createdIssueUrl || backend.reportOperation !== "report")
        fail("report submitted before explicit preview action")
    else { backend.submitReport(); backend.installUpdate(); backend.submitReport(); phase = 2 }
} else if (phase === 2 && backend.reportError && !backend.reportBusy) {
    if (!backend.supportReport || backend.supportReport.fingerprint !== "fixture" || backend.createdIssueUrl)
        fail("failed submission lost reviewed report")
    else { backend.refresh(); phase = 3 }
} else if (phase === 3 && ticks > 25 && !backend.busy) {
    if (backend.reportError !== "GitHub authorization failed" || backend.reportOperation !== "submit")
        fail("submission error lost during polling")
    else { backend.retrySupport(); phase = 4 }
} else if (phase === 4 && backend.createdIssueUrl && !backend.reportBusy) {
    if (backend.createdIssueUrl !== "https://github.com/example/project/issues/123" || !backend.supportReport)
        fail("created issue missing")
    else { backend.submitReport(); phase = 5 }
} else if (phase === 5 && ticks > 35) pass()
''', ('submit-available', 'failed-submit'))
        submissions = [args for args in calls if args[:2] == ['support', 'submit']]
        self.assertEqual(submissions, [['support', 'submit', '--fingerprint', 'fixture']] * 2)
        self.assertFalse(any(args[:2] == ['updates', 'apply'] for args in calls))
        self.assertEqual(sum(args[:2] == ['support', 'report'] for args in calls), 1)
        self.assertFalse(any(args[0] in ('xdg-open', 'gio') for args in calls))
        panel = (ROOT / 'Panel.qml').read_text()
        self.assertIn('onClicked: root.backend.submitReport()', panel)
        self.assertIn('onClicked: Qt.openUrlExternally(root.backend.createdIssueUrl)', panel)
        self.assertNotIn('openUrlExternally', (ROOT / 'Service.qml').read_text())

    def test_missing_submit_capability_keeps_browser_and_copy_fallback(self):
        calls = self.scenario('''if (phase === 0 && backend.lastError && !backend.busy) {
    backend.prepareReport(); phase = 1
} else if (phase === 1 && backend.supportReport && !backend.reportBusy) {
    if (backend.supportReport.submit_available || !backend.supportReport.issue_url) fail("missing browser fallback")
    else { backend.submitReport(); backend.copyReport(); phase = 2 }
} else if (phase === 2 && backend.supportMessage) pass()
''')
        self.assertFalse(any(args[:2] == ['support', 'submit'] for args in calls))
        self.assertIn(['support', 'copy'], calls)

    def test_queued_update_blocks_report_prepare_copy_and_submit(self):
        calls = self.scenario('''if (phase === 0 && backend.updateAvailable && !backend.busy) {
    backend.prepareReport(); phase = 1
} else if (phase === 1 && backend.supportReport && !backend.reportBusy) {
    backend.installUpdate()
    if (!backend.updateInstalling) fail("update was not queued")
    else {
        backend.prepareReport()
        backend.copyReport()
        backend.submitReport()
        if (backend.reportBusy || !backend.supportReport || backend.reportOperation !== "report")
            fail("update allowed a support process or erased preview")
        else phase = 2
    }
} else if (phase === 2 && rescanFinished) pass()
''', ('submit-available', 'successful-update'))
        support_calls = [args for args in calls if args[0] == 'support']
        self.assertEqual(len(support_calls), 1)
        self.assertEqual(support_calls[0][:2], ['support', 'report'])
        self.assertEqual(sum(args[:2] == ['updates', 'apply'] for args in calls), 1)

    def test_successful_update_accepts_json_and_exits_before_one_rescan(self):
        calls = self.scenario('''if (phase === 0 && backend.updateAvailable && !backend.busy) {
    backend.update({brightness: 43})
    backend.installUpdate()
    backend.installUpdate()
    backend.update({brightness: 44})
    backend.command(["pair", "--device", "fixture"])
    phase = 1
} else if (phase === 1 && rescanFinished) {
    if (!rescanStarted || !jsonAccepted || !updateExited || backend.updateAvailable || backend.busy)
        fail("incomplete successful update lifecycle")
    else if (backend.state.brightness !== 43 || backend.queue.length || Object.keys(backend.pending).length)
        fail("pending draft lost or blocked changes queued")
    else pass()
}''', ('successful-update',))
        mutations = [args for args in calls if args[0] == 'set' or args[:2] == ['updates', 'apply'] or args[0] == 'omarchy-shell']
        self.assertEqual([args[0] for args in mutations], ['set', 'updates', 'omarchy-shell'])
        self.assertEqual(json.loads(mutations[0][2]), {'brightness': 43})
        self.assertEqual(mutations[1], ['updates', 'apply', '--tag', 'v1.1.0'])
        self.assertEqual(mutations[2], ['omarchy-shell', 'shell', 'rescanPlugins'])
        self.assertFalse(any(args[0] in ('pair', 'xdg-open', 'gio', 'support') for args in calls))
        self.assertNotIn('openUrlExternally', (ROOT / 'Service.qml').read_text())

    def test_update_waits_for_setup_and_rejects_new_mutations(self):
        calls = self.scenario('''if (phase === 0 && backend.updateAvailable && backend.setupPlan && !backend.busy) {
    backend.startSetup(); phase = 1
} else if (phase === 1 && backend.setupRunning) {
    backend.installUpdate()
    backend.update({color: "#000000"})
    backend.command(["pair", "--device", "fixture"])
    phase = 2
} else if (phase === 2 && !backend.busy && backend.lastError === "Update download failed") pass()
''', ('setup',))
        operations = [args for args in calls if args[:2] in (['onboarding', 'run'], ['updates', 'apply'])]
        self.assertEqual([args[:2] for args in operations], [
            ['onboarding', 'run'], ['onboarding', 'run'], ['updates', 'apply']])
        self.assertFalse(any(args[0] in ('set', 'pair') for args in calls))

    def test_update_waits_for_pending_draft_and_serial_action_failure_sticks(self):
        calls = self.scenario('''if (phase === 0 && backend.updateAvailable && !backend.busy) {
    backend.update({brightness: 43})
    backend.installUpdate()
    backend.installUpdate()
    phase = 1
} else if (phase === 1 && !backend.busy && backend.lastError === "Update download failed") {
    backend.refresh(); phase = 2
} else if (phase === 2 && ticks > 25 && !backend.busy) {
    if (backend.lastError !== "Update download failed" || backend.lastErrorOperation !== "update") fail("update error lost")
    else pass()
}''')
        writes = [args for args in calls if args[0] == 'set' or args[:2] == ['updates', 'apply']]
        self.assertEqual([args[0] for args in writes], ['set', 'updates'])
        self.assertEqual(json.loads(writes[0][2]), {'brightness': 43})
        self.assertEqual(writes[1], ['updates', 'apply', '--tag', 'v1.1.0'])
