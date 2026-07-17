from dataclasses import dataclass

from app.providers.registry import all_providers


@dataclass
class DetectedSource:
    provider: str
    source_identifier: str
    source_url: str


def detect_source(url: str) -> DetectedSource | None:
    """Mode D discovery (spec §11): the user pastes a source URL directly.

    Tries each registered provider's detect()/extract_source_identifier() in turn.
    """
    for provider in all_providers():
        if not provider.detect(url):
            continue
        identifier = provider.extract_source_identifier(url)
        if identifier is None:
            continue
        return DetectedSource(provider=provider.name, source_identifier=identifier, source_url=url)
    return None
