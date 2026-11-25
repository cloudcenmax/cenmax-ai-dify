import concurrent.futures
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from cenmax import oauth
from cenmax.store import ConnectionStore, catalogue
from cenmax.transport import events


REFERENCE = "a" * 64


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        os.chmod(self.root, 0o700)
        self.store = ConnectionStore(REFERENCE, self.root)

    def tearDown(self):
        self.temp.cleanup()

    def initial(self, expires=1):
        with self.store.locked():
            self.store.write({"access_token": "access-test", "refresh_token": "refresh-test", "expires_at_ms": expires})

    def test_reference_format_and_file_names(self):
        for value in ["pro", "../secret", "a" * 63, None]:
            with self.assertRaises(oauth.OAuthError):
                ConnectionStore(value, self.root)
        self.assertNotEqual(self.store.file.stem, REFERENCE)

    def test_revocation_accepts_successful_array_and_empty_bodies_with_bounds(self):
        class Response(io.BytesIO):
            def __init__(self, raw, status):
                super().__init__(raw)
                self.status = status
        for raw, status in [(b"[]", 200), (b"", 204), (b"not-json", 200)]:
            with patch.object(oauth.urllib.request, "build_opener") as opener:
                opener.return_value.open.return_value = Response(raw, status)
                self.assertEqual(oauth.request("/oauth/revoke", fields={"client_id": oauth.CLIENT_ID, "token": "access-test"}), {})
        with patch.object(oauth.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = Response(b"x" * (oauth.MAX_BODY + 1), 200)
            with self.assertRaises(oauth.OAuthError):
                oauth.revoke("access-test")

    def test_logout_removes_session_for_public_revoke_array_response(self):
        class Response(io.BytesIO):
            status = 200
        self.initial(time.time() * 1000 + 3600000)
        with patch.object(oauth.urllib.request, "build_opener") as opener:
            opener.return_value.open.side_effect = [Response(b"[]"), Response(b"[]")]
            self.store.logout()
        self.assertFalse(self.store.file.exists())

    def test_private_files_and_symlinks(self):
        self.initial(time.time() * 1000 + 3600000)
        self.assertEqual(self.store.file.stat().st_mode & 0o777, 0o600)
        os.chmod(self.store.file, 0o644)
        with self.assertRaises(oauth.OAuthError):
            self.store.access_token()
        self.store.file.unlink()
        target = self.root / "target"
        target.write_text("{}")
        self.store.file.symlink_to(target)
        with self.assertRaises(oauth.OAuthError):
            self.store.read()

    def test_concurrent_refresh_rotates_once(self):
        self.initial()
        calls = []
        def refresh(value):
            calls.append(value)
            time.sleep(0.05)
            return {"access_token": "new-access-test", "refresh_token": "new-refresh-test", "expires_at_ms": time.time() * 1000 + 3600000}
        with patch.object(oauth, "refresh", side_effect=refresh):
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                results = list(pool.map(lambda _: ConnectionStore(REFERENCE, self.root).access_token(), range(2)))
        self.assertEqual(results, ["new-access-test"] * 2)
        self.assertEqual(calls, ["refresh-test"])

    def test_uncertain_refresh_is_not_replayed(self):
        self.initial()
        with patch.object(oauth, "refresh", side_effect=oauth.OAuthError()) as refresh:
            for _ in range(2):
                with self.assertRaises(oauth.OAuthError):
                    self.store.access_token()
        self.assertEqual(refresh.call_count, 1)

    def test_process_interruption_after_dispatch_leaves_durable_reconnect_marker(self):
        self.initial()
        def interrupted(_token):
            self.assertEqual(json.loads(self.store.file.read_text()), {"refresh_in_flight": True})
            raise KeyboardInterrupt()
        with patch.object(oauth, "refresh", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.store.access_token()
        with patch.object(oauth, "refresh") as refresh:
            with self.assertRaises(oauth.OAuthError):
                self.store.access_token()
            refresh.assert_not_called()

    def test_catalogue_checks_owner_identity_and_entitlements(self):
        self.initial(time.time() * 1000 + 3600000)
        row = {"id": "pro", "display_name": "Pro by Cenmax AI", "owned_by": "Cenmax AI", "context_window": 128000, "max_output_tokens": 8192, "capabilities": {"tools": True}}
        with patch.object(oauth, "request", return_value={"data": [row]}):
            self.assertEqual(catalogue(self.store)[0]["id"], "pro")
        with patch.object(oauth, "request", return_value={"data": [{**row, "owned_by": "Other"}]}):
            with self.assertRaises(oauth.OAuthError):
                catalogue(self.store)

    def test_stream_requires_completion_and_redacts_errors(self):
        payload = b'data: {"model":"pro","choices":[]}\n\ndata: [DONE]\n\n'
        self.assertEqual(list(events(io.BytesIO(payload)))[0]["model"], "pro")
        with self.assertRaises(oauth.OAuthError) as error:
            list(events(io.BytesIO(b'data: {"error":"private-test"}\n\n')))
        self.assertNotIn("private-test", str(error.exception))
        with self.assertRaises(oauth.OAuthError):
            list(events(io.BytesIO(b'data: {"choices":[]}\n\n')))


if __name__ == "__main__":
    unittest.main()
