"""Private host-managed OAuth connections for self-hosted Dify."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import time

from . import oauth


class ConnectionStore:
    def __init__(self, reference, root=None):
        if not isinstance(reference, str) or not re.fullmatch(r"[a-f0-9]{64}", reference):
            raise oauth.OAuthError("invalid_connection")
        directory = root or os.environ.get("CENMAX_DIFY_CREDENTIAL_DIR") or Path.home() / ".config" / "cenmax-dify"
        if not os.path.isabs(directory):
            raise oauth.OAuthError("unsafe_store")
        self.root = Path(os.path.abspath(directory))
        self.key = hashlib.sha256(reference.encode()).hexdigest()
        self.file = self.root / (self.key + ".json")

    def prepare(self):
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for directory in [self.root, *self.root.parents]:
            info = directory.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise oauth.OAuthError("unsafe_store")
        info = self.root.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise oauth.OAuthError("unsafe_store")

    @staticmethod
    def secure_file(descriptor):
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 32768:
            raise oauth.OAuthError("unsafe_store")

    @contextmanager
    def locked(self):
        self.prepare()
        fd = os.open(self.root / (self.key + ".lock"), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            self.secure_file(fd)
            deadline = time.monotonic() + 15
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise oauth.OAuthError("connection_busy") from None
                    time.sleep(0.05)
            yield
        finally:
            os.close(fd)

    def read(self):
        try:
            descriptor = os.open(self.file, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor) as file:
                self.secure_file(file.fileno())
                value = json.load(file)
            oauth.secret(value.get("access_token"))
            oauth.secret(value.get("refresh_token"))
            oauth.number(value.get("expires_at_ms"), maximum=10**15)
            return value
        except Exception:
            raise oauth.OAuthError("sign_in_required") from None

    def write(self, value):
        temp = self.root / ("." + self.key + "." + secrets.token_hex(16) + ".tmp")
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w") as file:
                json.dump(value, file)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, self.file)
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temp.unlink(missing_ok=True)

    def login(self, output=print):
        # Browser approval happens before taking the short credential-store lock.
        value = oauth.login(output=output)
        with self.locked():
            self.write(value)

    def access_token(self):
        with self.locked():
            value = self.read()
            if value["expires_at_ms"] <= time.time() * 1000 + 60000:
                # Retire this generation durably before dispatch. A process crash
                # must never leave the single-use grant available for replay.
                self.write({"refresh_in_flight": True})
                try:
                    value = oauth.refresh(value["refresh_token"])
                    self.write(value)
                except Exception:
                    # Any post-dispatch error may have consumed the old grant.
                    self.file.unlink(missing_ok=True)
                    raise oauth.OAuthError("sign_in_required") from None
            return value["access_token"]

    def logout(self):
        with self.locked():
            value = self.read()
            oauth.revoke(value["refresh_token"], hint="refresh_token")
            oauth.revoke(value["access_token"], hint="access_token")
            self.file.unlink()


def catalogue(store):
    payload = oauth.request("/app/v1/models", access_token=store.access_token())
    if not isinstance(payload.get("data"), list):
        raise oauth.OAuthError("invalid_response")
    result = []
    for item in payload["data"]:
        if not isinstance(item, dict) or item.get("owned_by") != "Cenmax AI" or not isinstance(item.get("id"), str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", item["id"]):
            raise oauth.OAuthError("invalid_response")
        name = item.get("display_name", "")
        if not isinstance(name, str) or not name.endswith("by Cenmax AI") or len(name) > 128 or any(ord(char) < 32 or ord(char) == 127 for char in name):
            raise oauth.OAuthError("invalid_response")
        context = item.get("context_window")
        output = item.get("max_output_tokens")
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in [context, output]):
            raise oauth.OAuthError("invalid_response")
        caps = item.get("capabilities")
        result.append({"id": item["id"], "name": name, "context": context, "output": output,
            "tools": isinstance(caps, dict) and caps.get("tools") is True,
            "vision": isinstance(caps, dict) and caps.get("vision") is True})
    return result
