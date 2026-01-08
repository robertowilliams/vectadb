"""VectaDB exceptions."""

from typing import Any, Optional


class VectaDBError(Exception):
    """Base exception for all VectaDB errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Any] = None) -> None:
        """Initialize VectaDB error.

        Args:
            message: Error message
            status_code: HTTP status code if applicable
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details

    def __str__(self) -> str:
        """String representation of the error."""
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class ConnectionError(VectaDBError):
    """Raised when unable to connect to VectaDB server."""

    pass


class AuthenticationError(VectaDBError):
    """Raised when authentication fails."""

    pass


class ValidationError(VectaDBError):
    """Raised when data validation fails."""

    pass


class NotFoundError(VectaDBError):
    """Raised when a resource is not found."""

    pass


class ServerError(VectaDBError):
    """Raised when the server returns a 5xx error."""

    pass


class RateLimitError(VectaDBError):
    """Raised when rate limit is exceeded."""

    pass
