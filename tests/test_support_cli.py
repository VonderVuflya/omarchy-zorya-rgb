import contextlib
import io
import json
import unittest
from unittest.mock import patch
from zorya_rgb import cli


class SupportCliTests(unittest.TestCase):
    def test_update_check_and_apply_are_distinct_explicit_actions(self):
        with patch('zorya_rgb.updates.check',return_value={'ok':True}) as check, patch('zorya_rgb.updates.apply',return_value={'ok':True}) as apply:
            cli.execute(cli.parser().parse_args(['updates','check','--force']))
            check.assert_called_once_with(force=True); apply.assert_not_called()
            cli.execute(cli.parser().parse_args(['updates','apply','--tag','v0.3.0']))
            apply.assert_called_once_with('v0.3.0')

    def test_report_uses_structured_error_args_and_copy_does_not_publish(self):
        with patch('zorya_rgb.support.build_report',return_value={'ok':True}) as report, patch('zorya_rgb.support.copy_report',return_value={'ok':True}) as copy:
            cli.execute(cli.parser().parse_args(['support','report','--error=--failure value','--operation=hardware']))
            report.assert_called_once_with(error='--failure value',operation='hardware'); copy.assert_not_called()
            cli.execute(cli.parser().parse_args(['support','copy']))
            copy.assert_called_once_with()

    def test_submit_requires_explicit_preview_fingerprint(self):
        with patch('zorya_rgb.support.submit_report',return_value={'ok':True}) as submit:
            cli.execute(cli.parser().parse_args(['support','submit','--fingerprint','reviewed']))
            submit.assert_called_once_with('reviewed')

    def test_missing_update_target_is_rejected_as_json(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):code=cli.main(['updates','apply'])
        self.assertEqual(code,1); self.assertFalse(json.loads(output.getvalue())['ok'])
