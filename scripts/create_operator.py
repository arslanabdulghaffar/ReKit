"""Create one local operator credential without overwriting existing configuration."""

import argparse
from pathlib import Path
import secrets

from rekit.auth import Actor, ActorKind, AuthConfig, OperatorCredential, Role, token_digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(".secrets/operators.json"))
    parser.add_argument("--operator", required=True, help="Named human operator recorded in audits")
    parser.add_argument("--roles", nargs="+", choices=[role.value for role in Role], default=[role.value for role in Role])
    args = parser.parse_args()
    token = secrets.token_urlsafe(32)
    config = AuthConfig(operators=(OperatorCredential(
        actor=Actor(actor_id=args.operator, kind=ActorKind.HUMAN, roles=tuple(Role(role) for role in args.roles)),
        token_sha256=token_digest(token),
    ),))
    args.config.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves existing credentials and role assignments.
    with args.config.open("x", encoding="utf-8") as destination:
        destination.write(config.model_dump_json(indent=2) + "\n")
    print(f"Created {args.config}. Store this token privately; it is not saved in the config:")
    print(token)


if __name__ == "__main__":
    main()
