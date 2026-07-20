from app.providers.ashby.provider import AshbyProvider
from app.providers.base import JobProvider
from app.providers.breezyhr.provider import BreezyHRProvider
from app.providers.greenhouse.provider import GreenhouseProvider
from app.providers.lever.provider import LeverProvider
from app.providers.smartrecruiters.provider import SmartRecruitersProvider

_PROVIDERS: dict[str, JobProvider] = {
    "greenhouse": GreenhouseProvider(),
    "ashby": AshbyProvider(),
    "lever": LeverProvider(),
    "smartrecruiters": SmartRecruitersProvider(),
    "breezyhr": BreezyHRProvider(),
}


def get_provider(name: str) -> JobProvider:
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise ValueError(f"Unknown provider: {name}") from None


def all_providers() -> list[JobProvider]:
    return list(_PROVIDERS.values())
