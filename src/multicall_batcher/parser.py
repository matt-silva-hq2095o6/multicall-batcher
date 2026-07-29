import re
from typing import NamedTuple, List


class ParsedSignature(NamedTuple):
    name: str
    inputs: List[str]
    outputs: List[str]
    canonical: str


def _split_params(s: str) -> List[str]:
    # Split top-level commas without breaking nested tuples like ((address,uint256),bool)
    parts = []
    depth = 0
    current = []
    for char in s:
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                parts.append(item)
            current = []
        else:
            current.append(char)
    last = "".join(current).strip()
    if last:
        parts.append(last)
    return parts


def _clean_type(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    
    # Tuple handling: (address, uint256) or (address, uint256)[]
    if raw.startswith("("):
        idx = raw.rfind(")")
        if idx == -1:
            raise ValueError(f"Mismatched parens in tuple type: {raw}")
        inner = raw[1:idx]
        suffix = raw[idx + 1:].strip()
        # recursive clean on components
        sub_types = [_clean_type(p) for p in _split_params(inner)]
        return f"({','.join(sub_types)}){suffix}"

    parts = raw.split()
    t = parts[0]
    # uint/int aliases
    if t == "uint":
        return "uint256"
    if t == "int":
        return "int256"
    if t == "byte":
        return "bytes1"
    return t


_FUNC_RE = re.compile(r"^(?:function\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*)\)\s*(?:.*returns\s*\((.*)\))?$", re.DOTALL)


def parse_signature(sig: str) -> ParsedSignature:
    """Parse human-readable Solidity signatures into canonical types and selector string."""
    sig = sig.strip()
    match = _FUNC_RE.match(sig)
    if not match:
        raise ValueError(f"Invalid function signature format: {sig}")

    name, raw_inputs, raw_outputs = match.groups()
    
    inputs = []
    if raw_inputs and raw_inputs.strip():
        for item in _split_params(raw_inputs):
            c = _clean_type(item)
            if c:
                inputs.append(c)

    outputs = []
    if raw_outputs and raw_outputs.strip():
        for item in _split_params(raw_outputs):
            c = _clean_type(item)
            if c:
                outputs.append(c)

    canonical = f"{name}({','.join(inputs)})"
    return ParsedSignature(name=name, inputs=inputs, outputs=outputs, canonical=canonical)
