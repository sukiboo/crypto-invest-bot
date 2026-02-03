import asyncio
import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class KrakenClient:
    BASE_URL = "https://api.kraken.com"

    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()  # Serialize requests to avoid nonce conflicts

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _generate_signature(self, url_path: str, data: dict, nonce: int) -> str:
        """Generate HMAC-SHA512 signature for Kraken API authentication."""
        post_data = urllib.parse.urlencode(data)
        encoded = (str(nonce) + post_data).encode()
        message = url_path.encode() + hashlib.sha256(encoded).digest()
        secret = base64.b64decode(self.api_secret)
        signature = hmac.new(secret, message, hashlib.sha512)
        return base64.b64encode(signature.digest()).decode()

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        private: bool = True,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        url = f"{self.BASE_URL}{endpoint}"
        headers: dict[str, str] = {}
        request_data = data.copy() if data else {}

        async def do_request() -> dict[str, Any]:
            if private:
                nonce = int(time.time() * 1000)
                request_data["nonce"] = nonce
                headers["API-Key"] = self.api_key
                headers["API-Sign"] = self._generate_signature(endpoint, request_data, nonce)

            session = await self._get_session()
            client_timeout = aiohttp.ClientTimeout(total=timeout)
            async with session.post(
                url, data=request_data, headers=headers, timeout=client_timeout
            ) as response:
                result = await response.json()

                if result.get("error"):
                    error_msg = ", ".join(result["error"])
                    logger.error("Kraken API error: %s", error_msg)
                    raise KrakenAPIError(error_msg)

                return result.get("result", {})

        try:
            if private:
                async with self._lock:
                    return await do_request()
            return await do_request()
        except aiohttp.ClientError as e:
            logger.error("HTTP request failed: %s", e)
            raise KrakenAPIError(f"HTTP request failed: {e}") from e

    async def get_balance(self) -> dict[str, str]:
        return await self._request("POST", "/0/private/Balance")

    async def get_ticker(self, pair: str) -> dict[str, Any]:
        return await self._request("POST", "/0/public/Ticker", data={"pair": pair}, private=False)

    async def get_asset_pairs(self) -> set[str]:
        result = await self._request("POST", "/0/public/AssetPairs", private=False)
        pairs = set(result.keys())
        pairs.update(v.get("altname") for v in result.values() if v.get("altname"))
        return pairs


class KrakenAPIError(Exception):
    pass
