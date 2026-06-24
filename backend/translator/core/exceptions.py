"""Translator engine exceptions."""


class TranslatorError(Exception):
    """Base exception for the translation engine."""


class ModelNotFoundError(TranslatorError):
    """Required model is missing or unreachable."""


class ModelDownloadError(TranslatorError):
    """Automatic model download or install failed."""


class UnsupportedFormatError(TranslatorError):
    """Input file format is not supported."""


class FileProcessingError(TranslatorError):
    """Failed to read or parse input file."""


class GPUUnavailableError(TranslatorError):
    """GPU was requested but is not available."""


class TranslationFailedError(TranslatorError):
    """Translation request failed."""


class DependencyMissingError(TranslatorError):
    """Required external dependency is missing."""
