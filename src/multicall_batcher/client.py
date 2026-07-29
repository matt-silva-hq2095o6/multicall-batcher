import random
import time
import httpx


class RpcError(Exception):
    def __init__(self, message: str, code: int | None = None, raw_data: dict | None = None):
        super().__init__(message)
        self.code = code
        self.raw_data = raw_data


class RateLimitError(RpcError):
    pass


class ChunkTooLargeError(RpcError):
    """Raised when the node rejects a call because output/gas exceeds provider limit."""
    pass


class RpcClient:
    """HTTP JSON-RPC client with jittered backoff on rate limits."""

    def __init__(
        self,
        rpc_url: str,
        timeout: float = 30.0,
        max_retries: int = 6,
        base_delay: float = 0.5,
        max_delay: float = 20.0,
    ):
        self.rpc_url = rpc_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._client = httpx.Client(timeout=self.timeout)
        self._req_id = 0

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _check_chunk_limits(self, msg: str, code: int | None) -> bool:
        lower = msg.lower()
        # Alchemy, Infura, Ankr, Quicknode error strings for big multicall chunks
        patterns = [
            "response size exceeded",
            "response size limit",
            "call gas limit exceeded",
            "gas limit exceeded",
            "out of gas",
            "execution timeout",
            "exceeds 10000000 gas limit",
            "exceeds 30000000 gas limit",
            "max response size",
            "block range is too wide",
        ]
        return any(p in lower for p in patterns)

    def call(self, method: str, params: list) -> dict | str | int | list:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params,
        }

        last_err: Exception | None = None
        delay = self.base_delay

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                sleep_time = min(delay * (2 ** (attempt - 1)), self.max_delay)
                # 20% jitter prevents synchronized thunder
                sleep_time += random.uniform(0, 0.2 * sleep_time)
                time.sleep(sleep_time)

            try:
                resp = self._client.post(self.rpc_url, json=payload)
            except httpx.RequestError as exc:
                last_err = exc
                continue

            # Cloudflare / gateway timeouts on heavy payloads
            if resp.status_code in (504, 524):
                last_err = ChunkTooLargeError(f"Gateway timeout ({resp.status_code})")
                # don't keep retrying the exact same massive payload without splitting
                raise last_err

            if resp.status_code == 429:
                last_err = RateLimitError("HTTP 429 Too Many Requests")
                continue

            if resp.status_code >= 500:
                last_err = RpcError(f"Server returned status {resp.status_code}")
                continue

            try:
                data = resp.json()
            except ValueError:
                last_err = RpcError(f"Invalid JSON response from node: {resp.text[:200]}")
                continue

            if "error" in data:
                err_info = data["error"]
                code = err_info.get("code")
                msg = err_info.get("message", "Unknown RPC error")

                if self._check_chunk_limits(msg, code):
                    raise ChunkTooLargeError(msg, code=code, raw_data=err_info)

                # node rate limit codes
                if code in (-32005, -32029) or "rate limit" in msg.lower() or "too many requests" in msg.lower():
                    last_err = RateLimitError(msg, code=code, raw_data=err_info)
                    continue

                raise RpcError(msg, code=code, raw_data=err_info)

            if "result" not in data:
                raise RpcError(f"Missing result in response: {data}")

            return data["result"]

        raise last_err or RpcError("Max retries exceeded")
