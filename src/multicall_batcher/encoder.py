from dataclasses import dataclass
from eth_abi import decode, encode
from eth_utils import function_signature_to_4byte_selector, to_bytes, to_checksum_address

MULTICALL3_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11"

# aggregate3((address,bool,bytes)[]) -> (bool,bytes)[]
AGGREGATE3_SELECTOR = bytes.fromhex("82ad56cb")

# Standard Solidity error selectors
ERROR_STRING_SELECTOR = bytes.fromhex("08c379a0")  # Error(string)
PANIC_SELECTOR = bytes.fromhex("4e487b71")         # Panic(uint256)


@dataclass
class Call3:
    target: str
    allow_failure: bool
    calldata: bytes


@dataclass
class CallResult:
    success: bool
    return_data: bytes
    revert_reason: str | None = None


def selector_from_sig(signature: str) -> bytes:
    clean = "".join(signature.split())
    return function_signature_to_4byte_selector(clean)


def decode_revert_reason(data: bytes) -> str | None:
    if len(data) < 4:
        return None

    # print(f"DEBUG: raw revert bytes: {data.hex()}")
    selector = data[:4]
    payload = data[4:]

    if selector == ERROR_STRING_SELECTOR:
        try:
            reason = decode(["string"], payload)[0]
            return str(reason)
        except Exception:
            return f"Reverted with unparseable Error(string): {payload.hex()}"

    if selector == PANIC_SELECTOR:
        try:
            code = decode(["uint256"], payload)[0]
            return f"Panic(0x{code:02x})"
        except Exception:
            return f"Panic({payload.hex()})"

    # TODO: add custom error ABI decoding registry from CLI args
    return f"CustomError(0x{selector.hex()})"


def encode_aggregate3(calls: list[Call3]) -> bytes:
    """Packs call tuples into Multicall3 aggregate3 calldata with 4-byte selector."""
    tuples = [
        (to_checksum_address(c.target), c.allow_failure, c.calldata)
        for c in calls
    ]
    encoded_args = encode(["(address,bool,bytes)[]"], [tuples])
    return AGGREGATE3_SELECTOR + encoded_args


def decode_aggregate3_result(raw_hex_or_bytes: str | bytes) -> list[CallResult]:
    if isinstance(raw_hex_or_bytes, str):
        raw = to_bytes(hexstr=raw_hex_or_bytes)
    else:
        raw = raw_hex_or_bytes

    if len(raw) == 0:
        return []

    decoded = decode(["(bool,bytes)[]"], raw)[0]
    results = []
    for item in decoded:
        success = item[0]
        return_data = item[1]
        reason = None if success else decode_revert_reason(return_data)
        results.append(CallResult(success=success, return_data=return_data, revert_reason=reason))
    return results
