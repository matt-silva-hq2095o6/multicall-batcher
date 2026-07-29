import pytest
from multicall_batcher.encoder import (
    encode_multicall3_aggregate3,
    decode_multicall3_response,
    encode_function_call,
    decode_function_result,
    Call,
)


def test_encode_function_call_erc20_balance_of():
    # balanceOf(address) -> 0x70a08231
    target = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    holder = "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
    
    calldata = encode_function_call(
        signature="balanceOf(address)",
        args=[holder]
    )
    assert calldata.startswith("0x70a08231")
    assert holder.lower().replace("0x", "") in calldata.lower()


def test_encode_multicall3_aggregate3_structure():
    calls = [
        Call(
            target="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            allow_failure=True,
            call_data="0x70a08231000000000000000000000000d8da6bf26964af9d7eed9e03e53415d37aa96045",
        ),
        Call(
            target="0x6B175474E89094C44Da98b954EedeAC495271d0F",
            allow_failure=False,
            call_data="0x18160ddd",  # totalSupply()
        ),
    ]

    encoded = encode_multicall3_aggregate3(calls)
    # aggregate3 selector is 0x82ad56cb
    assert encoded.startswith("0x82ad56cb")
    assert len(encoded) > 10


def test_decode_multicall3_response_success_and_failure():
    # Raw abi-encoded Result[](bool success, bytes returnData)
    # Simulating 2 results: 1 ok with uint256(1000), 1 failed with empty bytes
    raw_hex = (
        "0x0000000000000000000000000000000000000000000000000000000000000020"
        "0000000000000000000000000000000000000000000000000000000000000002"
        "0000000000000000000000000000000000000000000000000000000000000001"
        "0000000000000000000000000000000000000000000000000000000000000040"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000080"
        "0000000000000000000000000000000000000000000000000000000000000020"
        "00000000000000000000000000000000000000000000000000000000000003e8"
        "0000000000000000000000000000000000000000000000000000000000000000"
    )

    results = decode_multicall3_response(raw_hex)
    assert len(results) == 2
    assert results[0].success is True
    assert results[0].return_data.endswith("03e8")
    assert results[1].success is False
    assert results[1].return_data in ("", "0x")


def test_decode_multicall3_response_empty_string():
    assert decode_multicall3_response("") == []
    assert decode_multicall3_response("0x") == []


def test_decode_function_result():
    raw_ret = "0x000000000000000000000000000000000000000000000000000000000000002a"
    decoded = decode_function_result("uint256", raw_ret)
    assert decoded == 42
