from app.providers.base import JobProvider
from app.providers.greenhouse.provider import GreenhouseProvider

_PROVIDERS: dict[str, JobProvider] = {
    "greenhouse": GreenhouseProvider(),
}


def get_provider(name: str) -> JobProvider:
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise ValueError(f"Unknown provider: {name}") from None


def all_providers() -> list[JobProvider]:
    return list(_PROVIDERS.values())
