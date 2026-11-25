"""Fixed-origin model transport; no proxy or redirect can receive credentials."""
import json
import time
import urllib.error
import urllib.request

from . import oauth

MAX_OUTPUT = 32 * 1024 * 1024
MAX_EVENT = 2 * 1024 * 1024


def invoke(store, payload, stream=False):
    raw = json.dumps(payload, allow_nan=False).encode()
    if len(raw) > 8 * 1024 * 1024:
        raise oauth.OAuthError("request_too_large")
    request = urllib.request.Request(oauth.BASE_URL + "/chat/completions", data=raw,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + oauth.secret(store.access_token())})
    try:
        response = urllib.request.build_opener(urllib.request.ProxyHandler({}), oauth.NoRedirect()).open(request, timeout=120)
        expected = "text/event-stream" if stream else "application/json"
        if response.status != 200 or response.headers.get_content_type() != expected:
            response.close()
            raise oauth.OAuthError()
        return response
    except urllib.error.HTTPError as error:
        error.close()
        raise oauth.OAuthError() from None
    except Exception:
        raise oauth.OAuthError() from None


def response_json(response):
    try:
        with response:
            raw = response.read(MAX_OUTPUT + 1)
            if len(raw) > MAX_OUTPUT:
                raise oauth.OAuthError()
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise oauth.OAuthError()
            return result
    except Exception:
        raise oauth.OAuthError() from None


def events(response):
    size = 0
    pending = []
    pending_size = 0
    deadline = time.monotonic() + 600
    try:
        with response:
            while True:
                line = response.readline(MAX_EVENT + 1)
                if not line:
                    break
                size += len(line)
                pending_size += len(line)
                if size > MAX_OUTPUT or pending_size > MAX_EVENT or time.monotonic() >= deadline:
                    raise oauth.OAuthError()
                if line.strip():
                    if line.startswith(b"data:"):
                        pending.append(line[5:].strip())
                    continue
                data = b"\n".join(pending)
                pending = []
                pending_size = 0
                if not data:
                    continue
                if data == b"[DONE]":
                    return
                event = json.loads(data)
                if not isinstance(event, dict) or event.get("error"):
                    raise oauth.OAuthError()
                yield event
        raise oauth.OAuthError("incomplete_response")
    except Exception:
        raise oauth.OAuthError() from None
