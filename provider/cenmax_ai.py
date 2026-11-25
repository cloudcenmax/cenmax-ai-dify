from dify_plugin import ModelProvider
from dify_plugin.errors.model import CredentialsValidateFailedError

from cenmax.store import ConnectionStore, catalogue


class CenmaxAIProvider(ModelProvider):
    def validate_provider_credentials(self, credentials: dict) -> None:
        try:
            catalogue(ConnectionStore(credentials.get("connection_id")))
        except Exception:
            raise CredentialsValidateFailedError("Cenmax AI connection could not be verified. Sign in on the plugin host.") from None
