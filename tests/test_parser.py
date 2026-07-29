import pytest
from multicall_batcher.parser import parse_signature


def test_parse_simple_signature():
    sig = parse_signature("balanceOf(address)(uint256)")
    assert sig.name == "balanceOf"
    assert sig.inputs == ["address"]
    assert sig.outputs == ["uint256"]
    assert sig.canonical_name == "balanceOf(address)"


def test_parse_no_args():
    sig = parse_signature("totalSupply()(uint256)")
    assert sig.name == "totalSupply"
    assert sig.inputs == []
    assert sig.outputs == ["uint256"]


def test_parse_multiple_inputs_and_outputs():
    sig = parse_signature("swap(uint256,address,bool)(uint256,uint256)")
    assert sig.name == "swap"
    assert sig.inputs == ["uint256", "address", "bool"]
    assert sig.outputs == ["uint256", "uint256"]


def test_parse_tuple_syntax():
    sig = parse_signature("getReserves()((uint112,uint112,uint32))")
    assert sig.name == "getReserves"
    assert sig.inputs == []
    assert sig.outputs == ["(uint112,uint112,uint32)"]


def test_parse_nested_tuples_and_arrays():
    sig = parse_signature("exactInputSingle((address,address,uint24,address,uint256,uint256,uint160))(uint256)")
    assert sig.name == "exactInputSingle"
    assert sig.inputs == ["(address,address,uint24,address,uint256,uint256,uint160)"]
    assert sig.outputs == ["uint256"]

    sig2 = parse_signature("batchGet(address[],(uint256,bytes)[])((bool,bytes)[])")
    assert sig2.name == "batchGet"
    assert sig2.inputs == ["address[]", "(uint256,bytes)[]"]
    assert sig2.outputs == ["(bool,bytes)[]"]


def test_parse_whitespace_tolerance():
    sig = parse_signature("  transferFrom ( address , address , uint256 ) ( bool ) ")
    assert sig.name == "transferFrom"
    assert sig.inputs == ["address", "address", "uint256"]
    assert sig.outputs == ["bool"]
    assert sig.canonical_name == "transferFrom(address,address,uint256)"


def test_parse_no_return_type():
    sig = parse_signature("ping()")
    assert sig.name == "ping"
    assert sig.inputs == []
    assert sig.outputs == []


def test_invalid_signature_raises():
    with pytest.raises(ValueError):
        parse_signature("invalid_format_without_parens")

    with pytest.raises(ValueError):
        parse_signature("balanceOf(address")

    with pytest.raises(ValueError):
        parse_signature("foo((uint256,address)")
