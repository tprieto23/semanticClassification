import anthropic

from src.config import settings

_client: anthropic.Anthropic | None = None


def get_anthropic_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        default_headers = {}
        if settings.ANTHROPIC_WORKSPACE_ID:
            default_headers["anthropic-workspace-id"] = settings.ANTHROPIC_WORKSPACE_ID
        _client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            default_headers=default_headers,
        )
    return _client
