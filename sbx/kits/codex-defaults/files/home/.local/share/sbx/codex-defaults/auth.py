"""Select ChatGPT authentication without disturbing other Codex settings."""

import os
from pathlib import Path
import re
import tomllib


def configure(source):
    current = tomllib.loads(source)
    for key, value in (("forced_login_method", "chatgpt"), ("model_provider", "openai")):
        if current.get(key) == value:
            continue
        expected = dict(current, **{key: value})
        if key not in current:
            source = f'{key} = "{value}"\n' + source
        else:
            lines = source.splitlines(keepends=True)
            for index, line in enumerate(lines):
                if not re.match(r'^\s*' + key + r'\s*=', line):
                    continue
                candidate = ''.join(lines[:index] + [f'{key} = "{value}"\n'] + lines[index + 1:])
                try:
                    parsed = tomllib.loads(candidate)
                except tomllib.TOMLDecodeError:
                    continue
                if parsed == expected:
                    source = candidate
                    break
            else:
                raise ValueError(f'Cannot safely update {key}; edit config.toml manually')
        current = tomllib.loads(source)
        assert current == expected
    return source


home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
path = home / "config.toml"
source = path.read_text() if path.exists() else ""
updated = configure(source)
if updated != source:
    home.mkdir(parents=True, exist_ok=True)
    path.write_text(updated)
