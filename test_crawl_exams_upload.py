import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

import crawl_exams


class CrawlUploadSafetyTest(unittest.TestCase):
    def test_encode_credentials_inserts_scode_by_sxh_for_first_20_chars(self):
        encoded = crawl_exams.encode_credentials(
            "user",
            "pass",
            "abcdefghijklmnopqrstuvwxyz",
            "12345678901234567890",
        )

        self.assertEqual(
            "uasbcedefrghij%klmno%pqrstu%vwxyzpass",
            encoded,
        )

    def test_encode_credentials_appends_text_after_20_chars_unchanged(self):
        encoded = crawl_exams.encode_credentials(
            "abcdefghijklmnopqrstu",
            "pw",
            "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz",
            "11111111111111111111",
        )

        self.assertTrue(encoded.endswith("u%%%pw"))

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

    def test_crawl_writes_and_uploads_empty_payload_when_no_exam_tasks(self):
        with tempfile.TemporaryDirectory() as tempdir:
            output_path = os.path.join(tempdir, "exams.csv")
            json_path = os.path.join(tempdir, "payload.json")
            classroom = SimpleNamespace(
                cells=[SimpleNamespace(has_exam=False)],
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
                patch.dict(os.environ, {"VERCEL_UPLOAD_SECRET": "secret"}),
                patch(
                    "crawl_exams.upload_payload", return_value=True
                ) as upload_payload,
                redirect_stdout(io.StringIO()),
            ):
                status = crawl_exams.crawl(args)

            self.assertEqual(0, status)
            with open(json_path, encoding="utf-8") as f:
                payload = json.load(f)

            self.assertEqual("2025-2026-2", payload["semester"])
            self.assertEqual([], payload["records"])
            upload_payload.assert_called_once()
            self.assertEqual([], upload_payload.call_args.args[2]["records"])

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
        self.assertIn(
            "[!] 缺少Cookie，请设置 QFNU_JW_COOKIE，或手动使用 -c 传入", out.getvalue()
        )
        crawl.assert_not_called()

    def test_help_recommends_cookie_env_examples(self):
        out = io.StringIO()
        with (
            patch("sys.argv", ["crawl_exams.py", "--help"]),
            self.assertRaises(SystemExit) as cm,
            redirect_stdout(out),
        ):
            crawl_exams.main()

        help_text = out.getvalue()
        self.assertEqual(0, cm.exception.code)
        self.assertIn('export QFNU_JW_COOKIE="JSESSIONID=xxx"', help_text)
        self.assertIn("python crawl_exams.py --json-output exams.json", help_text)
        self.assertIn(
            "python crawl_exams.py -s 2025-2026-2 --start-week 19 --end-week 20",
            help_text,
        )
        self.assertIn(
            "python crawl_exams.py --upload --json-output exams.json", help_text
        )
        self.assertIn(
            "登录后的Cookie字符串 (不推荐命令行传入，优先使用环境变量)",
            help_text,
        )
        self.assertNotIn('-c "xxx"', help_text)

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
