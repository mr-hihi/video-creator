class ProviderNotFoundError(Exception):
    def __init__(self, provider_id: str):
        super().__init__(f"Provider {provider_id} not found")


class InvalidProviderSettingError(Exception):
    pass


class SecretKeyMissingError(Exception):
    def __init__(self):
        super().__init__("Set SETTINGS_SECRET_KEY in api/.env before saving API keys")


class ExtensionNotConnectedError(Exception):
    def __init__(self):
        super().__init__("The Google Flow extension is not connected")


class ProviderNotSetUpError(Exception):
    def __init__(self, provider_name: str):
        super().__init__(f"{provider_name} is not set up — open Settings")
