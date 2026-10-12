"""Credential provisioning is random, hash-only, and refuses destructive replacement."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


SCRIPT = Path(__file__).parents[2] / "scripts" / "create_operator.py"


def test_setup_generates_unique_hash_only_credentials_with_explicit_roles(tmp_path: Path) -> None:
    tokens = []
    for name in ("alice", "bob"):
        config = tmp_path / f"{name}.json"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--config", str(config), "--operator", name, "--roles", "viewer", "intake"],
            capture_output=True, text=True, check=True,
        )
        token = result.stdout.splitlines()[-1]
        assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
        data = json.loads(config.read_text(encoding="utf-8"))
        assert data["operators"] == [{
            "actor": {"actor_id": name, "kind": "human", "roles": ["viewer", "intake"]},
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        }]
        assert token not in config.read_text(encoding="utf-8")
        tokens.append(token)
    assert len(set(tokens)) == 2


def test_setup_preserves_existing_configuration(tmp_path: Path) -> None:
    config = tmp_path / "existing.json"
    config.write_text("preserve existing credentials", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--config", str(config), "--operator", "alice"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert result.stdout == ""
    assert config.read_text(encoding="utf-8") == "preserve existing credentials"
