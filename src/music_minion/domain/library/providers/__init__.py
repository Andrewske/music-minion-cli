"""
Music library provider registry.

Provides access to all available provider modules.
"""

from typing import Any, List

# Provider registry will be populated as providers are implemented
# Each provider module exports functions matching the LibraryProvider protocol

PROVIDERS: dict[str, Any] = {}


def register_provider(name: str, provider_module: Any) -> None:
    """Register a provider module.

    Args:
        name: Provider name (e.g., 'local', 'soundcloud')
        provider_module: Module implementing LibraryProvider protocol
    """
    PROVIDERS[name] = provider_module


def get_provider(name: str) -> Any:
    """Get provider module by name.

    Args:
        name: Provider name

    Returns:
        Provider module

    Raises:
        ValueError: If provider not found
    """
    if name not in PROVIDERS:
        available = list_providers()
        raise ValueError(
            f"Unknown provider: '{name}'. "
            f"Available providers: {', '.join(available) if available else 'none'}"
        )
    return PROVIDERS[name]


def list_providers() -> List[str]:
    """Get list of all registered provider names.

    Returns:
        List of provider names
    """
    return list(PROVIDERS.keys())


def provider_exists(name: str) -> bool:
    """Check if a provider is registered.

    Args:
        name: Provider name

    Returns:
        True if provider exists
    """
    return name in PROVIDERS


# Import and register providers as they are implemented
from . import local, soundcloud, spotify

register_provider("local", local)
register_provider("soundcloud", soundcloud)
register_provider("spotify", spotify)
