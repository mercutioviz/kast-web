"""
app/cloud/zap_api_client — HTTP client for a provisioned ZAP instance.

Ported from kast/kast/scripts/zap_api_client.py with logger swap only.
Used by CloudProvider.provision() to confirm ZAP is healthy before
returning the endpoint to the orchestrator.

Note: this client is only for pre-scan health checks and bootstrap
confirmation. The kast CLI drives the actual scan via its own ZAP
automation plan once kast-web hands it the remote URL + API key.
"""

from flask import current_app


class ZapApiClient:
    """Thin client for confirming a provisioned ZAP instance is healthy.

    Args:
        url: ZAP base URL, e.g. 'http://1.2.3.4:8080'.
        api_key: ZAP API key.
        timeout: Default request timeout in seconds.
    """

    def __init__(self, url: str, api_key: str, timeout: int = 10):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout

    def health_check(self) -> bool:
        """Return True if ZAP's /JSON/core/view/version/ endpoint responds.

        Returns:
            True if ZAP is running and the API key is accepted.
            False if ZAP is not reachable or the key is rejected.
        """
        raise NotImplementedError("Will be implemented in D2 (zap_api_client port)")

    def wait_until_ready(self, timeout: int = 300, interval: int = 5) -> None:
        """Poll health_check() until ZAP is ready or timeout expires.

        Args:
            timeout: Maximum wait time in seconds.
            interval: Seconds between health check attempts.

        Raises:
            TimeoutError: if ZAP does not become ready within timeout.
        """
        raise NotImplementedError("Will be implemented in D2 (zap_api_client port)")
