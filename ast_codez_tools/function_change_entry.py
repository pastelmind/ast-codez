import typing

from ast_codez_tools.code_normalizer import ReplacementMap


class FunctionChangeEntry(typing.TypedDict):
    name: str
    before_code: str
    after_code: str
    before_code_normalized: str
    after_code_normalized: str
    edit_actions: list[str]
    replacement_map: ReplacementMap
