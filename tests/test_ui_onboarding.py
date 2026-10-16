"""Exercise the actual QML process lifecycle without hardware or a daemon."""
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
class OnboardingUiTests(unittest.TestCase):
    def run_scenario(self, body, fail=False, markers=()):
        with tempfile.TemporaryDirectory(prefix='zorya-onboarding-') as folder:
            root = Path(folder)
            (root / 'bin').mkdir()
            shutil.copyfile(ROOT / 'Service.qml', root / 'Service.qml')
            command = root / 'bin/zorya-rgb'
            command.write_text(textwrap.dedent('''\
                #!/usr/bin/env python3
                import json,pathlib,sys,time
                root=pathlib.Path(__file__).resolve().parents[1]
                args=sys.argv[1:]
                with (root/'calls').open('a') as out: out.write(json.dumps(args)+'\\n')
                if args==['onboarding','plan']:
                    keys=['runtime','openrgb','verify']
                    if (root/'change').exists() and (root/'calls').read_text().count('onboarding\", \"plan') > 1: keys.insert(2,'lianli')
                    steps=[dict(id=k,label=k,description='Review '+k,status='ready' if (root/k).exists() else 'needed',required=True) for k in keys]
                    if (root/'blocked').exists(): steps[1]['status']='blocked'
                    print(json.dumps(dict(ok=True,steps=steps,summary='Needs setup',ready=False,error='Preserve cooling service' if (root/'blocked').exists() else None)))
                elif args[:2]==['onboarding','run']:
                    step=args[-1]
                    time.sleep(.12)
                    if step=='openrgb' and (root/'fail').exists():
                        (root/'fail').unlink()
                        print(json.dumps(dict(ok=False,error='USB permission denied',hint='Authorize USB access, then retry.')))
                        sys.exit(1)
                    (root/step).touch()
                    print(json.dumps(dict(ok=True,error=None,devices=[dict(id='fake',name='Fixture')]) if step=='verify' else dict(ok=True,error=None)))
                elif args==['status']:
                    print(json.dumps(dict(connected=(root/'runtime').exists(),error=None)))
                else: print(json.dumps(dict(devices=[],error=None)))
            ''').replace('#!/usr/bin/env python3', '#!' + sys.executable))
            command.chmod(0o755)
            for marker in markers:
                (root / marker).touch()
            if fail:
                (root / 'fail').touch()
            (root / 'shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Io
ShellRoot {
    property Service backend: Service { active: true }
    property int phase: 0
    property int ticks: 0
    Timer {
        interval: 30; running: true; repeat: true
        onTriggered: {
            ticks++
''' + textwrap.indent(body, '            ') + '''
            if (ticks > 180) { console.log("TEST_TIMEOUT"); Qt.quit() }
        }
    }
}
''')
            result = subprocess.run(
                ['quickshell', '--no-color', '-p', str(root / 'shell.qml')],
                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                capture_output=True, text=True, timeout=9,
            )
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertNotIn('TEST_TIMEOUT', output)
            self.assertNotIn('TEST_FAILURE', output)
            self.assertIn('TEST_PASSED', output)
            return [json.loads(line) for line in (root / 'calls').read_text().splitlines()]

    def test_opening_only_reviews_and_needs_no_daemon(self):
        calls = self.run_scenario('''if (backend.setupPlan && !backend.planLoading) {
    if (!backend.needsSetup) console.log("TEST_FAILURE missing setup route")
    backend.active = false
    backend.active = true
    console.log("TEST_PASSED")
    Qt.quit()
}''')
        self.assertEqual(calls.count(['onboarding', 'plan']), 1)
        self.assertFalse(any(args[:2] == ['onboarding', 'run'] for args in calls))
        self.assertFalse(any(args[0] in ('set', 'setup', 'pair') for args in calls))

    def test_failure_polling_close_reopen_and_retry_skip_completed_runtime(self):
        calls = self.run_scenario('''if (phase === 0 && backend.setupPlan && !backend.planLoading) {
    phase = 1
    backend.startSetup()
} else if (phase === 1 && backend.setupRunning) {
    backend.active = false
    phase = 2
} else if (phase === 2 && backend.setupError) {
    backend.active = true
    backend.refresh()
    phase = 3
} else if (phase === 3 && ticks > 45) {
    if (backend.setupError !== "USB permission denied" || backend.setupHint.indexOf("Authorize") < 0)
        console.log("TEST_FAILURE error lost during status polling")
    backend.startSetup()
    phase = 4
} else if (phase === 4 && backend.setupSucceeded) {
    if (backend.setupDeviceCount !== 1 || backend.setupError || backend.setupCompleted !== 2)
        console.log("TEST_FAILURE incorrect success")
    console.log("TEST_PASSED")
    Qt.quit()
}''', fail=True)
        runs = [args[-1] for args in calls if args[:2] == ['onboarding', 'run']]
        self.assertEqual(runs, ['runtime', 'openrgb', 'openrgb', 'verify'])
        self.assertFalse(any(args[0] in ('set', 'pair') for args in calls))
        self.assertEqual(calls.count(['onboarding', 'plan']), 3)

    def test_blocked_plan_keeps_review_and_does_not_run(self):
        calls = self.run_scenario('''if (backend.setupPlan && backend.setupError) {
    if (!backend.needsSetup || backend.setupPlan.steps[1].status !== "blocked")
        console.log("TEST_FAILURE missing blocked review")
    console.log("TEST_PASSED")
    Qt.quit()
}''', markers=('blocked', 'runtime'))
        self.assertFalse(any(args[:2] == ['onboarding', 'run'] for args in calls))

    def test_actions_wait_for_wizard_and_preexisting_writes_flush(self):
        calls = self.run_scenario('''if (phase === 0 && backend.setupPlan && !backend.planLoading) {
    backend.update({color: "#112233"})
    backend.startSetup()
    phase = 1
} else if (phase === 1 && backend.setupRunning) {
    backend.update({brightness: 42})
    backend.commitPending()
    phase = 2
} else if (phase === 2 && backend.setupSucceeded && !backend.busy) {
    console.log("TEST_PASSED")
    Qt.quit()
}''')
        actions = [args for args in calls if args[0] == 'set' or args[:2] == ['onboarding', 'run']]
        self.assertEqual(actions[0][0], 'set')
        self.assertEqual(actions[-1][0], 'set')
        self.assertEqual([args[-1] for args in actions[1:-1]], ['runtime', 'openrgb', 'verify'])

    def test_changed_plan_requires_another_explicit_start(self):
        calls = self.run_scenario('''if (phase === 0 && backend.setupPlan && !backend.planLoading) {
    backend.startSetup()
    phase = 1
} else if (phase === 1 && backend.setupError.indexOf("plan changed") >= 0) {
    if (backend.setupRunning || backend.setupPlan.steps.length !== 4)
        console.log("TEST_FAILURE changed actions not reviewed")
    backend.startSetup()
    phase = 2
} else if (phase === 2 && backend.setupSucceeded) {
    console.log("TEST_PASSED")
    Qt.quit()
}''', markers=('change',))
        self.assertEqual(calls.count(['onboarding', 'plan']), 3)
        self.assertEqual([args[-1] for args in calls if args[:2] == ['onboarding', 'run']],
                         ['runtime', 'openrgb', 'lianli', 'verify'])
