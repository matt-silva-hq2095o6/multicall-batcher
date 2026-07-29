import asyncio
import logging
from typing import List, Tuple
from multicall_batcher.encoder import Call, CallResult
from multicall_batcher.client import MulticallClient, RpcError

log = logging.getLogger("multicall_batcher")


class BatchExecutor:
    """Splits contract calls into dynamic chunks and scales down on RPC errors."""

    def __init__(
        self,
        client: MulticallClient,
        initial_chunk_size: int = 500,
        min_chunk_size: int = 5,
        max_chunk_size: int = 1500,
        concurrency: int = 4,
        require_success: bool = False,
        block_number: int | None = None,
    ):
        self.client = client
        self.current_chunk_size = initial_chunk_size
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.semaphore = asyncio.Semaphore(concurrency)
        self.require_success = require_success
        self.block_number = block_number
        self._success_streak = 0
        self._lock = asyncio.Lock()

    async def _adjust_chunk_size(self, success: bool):
        async with self._lock:
            if success:
                self._success_streak += 1
                # slowly ramp back up after 5 consecutive successful chunk calls
                if self._success_streak >= 5 and self.current_chunk_size < self.max_chunk_size:
                    old = self.current_chunk_size
                    self.current_chunk_size = min(self.max_chunk_size, int(self.current_chunk_size * 1.25))
                    self._success_streak = 0
                    log.debug("increasing chunk size %d -> %d", old, self.current_chunk_size)
            else:
                self._success_streak = 0
                old = self.current_chunk_size
                self.current_chunk_size = max(self.min_chunk_size, self.current_chunk_size // 2)
                log.warning("rpc limit encountered, dropping chunk size %d -> %d", old, self.current_chunk_size)

    async def _execute_subchunk(self, calls: List[Call], max_retries: int = 4) -> List[CallResult]:
        if not calls:
            return []

        attempt = 0
        sub = calls
        while attempt < max_retries:
            try:
                async with self.semaphore:
                    # print(f"executing chunk len={len(sub)}")
                    res = await self.client.aggregate(
                        sub,
                        require_success=self.require_success,
                        block_number=self.block_number,
                    )
                    await self._adjust_chunk_size(success=True)
                    return res
            except RpcError as err:
                attempt += 1
                await self._adjust_chunk_size(success=False)

                # if it's too big or node returned 429/timeout, bisect the slice recursively
                if len(sub) > self.min_chunk_size:
                    mid = len(sub) // 2
                    left, right = sub[:mid], sub[mid:]
                    res_left = await self._execute_subchunk(left, max_retries=max_retries)
                    res_right = await self._execute_subchunk(right, max_retries=max_retries)
                    return res_left + res_right

                if attempt >= max_retries:
                    raise err

                # FIXME: Alchemy throws string payload limits, Infura returns code -32005
                await asyncio.sleep(0.3 * (2 ** attempt))

        return []

    async def run(self, calls: List[Call]) -> List[CallResult]:
        if not calls:
            return []

        indexed_calls: List[Tuple[int, Call]] = list(enumerate(calls))
        results_indexed: List[Tuple[int, CallResult]] = []

        i = 0
        tasks = []
        while i < len(indexed_calls):
            chunk = indexed_calls[i : i + self.current_chunk_size]
            i += len(chunk)

            raw_calls = [c for _, c in chunk]
            indices = [idx for idx, _ in chunk]

            async def _worker(idxs: List[int], batch: List[Call]):
                res = await self._execute_subchunk(batch)
                return list(zip(idxs, res))

            tasks.append(_worker(indices, raw_calls))

        chunk_batches = await asyncio.gather(*tasks)
        for batch in chunk_batches:
            results_indexed.extend(batch)

        # preserve original user call ordering
        results_indexed.sort(key=lambda x: x[0])
        return [r for _, r in results_indexed]
