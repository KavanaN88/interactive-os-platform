class ValidationError(ValueError):
    """Invalid simulation input (maps to HTTP 422 in the API layer). Shared by all engines."""
