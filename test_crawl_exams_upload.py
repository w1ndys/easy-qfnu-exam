import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

import crawl_exams


class CrawlUploadSafetyTest(unittest.TestCase):
    def test_upload_payload_handles_request_errors_without_secret(self):
        out = io.StringIO()
        with patch(
            "crawl_exams.requests.post", side_effect=requests.RequestException("boom")
        ):
            with redirect_stdout(out):
                ok = crawl_exams.upload_payload(
                    "https://example.test/upload", "secret-token", {}
                )

        self.assertFalse(ok)
        self.assertIn("[!] 上传失败: boom", out.getvalue())
        self.assertNotIn("secret-token", out.getvalue())

    def test_upload_payload_truncates_response_body(self):
        resp = Mock(status_code=500, text="x" * 600)
        out = io.StringIO()
        with patch("crawl_exams.requests.post", return_value=resp):
            with redirect_stdout(out):
                ok = crawl_exams.upload_payload(
                    "https://example.test/upload", "secret-token", {}
                )

        self.assertFalse(ok)
        self.assertIn("[!] 上传失败: HTTP 500", out.getvalue())
        self.assertIn("x" * 500, out.getvalue())
        self.assertNotIn("x" * 501, out.getvalue())

    def test_crawl_skips_json_and_upload_when_detail_tasks_fail(self):
        with tempfile.TemporaryDirectory() as tempdir:
            output_path = os.path.join(tempdir, "exams.csv")
            json_path = os.path.join(tempdir, "payload.json")
            classroom = SimpleNamespace(
                cells=[SimpleNamespace(has_exam=True)],
            )
            args = SimpleNamespace(
                cookie="cookie",
                semester="2025-2026-2",
                start_week="19",
                end_week="20",
                start_xq="1",
                end_xq="7",
                jszt="4",
                output=output_path,
                format="csv",
                workers=1,
                rate=1000,
                verbose=False,
                json_output=json_path,
                upload=True,
                upload_url="https://example.test/upload",
            )
            session = Mock()
            session.post.return_value.text = "grid"

            with (
                patch("crawl_exams.make_session", return_value=session),
                patch("crawl_exams.get_kbjcmsid", return_value="kbjcmsid"),
                patch("crawl_exams.parse_grid_html", return_value=([classroom], {})),
                patch(
                    "crawl_exams.process_task", side_effect=Exception("detail failed")
                ),
                patch("crawl_exams.upload_payload") as upload_payload,
                redirect_stdout(io.StringIO()),
            ):
                status = crawl_exams.crawl(args)

            self.assertEqual(1, status)
            self.assertFalse(os.path.exists(json_path))
            upload_payload.assert_not_called()

    def test_main_returns_1_without_cookie_or_cookie_env(self):
        out = io.StringIO()
        with (
            patch("sys.argv", ["crawl_exams.py"]),
            patch.dict(os.environ, {}, clear=True),
            patch("crawl_exams.crawl") as crawl,
            redirect_stdout(out),
        ):
            status = crawl_exams.main()

        self.assertEqual(1, status)
        self.assertIn("[!] 缺少Cookie，请使用 -c 或设置 QFNU_JW_COOKIE", out.getvalue())
        crawl.assert_not_called()

    def test_main_reads_cookie_from_default_env(self):
        with (
            patch("sys.argv", ["crawl_exams.py"]),
            patch.dict(os.environ, {"QFNU_JW_COOKIE": "JSESSIONID=env"}, clear=True),
            patch("crawl_exams.crawl", return_value=0) as crawl,
            redirect_stdout(io.StringIO()),
        ):
            status = crawl_exams.main()

        self.assertEqual(0, status)
        self.assertEqual("JSESSIONID=env", crawl.call_args.args[0].cookie)


if __name__ == "__main__":
    unittest.main()
