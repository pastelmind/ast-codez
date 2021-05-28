"""Modification of pythonparser from GumTree, adapted for our needs.

This code is based on the following file:
https://github.com/GumTreeDiff/pythonparser/blob/1ff1d4d7bb9660c881d8cc590bfa44b20c296e0b/pythonparser
"""

# pythonparser is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pythonparser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pythonparser.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2020-2021 Jean-Rémy Falleri <jr.falleri@gmail.com>

import typing
from xml.dom import minidom

import parso


def main(file):
    with open(file, mode="r") as f:
        code = f.read()
    print(python_code_to_gumtree_xml(code, pretty=True))


def python_code_to_gumtree_xml(code: str, *, pretty: bool = False) -> str:
    """Converts Python code to XML format supported by GumTree."""
    positions = make_code_positions(code)
    parso_ast = parso.parse(code)

    doc = minidom.Document()
    parso_ast = parso.parse(code)
    gumtree_ast = to_gumtree_node(doc, parso_ast, positions)
    assert gumtree_ast is not None
    doc.appendChild(gumtree_ast)
    process_node(parso_ast, gumtree_ast, positions)
    return doc.toprettyxml() if pretty else doc.toxml()


def process_node(
    parso_node, gumtree_node: minidom.Node, positions: typing.Sequence[int]
) -> None:
    if parso_node.type == "error_node":
        raise SyntaxError(f"parso failed to parse code: got {parso_node}")

    for parso_child in parso_node.children:
        gumtree_child = to_gumtree_node(
            gumtree_node.ownerDocument, parso_child, positions
        )
        if gumtree_child is not None:
            gumtree_node.appendChild(gumtree_child)
            if hasattr(parso_child, "children"):
                process_node(parso_child, gumtree_child, positions)


def to_gumtree_node(
    doc: minidom.Document, parso_node, positions: typing.Sequence[int]
) -> typing.Union[minidom.Node, None]:
    if parso_node.type in ("keyword", "newline", "endmarker"):
        return
    if parso_node.type == "operator" and parso_node.value in ".()[]:;":
        return

    gumtree_node = doc.createElement("tree")
    gumtree_node.setAttribute("type", parso_node.type)

    start = positions[parso_node.start_pos[0] - 1] + parso_node.start_pos[1]
    end = positions[parso_node.end_pos[0] - 1] + parso_node.end_pos[1]
    length = end - start
    gumtree_node.setAttribute("pos", str(start))
    gumtree_node.setAttribute("length", str(length))

    if not hasattr(parso_node, "children") or len(parso_node.children) == 0:
        gumtree_node.setAttribute("label", parso_node.value)

    return gumtree_node


def make_code_positions(code: str) -> list[int]:
    return [0, *(i for i, chr in enumerate(code, start=1) if chr == "\n")]


if __name__ == "__main__":
    import sys

    main(sys.argv[1])
