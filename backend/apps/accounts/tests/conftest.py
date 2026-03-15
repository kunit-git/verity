import pytest
from apps.accounts.models import SiteSettings


@pytest.fixture(autouse=True)
def site_settings(db):
    """Ensure SiteSettings singleton exists for every test."""
    return SiteSettings.get()
