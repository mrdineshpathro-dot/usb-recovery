"""Typed exceptions. Callers should catch specific classes, not bare Exception."""

from __future__ import annotations


class RecoveryError(Exception):
    """Base error for USB Recovery Lab."""


class SafetyError(RecoveryError):
    """Raised when an operation would violate a mandatory data-safety rule."""


class ConfirmationRequired(SafetyError):
    """Physical device access or another sensitive step needs an explicit token."""


class SourceAccessError(RecoveryError):
    """The source device or image cannot be opened read-only."""


class DestinationError(RecoveryError):
    """The recovery destination is missing, full, or unsafe."""


class ParseError(RecoveryError):
    """Malformed filesystem or partition metadata was skipped defensively."""


class CancelledError(RecoveryError):
    """The user or caller cancelled a long-running operation."""


class UnsupportedFilesystemError(RecoveryError):
    """A volume signature was recognized but reconstruction is not implemented."""


class ConfigurationError(RecoveryError):
    """Invalid configuration file or option combination."""


class StopThresholdError(CancelledError):
    """Acquisition paused because a configured error/risk threshold was reached."""


class IdentityMismatchError(SafetyError):
    """The reconnected device does not match the checkpoint identity."""


class PluginVerificationError(SafetyError):
    """A plugin failed signature or allow-list verification."""


class VaultError(RecoveryError):
    """Local recovery vault encryption or unlock failed."""
