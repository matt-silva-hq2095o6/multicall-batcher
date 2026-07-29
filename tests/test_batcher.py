import pytest
from unittest.mock import MagicMock, patch
from multicall_batcher.batcher import MulticallBatcher, BatchConfig
from multicall_batcher.encoder import Call, MulticallResult
from multicall_batcher.client import RpcError, RateLimitError


def make_dummy_calls(n: int):
    return [
        Call(
            target="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            allow_failure=True,
            call_data=f"0x70a08231{i:064x}",
        )
        for i in range(n)
    ]


def test_batcher_runs_in_chunks():
    calls = make_dummy_calls(50)
    client = MagicMock()

    client.call_aggregate3.side_effect = lambda chunk: [
        MulticallResult(success=True, return_data="0x01") for _ in chunk
    ]

    config = BatchConfig(initial_chunk_size=20, min_chunk_size=5)
    batcher = MulticallBatcher(client=client, config=config)

    results = batcher.execute(calls)
    assert len(results) == 50
    # 50 calls in chunks of 20 -> 20, 20, 10 -> 3 calls
    assert client.call_aggregate3.call_count == 3


def test_batcher_splits_on_oversized_request():
    calls = make_dummy_calls(20)
    client = MagicMock()

    def side_effect(chunk):
        if len(chunk) > 10:
            raise RpcError(code=-32000, message="response size exceeded")
        return [MulticallResult(success=True, return_data="0xaa") for _ in chunk]

    client.call_aggregate3.side_effect = side_effect

    config = BatchConfig(initial_chunk_size=20, min_chunk_size=2)
    batcher = MulticallBatcher(client=client, config=config)

    results = batcher.execute(calls)
    assert len(results) == 20
    # First attempt (20) fails -> splits into two batches of 10 -> both succeed
    assert client.call_aggregate3.call_count == 3


@patch("time.sleep", return_value=None)
def test_batcher_retries_on_rate_limit(mock_sleep):
    calls = make_dummy_calls(5)
    client = MagicMock()

    # Fail once with 429, then succeed
    attempts = {"count": 0}

    def side_effect(chunk):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RateLimitError("429 Too Many Requests")
        return [MulticallResult(success=True, return_data="0xbb") for _ in chunk]

    client.call_aggregate3.side_effect = side_effect

    config = BatchConfig(initial_chunk_size=10, max_retries=3, backoff_base=0.01)
    batcher = MulticallBatcher(client=client, config=config)

    results = batcher.execute(calls)
    assert len(results) == 5
    assert client.call_aggregate3.call_count == 2
    assert mock_sleep.called


def test_batcher_raises_when_min_chunk_fails():
    calls = make_dummy_calls(4)
    client = MagicMock()
    client.call_aggregate3.side_effect = RpcError(code=-32603, message="out of gas")

    config = BatchConfig(initial_chunk_size=4, min_chunk_size=2)
    batcher = MulticallBatcher(client=client, config=config)

    with pytest.raises(RpcError):
        batcher.execute(calls)
