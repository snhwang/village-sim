"""What the villagers call each person who talks with them.

A visitor to the live village is signed in through Cloudflare Access, which
tells the server who it is in the ``Cf-Access-Authenticated-User-Email``
header. The first time a visitor talks with a villager, the page asks what
the villagers should call it, and the name is kept against that account, so it
follows the visitor to any device and villagers can know them again. Without
that header (the server reached directly, as on localhost) the page sends a
random token it keeps in the browser instead.

An account is kept only as a salted hash, never as an email or a token, in
``accounts.json`` beside the runs (``runs/`` is not published). The salt is
made once, when the file is.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
from pathlib import Path

EMAIL_HEADER = "cf-access-authenticated-user-email"
TOKEN_HEADER = "x-visitor"
# A name a villager can say: letters, with spaces, hyphens or apostrophes
# between them, up to 24 characters.
NAME = re.compile(r"^[^\W\d_]+(?:[ '\-][^\W\d_]+)*$")
MAX_NAME = 24


class Accounts:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.salt: str = data.get("salt") or secrets.token_hex(16)
        self.names: dict[str, str] = dict(data.get("names") or {})

    def key(self, headers) -> str | None:
        """Who is asking, as a salted hash: the Cloudflare account, or else the
        browser's own token. None for neither."""
        email = (headers.get(EMAIL_HEADER) or "").strip().lower()
        if email:
            return "cf:" + self._hash(email)
        token = (headers.get(TOKEN_HEADER) or "").strip()
        if 16 <= len(token) <= 128:
            return "browser:" + self._hash(token)
        return None

    def _hash(self, value: str) -> str:
        return hashlib.sha256(f"{self.salt}:{value}".encode()).hexdigest()

    def name_of(self, key: str | None) -> str | None:
        return self.names.get(key) if key else None

    def refusal(self, name: str, taken: set[str]) -> str | None:
        """Why a name will not do, or None. ``taken`` holds the villagers'
        names, so nobody is mistaken for one of them."""
        if not name:
            return "a name is needed"
        if len(name) > MAX_NAME:
            return f"a name of at most {MAX_NAME} letters, please"
        if not NAME.match(name):
            return "letters only, with spaces, hyphens or apostrophes between them"
        if name.lower() in {t.lower() for t in taken}:
            return f"{name} is already a villager's name"
        return None

    def set(self, key: str, name: str) -> None:
        with self._lock:
            self.names[key] = name
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"salt": self.salt, "names": self.names}, indent=1),
                           encoding="utf-8")
            tmp.replace(self.path)
