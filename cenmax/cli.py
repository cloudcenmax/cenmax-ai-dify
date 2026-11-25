"""Device sign-in helper; run as the plugin daemon's operating-system user."""
import argparse
import secrets
import sys

from .store import ConnectionStore, catalogue
from .oauth import OAuthError


def main():
    parser = argparse.ArgumentParser(prog="python -m cenmax.cli")
    parser.add_argument("action", choices=["login", "models", "logout"])
    parser.add_argument("connection", nargs="?")
    args = parser.parse_args()
    if (args.action == "login") == bool(args.connection):
        parser.error("login creates a connection; models and logout require one")
    reference = secrets.token_hex(32) if args.action == "login" else args.connection
    store = ConnectionStore(reference)
    try:
        if args.action == "login":
            store.login(output=lambda text: print(text, file=sys.stderr))
            print("Connected. Keep this reference private and enter it in Dify's Cenmax AI credential.", file=sys.stderr)
            print(reference)
        elif args.action == "models":
            for model in catalogue(store):
                print(model["id"] + "\t" + model["name"])
        else:
            store.logout()
            print("Cenmax AI disconnected.")
    except Exception:
        print("Cenmax AI operation failed. Check the connection or sign in again.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
