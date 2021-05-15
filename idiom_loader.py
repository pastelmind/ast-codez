import json
import typing


class IdiomDatabase(typing.NamedTuple):
    floats: typing.FrozenSet[float]
    ints: typing.FrozenSet[int]
    strings: typing.FrozenSet[str]
    identifiers: typing.FrozenSet[str]


def load_idioms() -> IdiomDatabase:
    with open("idioms.json", encoding="utf8") as json_file:
        raw_db = json.load(json_file)
    return IdiomDatabase(
        floats=frozenset(entry["value"] for entry in raw_db["float"]),
        ints=frozenset(int(entry["value"]) for entry in raw_db["int"]),
        strings=frozenset(entry["value"] for entry in raw_db["str"]),
        identifiers=frozenset(entry["value"] for entry in raw_db["identifiers"]),
    )
