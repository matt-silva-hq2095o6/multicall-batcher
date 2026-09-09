# multicall-batcher

CLI tool and async helper to pack thousands of EVM view calls into Multicall3 `aggregate3` calls.

Most public/free RPCs choke on large multicalls due to gas limits or response body caps (looking at you, Alchemy 10MB limit and Infura compute unit limits). This package adapts chunk size on the fly: cuts batch size in half on 429/timeouts/payload errors, and ramps back up after consecutive successful responses.

## Installation

```bash
pip install multicall-batcher
# or for local dev:
pip install -e .[dev]
```

## CLI Flags

```
multicall-batcher [OPTIONS]

Options:
  --rpc TEXT               RPC HTTP URL [required]
  --input PATH             Input JSON file with calls array [required]
  --output PATH            Output JSON destination path [default: stdout]
  --batch-size INT         Starting chunk size (default: 500)
  --min-batch-size INT     Lower bound when backing off (default: 10)
  --max-batch-size INT     Upper bound (default: 2000)
  --concurrency INT        Max concurrent multicall requests (default: 4)
  --multicall-address HEX  Multicall3 address override
  --allow-failure / --no-allow-failure
                           Multicall3 allowFailure flag (default: true)
  --retries INT            Max retries per failed sub-chunk (default: 5)
  -v, --verbose            Debug logging
```

## Input formats

Input can be a list of call objects with function signatures:

```json
[
  {
    "target": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "signature": "balanceOf(address)(uint256)",
    "args": ["0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"]
  }
]
```

Or raw calldata directly:

```json
[
  {
    "target": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "call_data": "0x70a08231000000000000000000000000d8da6bf26964af9d7eed9e03e53415d37aa96045"
  }
]
```

## Python API

```python
import asyncio
from multicall_batcher import MulticallBatcher, Call

async def main():
    batcher = MulticallBatcher(
        rpc_url="https://arb1.arbitrum.io/rpc",
        initial_batch_size=200,
        max_concurrency=8,
    )

    calls = [
        Call.from_signature(
            target="0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
            signature="decimals()(uint8)",
        )
    ]

    results = await batcher.execute(calls)
    for res in results:
        if res.success:
            print("Decoded:", res.decoded)
        else:
            print("Call failed on chain")

if __name__ == "__main__":
    asyncio.run(main())
```

<!-- refreshed: 2026-09-09 -->
