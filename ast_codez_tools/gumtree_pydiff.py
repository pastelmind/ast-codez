"""Uses GumTree to compare two versions of Python code."""

import json
import pathlib
import typing

import jpype
import jpype.imports

from .gumtree_pythonparser import python_code_to_gumtree_xml

######## GumTree initialization code

_GUMTREE_JAR_PATH = pathlib.Path(__file__, "../../gumtree/gumtree.jar").resolve()
jpype.startJVM(classpath=[str(_GUMTREE_JAR_PATH)])

from com.github.gumtreediff.actions import ChawatheScriptGenerator
from com.github.gumtreediff.client import Run
from com.github.gumtreediff.io import ActionsIoUtils, TreeIoUtils
from com.github.gumtreediff.matchers import Matchers

# Based on https://github.com/GumTreeDiff/gumtree/wiki/GumTree-API#computing-the-edit-script-between-two-trees
Run.initGenerators()
_j_default_matcher = Matchers.getInstance().getMatcher()
_j_edit_script_generator = ChawatheScriptGenerator()
# type: XmlInternalGenerator.ReaderConfigurator
_j_tree_ctx_generator = TreeIoUtils.fromXml().generateFrom()


class GumTreeMatch(typing.TypedDict):
    """A single match item in a GumTreeDiff"""

    src: str
    dest: str


class GumTreeAction(typing.TypedDict, total=False):
    """A single edit action in a GumTreeDiff"""

    action: str
    tree: str
    at: int
    parent: str


class GumTreeDiff(typing.TypedDict):
    """TypedDict for GumTree diff"""

    actions: list[GumTreeAction]
    matches: list[GumTreeMatch]


def gumtree_diff(code_before: str, code_after: str) -> GumTreeDiff:
    """Computes a GumTree diff of two versions of Python code.

    Args:
        code_before: Python code before the change
        code_after: Python code after the change

    Returns:
        A `dict` containing the actions (for edit actions necessary to go from
        `code_before` to `code_after`) and matches (for identical code)
    """
    # We choose not to use PythonTreeGenerator which is built into GumTree.
    # PythonTreeGenerator is very slow because it launches a new Python process
    # to run pythonparser. It also doesn't work on Windows, because the original
    # version of pythonparser is a shell script, and Windows does not support
    # launching shell scripts as a process.
    # Instead, we run the pythonparser directly in our main Python process, then
    # feed the resulting XML string to GumTree.
    xml_before = python_code_to_gumtree_xml(code_before)
    xml_after = python_code_to_gumtree_xml(code_after)

    j_tree_ctx_before = _j_tree_ctx_generator.string(xml_before)
    if j_tree_ctx_before is None:
        raise ValueError(
            f"GumTree failed to parse Python code"
            f"\n{'Python code: ':-<80}\n{code_before}"
            f"\n{'XML representation: ':-<80}\n{xml_before}"
        )
    j_tree_ctx_after = _j_tree_ctx_generator.string(xml_after)
    if j_tree_ctx_after is None:
        raise ValueError(
            f"GumTree failed to parse Python code"
            f"\n{'Python code: ':-<80}\n{code_after}"
            f"\n{'XML representation: ':-<80}\n{xml_after}"
        )

    j_mappings = _j_default_matcher.match(
        j_tree_ctx_before.getRoot(), j_tree_ctx_after.getRoot()
    )
    j_actions = _j_edit_script_generator.computeActions(j_mappings)

    # Based on https://github.com/GumTreeDiff/gumtree/blob/594f2f69679eae0894bd99594a76320a6cd69670/client.diff/src/main/java/com/github/gumtreediff/client/diff/TextDiff.java#L129
    # type: ActionSerializer
    j_serializer = ActionsIoUtils.toJson(j_tree_ctx_before, j_actions, j_mappings)

    # ActionSerializer inherits toString() from AbstractSerializer, and can be
    # directly converted to string
    return json.loads(str(j_serializer))


def main():
    import pprint

    CODE_BEFORE = """
    def static_folder(self, value):
        if value is not None:
            value = os.fspath(value).rstrip(r"\\/")
        self._static_folder = value
    """.strip()
    CODE_AFTER = """
    def static_folder(self, value):
        if value is not None:
            value = fspath(value).rstrip(r"\\/")
        self._static_folder = value
    """.strip()
    print("STARTING WORK...")
    result = gumtree_diff(CODE_BEFORE, CODE_AFTER)
    print(f"{'Result: ':-<80}")
    pprint.pprint(result)
    print("DONE!")


if __name__ == "__main__":
    main()
