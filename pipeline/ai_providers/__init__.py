"""Provider boundary: HTTP models and file-based online agents share one contract."""
from .transport import AgentFilesProvider, AgentNeeded, CompletionProvider, OpenAICompatibleProvider

__all__ = ["AgentFilesProvider", "AgentNeeded", "CompletionProvider", "OpenAICompatibleProvider"]
