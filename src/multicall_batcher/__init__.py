"""Batch thousands of EVM read calls into Multicall3 chunks."""

from multicall_batcher.batcher import MulticallBatcher
from multicall_batcher.client import MulticallClient, RpcError
from multicall_batcher.parser import Call

__version__ = "0.2.1"

__all__ = [
    "MulticallBatcher",
    "MulticallClient",
    "RpcError",
    "Call",
    "__version__",
]
