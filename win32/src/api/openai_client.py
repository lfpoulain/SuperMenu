"""Windows adapter for the shared provider client."""

import requests  # noqa: F401 - compatibility with existing test patches.

from supermenu_core.api.openai_client import OpenAIClient as _SharedOpenAIClient


class OpenAIClient(_SharedOpenAIClient):
    """Shared client with multimodal payloads enabled for screen capture."""

    def __init__(
        self,
        settings,
        api_key=None,
        model=None,
        max_retries=3,
        retry_delay=1.0,
        *,
        endpoint_api_key=None,
    ):
        super().__init__(
            settings,
            api_key=api_key,
            model=model,
            max_retries=max_retries,
            retry_delay=retry_delay,
            allow_images=True,
            endpoint_api_key=endpoint_api_key,
        )
