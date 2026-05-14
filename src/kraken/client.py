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

REQUEST_TIMEOUT = 30.0


class KrakenClient:
    BASE_URL = "https://api.kraken.com"

    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()  # Serialize requests to avoid nonce conflicts
        self._asset_pairs: dict[str, dict[str, Any]] | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _generate_signature(self, url_path: str, data: dict, nonce: int) -> str:
        post_data = urllib.parse.urlencode(data)
        encoded = (str(nonce) + post_data).encode()
        message = url_path.encode() + hashlib.sha256(encoded).digest()
        secret = base64.b64decode(self.api_secret)
        signature = hmac.new(secret, message, hashlib.sha512)
        return base64.b64encode(signature.digest()).decode()

    async def _request(
        self,
        endpoint: str,
        data: dict | None = None,
        private: bool = True,
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
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            async with session.post(url, data=request_data, headers=headers, timeout=timeout) as r:
                result = await r.json()
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
        return await self._request("/0/private/Balance")

    async def get_asset_balance(self, asset: str, balance: dict[str, str] | None = None) -> float:
        if balance is None:
            balance = await self.get_balance()
        for variant in (asset, f"X{asset}", f"Z{asset}"):
            if variant in balance:
                return float(balance[variant])
        return 0.0

    async def get_ledger_entries(self, ledger_type: str | None = None) -> dict[str, Any]:
        data = {"type": ledger_type} if ledger_type is not None else {}
        result = await self._request("/0/private/Ledgers", data=data)
        return result.get("ledger", {})

    async def _get_asset_pairs_metadata(self) -> dict[str, dict[str, Any]]:
        if self._asset_pairs is None:
            self._asset_pairs = await self._request("/0/public/AssetPairs", private=False)
        return self._asset_pairs  # type: ignore[return-value]

    async def get_asset_pairs(self) -> set[str]:
        metadata = await self._get_asset_pairs_metadata()
        pairs = set(metadata.keys())
        pairs.update(v["altname"] for v in metadata.values() if isinstance(v.get("altname"), str))
        return pairs

    async def get_pair_symbols(self, pair: str) -> tuple[str, str]:
        # Returns (base, quote) display symbols parsed from AssetPairs `wsname`
        # (e.g. 'ETH', 'USD'). Accepts either the canonical pair key or its altname.
        metadata = await self._get_asset_pairs_metadata()
        entry = metadata.get(pair) or next(
            (v for v in metadata.values() if v.get("altname") == pair), None
        )
        if entry is None:
            raise ValueError(f"Unknown trading pair: {pair}")
        wsname = entry.get("wsname")
        if not isinstance(wsname, str) or "/" not in wsname:
            raise ValueError(f"Pair '{pair}' missing or malformed 'wsname': {wsname!r}")
        base, quote = wsname.split("/", 1)
        return base, quote


class KrakenAPIError(Exception):
    pass
