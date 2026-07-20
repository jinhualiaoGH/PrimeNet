class PaperBuilderError(Exception):
    """Base exception for all Paper Builder failures."""


class ConfigurationError(PaperBuilderError):
    """Raised when configuration is invalid."""


class ManifestError(PaperBuilderError):
    """Raised when a paper manifest is missing or invalid."""


class PluginNotFoundError(PaperBuilderError):
    """Raised when a requested paper plugin cannot be found."""


class PipelineError(PaperBuilderError):
    """Raised when a build pipeline stage fails."""
