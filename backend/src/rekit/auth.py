"""Local bearer authentication with hashed credentials and explicit actor roles."""

from enum import StrEnum
import hashlib
import hmac
import re
from typing import Annotated, Self

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field, StringConstraints, model_validator

from rekit.catalog.models import CatalogModel, Identifier


class ActorKind(StrEnum):
    HUMAN = "human"
    SERVICE = "service"


class Role(StrEnum):
    VIEWER = "viewer"
    INTAKE = "intake"
    REVIEWER = "reviewer"
    PLANNER = "planner"
    APPROVER = "approver"
    EXECUTOR = "executor"


_HUMAN_ROLES = {Role.REVIEWER, Role.APPROVER, Role.EXECUTOR}
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43,128}")


class Actor(CatalogModel):
    actor_id: Identifier
    kind: ActorKind
    roles: tuple[Role, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def explicit_actor_authority(self) -> Self:
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("Actor roles must be unique")
        if self.kind == ActorKind.SERVICE and _HUMAN_ROLES.intersection(self.roles):
            raise ValueError("Service actors cannot hold reviewer, approver, or executor roles")
        return self


class OperatorCredential(CatalogModel):
    actor: Actor
    token_sha256: Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")] = Field(repr=False)


class AuthConfig(CatalogModel):
    operators: tuple[OperatorCredential, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_credentials(self) -> Self:
        if len({record.actor.actor_id for record in self.operators}) != len(self.operators):
            raise ValueError("Authentication actor IDs must be unique")
        if len({record.token_sha256 for record in self.operators}) != len(self.operators):
            raise ValueError("Authentication token digests must be unique")
        return self


def token_digest(token: str) -> str:
    """Hash a provisioned secrets.token_urlsafe(32) token; never store the raw value."""
    if not isinstance(token, str) or _TOKEN_PATTERN.fullmatch(token) is None:
        raise ValueError("Bearer token must contain 43 to 128 URL-safe characters")
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class AuthDirectory:
    def __init__(self, config: AuthConfig) -> None:
        validated = AuthConfig.model_validate(config.model_dump(mode="json", warnings=False))
        self._records = tuple((record.token_sha256, record.actor) for record in validated.operators)

    def authenticate(self, token: str) -> Actor | None:
        if not isinstance(token, str) or _TOKEN_PATTERN.fullmatch(token) is None:
            return None
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        matched = None
        # Compare every configured digest, including after a match, without exposing credentials.
        for stored_digest, actor in self._records:
            if hmac.compare_digest(digest, stored_digest):
                matched = actor
        return matched


_bearer = HTTPBearer(auto_error=False)


def authenticated_actor(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Actor:
    directory = request.app.state.auth
    if directory is None:
        raise HTTPException(status_code=503, detail="Authentication is not configured.")
    invalid = HTTPException(
        status_code=401, detail="Valid bearer authentication is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if len(request.headers.getlist("authorization")) != 1 or credentials is None:
        raise invalid
    actor = directory.authenticate(credentials.credentials)
    if actor is None:
        raise invalid
    return actor


def require_role(role: Role, *, human: bool = False):
    def authorized_actor(actor: Annotated[Actor, Depends(authenticated_actor)]) -> Actor:
        if role not in actor.roles or (human and actor.kind != ActorKind.HUMAN):
            raise HTTPException(status_code=403, detail="This actor is not authorized for the requested operation.")
        return actor

    return authorized_actor
