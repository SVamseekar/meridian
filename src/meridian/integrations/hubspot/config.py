import os

DEFAULT_HUBSPOT_SCOPES = [
    "crm.objects.contacts.read",
    "companies.read",
    "companies.write",
    "deals.read",
]


def get_hubspot_client_id() -> str:
    return os.environ.get("HUBSPOT_CLIENT_ID", "mock-client-id")


def get_hubspot_client_secret() -> str:
    return os.environ.get("HUBSPOT_CLIENT_SECRET", "mock-client-secret")


def get_hubspot_redirect_uri() -> str:
    return os.environ.get(
        "HUBSPOT_REDIRECT_URI",
        "http://localhost:8000/api/v1/oauth/hubspot/callback",
    )


def get_frontend_base_url() -> str:
    return os.environ.get("FRONTEND_BASE_URL", "http://localhost:3001")
