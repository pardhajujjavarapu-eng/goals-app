"""
Schwab OAuth client. Run this file directly to authenticate:
    python backend/auth/schwab_auth.py
Then use get_client() in all other modules.
"""
import os
from pathlib import Path
import schwab
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_ENV_PATH)

APP_KEY = os.getenv("SCHWAB_APP_KEY", "")
APP_SECRET = os.getenv("SCHWAB_APP_SECRET", "")
CALLBACK_URL = "https://127.0.0.1:8182"
TOKEN_PATH = Path(__file__).parent.parent.parent / "data" / "token.json"

_client = None


def get_client():
    global _client
    if _client is not None:
        return _client

    if not APP_KEY or not APP_SECRET:
        raise ValueError(
            "SCHWAB_APP_KEY and SCHWAB_APP_SECRET must be set in .env\n"
            "Copy .env.example to .env and fill in your credentials."
        )

    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"No token found at {TOKEN_PATH}\n"
            "Run:  python backend/auth/schwab_auth.py\n"
            "Then visit the URL printed in your terminal to complete authentication."
        )

    try:
        _client = schwab.auth.client_from_token_file(
            token_path=str(TOKEN_PATH),
            api_key=APP_KEY,
            app_secret=APP_SECRET,
        )
        return _client
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load Schwab token: {exc}\n"
            "Token may be expired — run:  python backend/auth/schwab_auth.py"
        ) from exc


if __name__ == "__main__":
    load_dotenv(_ENV_PATH)
    if not APP_KEY or not APP_SECRET:
        print("ERROR: Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET in your .env file.")
        raise SystemExit(1)

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    print("Starting Schwab OAuth flow.")
    print("A browser window will open (or copy-paste the URL printed below).\n")

    client = schwab.auth.easy_client(
        api_key=APP_KEY,
        app_secret=APP_SECRET,
        callback_url=CALLBACK_URL,
        token_path=str(TOKEN_PATH),
    )
    print(f"\nAuthentication successful.  Token saved to: {TOKEN_PATH}")
    print("You can now start the server with:  bash run.sh")
