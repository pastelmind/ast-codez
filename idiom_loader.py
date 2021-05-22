import json
import re
import typing


class IdiomDatabase(typing.NamedTuple):
    floats: typing.FrozenSet[float]
    ints: typing.FrozenSet[int]
    strings: typing.FrozenSet[str]
    identifiers: typing.FrozenSet[str]


def load_idioms() -> IdiomDatabase:
    with open("idioms.json", encoding="utf8") as json_file:
        raw_db = json.load(json_file)

    WHITESPACE_PATTERN = re.compile(r"\s")

    return IdiomDatabase(
        floats=frozenset(entry["value"] for entry in raw_db["float"]),
        ints=frozenset(int(entry["value"]) for entry in raw_db["int"]),
        # Strings may contain whitespace, which may prevent seq2seq from
        # treating it as a single token.
        # Such string literals must be normalized even if they are common
        # idioms.
        strings=frozenset(
            value
            for value in (entry["value"] for entry in raw_db["str"])
            if not WHITESPACE_PATTERN.search(value)
        ),
        identifiers=frozenset(entry["value"] for entry in raw_db["identifiers"]),
    )
