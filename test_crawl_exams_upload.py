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

    def test_solve_captcha_strips_ocr_whitespace(self):
        fake_ocr = Mock()
        fake_ocr.classification.return_value = " a b c d \n"

        with patch.dict(
            "sys.modules", {"ddddocr": SimpleNamespace(DdddOcr=Mock(return_value=fake_ocr))}
        ):
            self.assertEqual("abcd", crawl_exams.solve_captcha(b"image-bytes"))

    def test_solve_captcha_returns_empty_when_ocr_dependency_missing(self):
        with patch.dict("sys.modules", {"ddddocr": None}):
            self.assertEqual("", crawl_exams.solve_captcha(b"image-bytes"))

    def test_fetch_captcha_returns_response_bytes(self):
        session = Mock()
        session.get.return_value = SimpleNamespace(status_code=200, content=b"captcha")

        self.assertEqual(b"captcha", crawl_exams.fetch_captcha(session))
        session.get.assert_called_once_with(crawl_exams.CAPTCHA_URL, timeout=30)

    def test_fetch_captcha_rejects_empty_body(self):
        session = Mock()
        session.get.return_value = SimpleNamespace(status_code=200, content=b"")

        self.assertEqual(b"", crawl_exams.fetch_captcha(session))

    def test_fetch_login_sess_parses_scode_and_sxh(self):
        session = Mock()
        session.post.return_value = SimpleNamespace(text="scode-value#12345")

        self.assertEqual(("scode-value", "12345"), crawl_exams.fetch_login_sess(session))
        session.post.assert_called_once_with(
            crawl_exams.LOGIN_SESS_URL,
            data={},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )

    def test_fetch_login_sess_rejects_invalid_responses(self):
        for body in ["", "no", "missing-separator"]:
            session = Mock()
            session.post.return_value = SimpleNamespace(text=body)

            self.assertEqual(("", ""), crawl_exams.fetch_login_sess(session))

    def test_submit_login_posts_encoded_credentials(self):
        session = Mock()
        session.post.return_value = SimpleNamespace(text="正在登录")

        result = crawl_exams.submit_login(session, "u", "p", "abcd", "scode", "11111")

        self.assertEqual(crawl_exams.LOGIN_SUCCESS, result)
        called_url = session.post.call_args.args[0]
        called_kwargs = session.post.call_args.kwargs
        self.assertEqual(crawl_exams.LOGIN_URL, called_url)
        self.assertEqual("", called_kwargs["data"]["userAccount"])
        self.assertEqual("", called_kwargs["data"]["userPassword"])
        self.assertEqual("abcd", called_kwargs["data"]["RANDOMCODE"])
        self.assertEqual(
            crawl_exams.encode_credentials("u", "p", "scode", "11111"),
            called_kwargs["data"]["encoded"],
        )

    def test_submit_login_classifies_password_and_captcha_errors(self):
        session = Mock()
        session.post.return_value = SimpleNamespace(text="用户名或密码错误")
        self.assertEqual(
            crawl_exams.LOGIN_BAD_CREDENTIALS,
            crawl_exams.submit_login(session, "u", "p", "abcd", "scode", "1"),
        )

        session.post.return_value = SimpleNamespace(text="验证码错误")
        self.assertEqual(
            crawl_exams.LOGIN_BAD_CAPTCHA,
            crawl_exams.submit_login(session, "u", "p", "abcd", "scode", "1"),
        )

    def test_verify_login_rejects_redirects_and_accepts_main_page_marker(self):
        session = Mock()
        session.get.return_value = SimpleNamespace(status_code=302, text="")
        self.assertFalse(crawl_exams.verify_login(session))

        session.get.return_value = SimpleNamespace(status_code=200, text="教学一体化服务平台")
        self.assertTrue(crawl_exams.verify_login(session))
        session.get.assert_called_with(
            crawl_exams.MAIN_PAGE_URL, timeout=30, allow_redirects=False
        )

    def test_verify_login_rejects_unmarked_200_response(self):
        session = Mock()
        session.get.return_value = SimpleNamespace(status_code=200, text="login page")

        self.assertFalse(crawl_exams.verify_login(session))

    def test_login_retries_after_bad_captcha_and_then_succeeds(self):
        session = Mock()
        session.get.return_value = SimpleNamespace(status_code=200)

        with (
            patch("crawl_exams.fetch_captcha", side_effect=[b"img1", b"img2"]),
            patch("crawl_exams.solve_captcha", side_effect=["1111", "2222"]),
            patch("crawl_exams.fetch_login_sess", return_value=("scode", "11111")),
            patch(
                "crawl_exams.submit_login",
                side_effect=[crawl_exams.LOGIN_BAD_CAPTCHA, crawl_exams.LOGIN_SUCCESS],
            ) as submit_login,
            patch("crawl_exams.verify_login", return_value=True),
            redirect_stdout(io.StringIO()),
        ):
            self.assertTrue(crawl_exams.login(session, "user", "pass"))

        self.assertEqual(2, submit_login.call_count)

    def test_login_stops_immediately_on_bad_credentials(self):
        session = Mock()
        session.get.return_value = SimpleNamespace(status_code=200)

        with (
            patch("crawl_exams.fetch_captcha", return_value=b"img"),
            patch("crawl_exams.solve_captcha", return_value="1111"),
            patch("crawl_exams.fetch_login_sess", return_value=("scode", "11111")),
            patch(
                "crawl_exams.submit_login", return_value=crawl_exams.LOGIN_BAD_CREDENTIALS
            ) as submit_login,
            patch("crawl_exams.verify_login") as verify_login,
            redirect_stdout(io.StringIO()),
        ):
            self.assertFalse(crawl_exams.login(session, "user", "bad-pass"))

        self.assertEqual(1, submit_login.call_count)
        verify_login.assert_not_called()

    def test_login_fails_when_verification_never_passes(self):
        session = Mock()
        session.get.return_value = SimpleNamespace(status_code=200)

        with (
            patch("crawl_exams.fetch_captcha", return_value=b"img"),
            patch("crawl_exams.solve_captcha", return_value="1111"),
            patch("crawl_exams.fetch_login_sess", return_value=("scode", "11111")),
            patch("crawl_exams.submit_login", return_value=crawl_exams.LOGIN_SUCCESS),
            patch("crawl_exams.verify_login", return_value=False) as verify_login,
            redirect_stdout(io.StringIO()),
        ):
            self.assertFalse(crawl_exams.login(session, "user", "pass"))

        self.assertEqual(2, verify_login.call_count)


if __name__ == "__main__":
    unittest.main()
