"""
AI Agent SOC - Identity Issuance Broker
Issues and verifies JWT tokens for agent authentication.
"""
from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger(__name__)

ISSUER = "ai-agent-soc-identity-broker"
AUDIENCE = "ai-agent-soc-api"
ALGORITHM = "RS256"


class TokenRevocationError(Exception):
    """Raised when attempting to verify a revoked token."""


class AgentIdentityBroker:
    """Issues, verifies, and revokes JWT tokens for SOC agents."""

    def __init__(self, private_key_pem: bytes, public_key_pem: bytes) -> None:
        self._private_key = serialization.load_pem_private_key(
            private_key_pem, password=None, backend=default_backend()
        )
        self._public_key = serialization.load_pem_public_key(
            public_key_pem, backend=default_backend()
        )
        # In production, this would be backed by Redis or a database.
        self._revocation_store: set[str] = set()

    # ------------------------------------------------------------------
    # Token issuance
    # ------------------------------------------------------------------

    def issue_token(
        self,
        agent_id: str,
        tenant_id: str,
        scopes: list[str],
        tier: str = "T1",
        ttl_seconds: int = 3600,
    ) -> str:
        """Issue a signed JWT for the given agent."""
        now = datetime.datetime.utcnow()
        jti = str(uuid.uuid4())
        payload: dict[str, Any] = {
            "sub": agent_id,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "tenant_id": tenant_id,
            "scopes": scopes,
            "tier": tier,
            "iat": now,
            "exp": now + datetime.timedelta(seconds=ttl_seconds),
            "jti": jti,
        }
        token = jwt.encode(payload, self._private_key, algorithm=ALGORITHM)
        logger.info(
            "Issued token jti=%s agent_id=%s tenant_id=%s tier=%s ttl=%d",
            jti,
            agent_id,
            tenant_id,
            tier,
            ttl_seconds,
        )
        return token

    # ------------------------------------------------------------------
    # Token verification
    # ------------------------------------------------------------------

    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify and decode a JWT; raises if revoked, expired, or invalid."""
        try:
            claims = jwt.decode(
                token,
                self._public_key,
                algorithms=[ALGORITHM],
                audience=AUDIENCE,
                options={"require": ["exp", "iat", "jti", "sub", "iss", "aud"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise jwt.ExpiredSignatureError("Token has expired.") from exc
        except jwt.InvalidTokenError as exc:
            raise jwt.InvalidTokenError(f"Token validation failed: {exc}") from exc

        jti = claims.get("jti")
        if jti and jti in self._revocation_store:
            raise TokenRevocationError(f"Token {jti} has been revoked.")

        return claims

    # ------------------------------------------------------------------
    # Token revocation
    # ------------------------------------------------------------------

    def revoke_token(self, jti: str, reason: str = "unspecified") -> None:
        """Add a JTI to the revocation list."""
        self._revocation_store.add(jti)
        logger.warning("Revoked token jti=%s reason=%s", jti, reason)

    def is_revoked(self, jti: str) -> bool:
        """Return True if the given JTI has been revoked."""
        return jti in self._revocation_store

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_rsa_key_pair(key_size: int = 4096) -> tuple[bytes, bytes]:
        """Generate a new RSA key pair and return (private_pem, public_pem)."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend(),
        )
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return private_pem, public_pem
