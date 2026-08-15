class VendorResponseError(RuntimeError):
    """Raised by vendor adapters (STT/LLM/prosody/etc.) for a technical,
    English, non-user-facing failure — an unexpected API response shape,
    a raw error payload, and similar. Distinct from a plain RuntimeError
    so analysis_service.py can tell the two apart: its own RuntimeErrors
    are curated Japanese copy safe to show as-is, but str(this) is not."""
