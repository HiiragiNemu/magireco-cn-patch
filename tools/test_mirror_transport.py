"""Exercise real mirror transport, with no network calls or credentials."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request

import mirror_release as t
import mirror_release as m

SECRET_URL = 'https://release-assets.githubusercontent.com/file?sig=DO_NOT_LOG'
ERRORS = []

def error(code):
    exc = urllib.error.HTTPError(SECRET_URL, code, 'DO_NOT_LOG', {}, io.BytesIO(b'DO_NOT_LOG'))
    ERRORS.append(exc)
    return exc

class Transport(unittest.TestCase):
    def tearDown(self):
        for exc in ERRORS: exc.close()
        ERRORS.clear()

    def request(self, method='GET', data=None):
        return urllib.request.Request('https://api.github.com/repos/a/b/x', data=data,
                                      headers={'Authorization': 'Bearer DO_NOT_LOG'}, method=method)

    def test_success_does_not_add_requests_or_delay(self):
        sentinel = object(); opener = Mock(); opener.open.return_value = sentinel
        with patch.object(t.time, 'sleep') as sleep:
            self.assertIs(t.open_request(opener, self.request(), 300, 'metadata'), sentinel)
        self.assertEqual(opener.open.call_count, 1); sleep.assert_not_called()

    def test_transient_read_recovery_all_allowed_codes(self):
        for code in (500, 502, 503, 504):
            with self.subTest(code=code):
                opener=Mock(); sentinel=object(); opener.open.side_effect=[error(code),sentinel]
                with patch.object(t.time,'sleep') as sleep:
                    self.assertIs(t.open_request(opener,self.request(),300,'metadata'),sentinel)
                self.assertEqual(opener.open.call_count,2);sleep.assert_called_once_with(1)

    def test_read_retry_is_bounded(self):
        opener=Mock();opener.open.side_effect=[error(503) for _ in range(3)]
        with patch.object(t.time,'sleep') as sleep:
            with self.assertRaises(urllib.error.HTTPError) as e:
                t.open_request(opener,self.request(),300,'metadata')
        self.assertEqual(opener.open.call_count,3)
        self.assertEqual(e.exception.mirror_transport['attempts'],3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list],[1,2])

    def test_publication_writes_are_never_repeated(self):
        for method in ('POST','PUT','PATCH','DELETE'):
            with self.subTest(method=method):
                opener=Mock();opener.open.side_effect=error(503)
                with patch.object(t.time,'sleep') as sleep:
                    with self.assertRaises(urllib.error.HTTPError):
                        t.open_request(opener,self.request(method,b'{}'),300,'write')
                self.assertEqual(opener.open.call_count,1);sleep.assert_not_called()

    def test_get_with_body_not_repeated(self):
        opener=Mock();opener.open.side_effect=error(503)
        with patch.object(t.time,'sleep') as sleep:
            with self.assertRaises(urllib.error.HTTPError):
                t.open_request(opener,self.request('GET',b'x'),300,'metadata')
        self.assertEqual(opener.open.call_count,1);sleep.assert_not_called()

    def test_permission_rate_limit_and_missing_are_not_retried(self):
        for code in (400,401,403,404,409,422,429):
            with self.subTest(code=code):
                opener=Mock();opener.open.side_effect=error(code)
                with patch.object(t.time,'sleep') as sleep:
                    with self.assertRaises(urllib.error.HTTPError):
                        t.open_request(opener,self.request(),300,'metadata')
                self.assertEqual(opener.open.call_count,1);sleep.assert_not_called()

    def test_unknown_url_failure_has_no_blind_retry(self):
        opener=Mock();opener.open.side_effect=urllib.error.URLError(SECRET_URL)
        with patch.object(t.time,'sleep') as sleep:
            with self.assertRaises(urllib.error.URLError):
                t.open_request(opener,self.request(),300,'metadata')
        self.assertEqual(opener.open.call_count,1);sleep.assert_not_called()

    def test_missing_optional_api_keeps_original_404_semantics(self):
        api=m.API('a/b');api.opener=Mock();api.opener.open.side_effect=error(404)
        self.assertIsNone(api.json('releases/tags/latest',missing=True))
        self.assertEqual(api.opener.open.call_count,1)

    def test_sanitized_status_survives_api_exception_translation(self):
        api=m.API('a/b','DO_NOT_LOG');api.opener=Mock();api.opener.open.side_effect=error(403)
        with self.assertRaises(m.Failure) as e:api.json('contents/public.json?ref=main')
        report=t.failure_report(e.exception)
        self.assertEqual(report['transport']['http_status'],403)
        self.assertEqual(report['transport']['operation'],'contents/public.json')
        self.assertNotIn('DO_NOT_LOG',json.dumps(report));self.assertNotIn('?ref',json.dumps(report))

    def test_report_does_not_serialize_signed_url_or_exception_body(self):
        opener=Mock();opener.open.side_effect=error(403)
        try:t.open_request(opener,self.request(),300,SECRET_URL)
        except urllib.error.HTTPError as e:
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'report.json';t.write_failure_report(e,path)
                raw=path.read_text();data=json.loads(raw)
                self.assertNotIn('DO_NOT_LOG',raw);self.assertNotIn('https://',raw)
                self.assertEqual(data['transport']['operation'],'transport')
                self.assertEqual(data['status'],'failed')

    def test_bad_digest_is_still_rejected(self):
        api=m.API('a/b');api.opener=Mock();api.opener.open.return_value=io.BytesIO(b'wrong')
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(m.Failure):
                api.download({'id':1,'size':5,'digest':'sha256:'+'0'*64,'name':'data.zip'},Path(directory)/'data.zip')
        self.assertEqual(api.opener.open.call_count,1)

    def test_cli_preflight_failure_now_creates_report(self):
        script=Path(m.__file__).resolve()
        with tempfile.TemporaryDirectory() as directory:
            r=subprocess.run([sys.executable,str(script),'--source','a/b','--target','a/b'],
                             cwd=directory,capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            record=json.loads((Path(directory)/'mirror-report.json').read_text())
            self.assertEqual(record['status'],'failed')
            self.assertEqual(record['error_type'],'Failure')
            self.assertIsNone(record['transport'])
            self.assertIn('Source and target must differ',r.stderr)

if __name__=='__main__':unittest.main()
