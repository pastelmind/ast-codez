"""Converts the downloaded Change Entries into a format that can be passed to
seq2seq.

Steps for each change entry:

1. Excluded unwanted changes. These include:

    - If either the before_code or after_code cannot be parsed
      (May happen if they are Python 2 code, not Python 3)

2. From the before_code and after_code, extract top-level functions and methods
    of top-level classes.
    Find matching function/method pairs in before_code and after_code.

    See `function_pair_extractor.py` for more info.

3. Normalize before_code and after_code. This does:

    - Replaces identifiers and constants with special constants
      (e.g. INT_1, STR_1, IDENTIFIER_2) so that the model can work with a
      limited vocabulary.
    - Converts Python code to a single-line representation so that seq2seq can
      recognize semantically significant tokens (e.g. indents) as words.
    - If either the before_code or after_code has > 50 tokens, exclude them.

4. Exclude normalized function pairs that are identical.
    This leaves us with function pairs that have changes.
"""

import ast
import contextlib
import io
import logging
import sys
import tokenize
import typing

import jsonlines

from ast_codez_tools.code_normalizer import (
    CodeNormalizer,
    ReplacementMap,
    extract_identifiers,
)
from ast_codez_tools.file_change_result import FileChangeResult
from ast_codez_tools.function_pair_extractor import extract_function_pairs
from ast_codez_tools.gumtree_pydiff import gumtree_diff
from idiom_loader import IdiomDatabase, load_idioms

MAX_TOKEN_COUNT = 50


def yield_changed_entries(
    *, changed_entries_file: str
) -> typing.Iterator[FileChangeResult]:
    with jsonlines.open(changed_entries_file, mode="r") as rows:
        yield from typing.cast(typing.Iterator[FileChangeResult], rows)


class FunctionChangeEntry(typing.TypedDict):
    name: str
    before_code: str
    after_code: str
    before_code_normalized: str
    after_code_normalized: str
    edit_actions: list[str]
    replacement_map: ReplacementMap


def sanitize_code(code: str) -> str:
    """Apparently, some of the downloaded code contains null bytes?
    Not sure how they snuck into code.
    In any case, this removes it."""
    return code.replace("\0", "")


@contextlib.contextmanager
def set_recursion_limit(n: int):
    """Context manager that temporarily changes the maximum recursion limit."""
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(n)
    try:
        yield
    finally:
        sys.setrecursionlimit(old_limit)


def extract_normalized_function_changes(
    *, changed_entries_file: str
) -> typing.Iterator[FunctionChangeEntry]:
    """
    Yields:
        Tuple of `(func_name, before_code_normalized, after_code_normalized)`
    """
    idioms = load_idioms()

    for row in yield_changed_entries(changed_entries_file=changed_entries_file):
        repo_name = row["repository"]
        commit_before = row["commit_before"]
        commit_after = row["commit_after"]
        file_before = row["file_before"]
        file_after = row["file_after"]
        code_before = sanitize_code(row["code_before"])
        code_after = sanitize_code(row["code_after"])

        try:
            for function_pair in extract_function_pairs(
                before_code=code_before,
                before_name=f"{repo_name}:{commit_before}:{file_before}",
                after_code=code_after,
                after_name=f"{repo_name}:{commit_after}:{file_after}",
            ):
                # Very rarely, ast.unparse() fails to convert an AST node
                # back to Python code.
                # Since we don't have a nice way of recovering from this,
                # we'll skip this code instead.
                try:
                    func_code_before = ast.unparse(function_pair.before_node)
                except ValueError as error:
                    logging.warning(
                        f"Failed to unparse code; skipping {repo_name}:{commit_before}:{file_before}:{function_pair.func_name}",
                        exc_info=error,
                    )
                    continue
                try:
                    func_code_after = ast.unparse(function_pair.after_node)
                except ValueError as error:
                    logging.warning(
                        f"Failed to unparse code; skipping {repo_name}:{commit_after}:{file_after}:{function_pair.func_name}",
                        exc_info=error,
                    )
                    continue

                # normalize_code_pair() mutates the before_node and after_node
                # in place. Because of this, it must be called after unparsing
                # func_code_before and func_code_after
                (
                    norm_before_code,
                    norm_after_code,
                    replacement_map,
                ) = normalize_code_pair(
                    idioms=idioms,
                    before_node=function_pair.before_node,
                    after_node=function_pair.after_node,
                )

                try:
                    norm_before_code = transform_to_oneline(norm_before_code)
                    norm_after_code = transform_to_oneline(norm_after_code)
                except TooManyTokensError:
                    continue

                if norm_before_code == norm_after_code:
                    logging.debug(
                        f"Skipped identical function after normalizing: {repo_name}:{commit_after}:{file_after}:{function_pair.func_name}()"
                    )
                    continue

                diff_result = gumtree_diff(
                    code_before=func_code_before,
                    code_after=func_code_after,
                )

                yield FunctionChangeEntry(
                    name=f"{repo_name}:{commit_after}:{file_after}:{function_pair.func_name}",
                    before_code=func_code_before,
                    after_code=func_code_after,
                    before_code_normalized=norm_before_code,
                    after_code_normalized=norm_after_code,
                    edit_actions=[
                        edit_action["action"] for edit_action in diff_result["actions"]
                    ],
                    replacement_map=replacement_map,
                )
        except SyntaxError as e:
            # We may have invalid Python code, or Python 2 code
            #
            # Fortunately, we don't need care about hashbang because ast.parse()
            # ignores it
            logging.debug(
                f"Skipped because of invalid Python syntax in {repo_name}:{commit_after}:{file_after}\n{e.msg}"
            )
        except:
            logging.error(
                f"Error while processing {repo_name}:{commit_after}:{file_after}"
            )
            raise


def normalize_code_pair(
    *, idioms: IdiomDatabase, before_node: ast.AST, after_node: ast.AST
) -> typing.Tuple[str, str, ReplacementMap]:
    """Normalizes before_node, after_node using a single CodeNormalizer.

    Using the same CodeNormalizer instance allows identical identifiers to be
    normalized in a predictable manner.

    NOTE: This modifies `before_node` and `after_node` in place.
    """
    identifiers = extract_identifiers(before_node) | extract_identifiers(after_node)
    normalizer = CodeNormalizer(identifiers=identifiers, idioms=idioms)
    # According to our paper, order is important.
    # We process
    normalized_before_code = ast.unparse(normalizer.visit(before_node))
    normalized_after_code = ast.unparse(normalizer.visit(after_node))
    return (
        normalized_before_code,
        normalized_after_code,
        normalizer.get_replacement_map(),
    )


class TooManyTokensError(ValueError):
    """Raised when the input code has too many tokens."""


def transform_to_oneline(code: str) -> str:
    """Transforms the given Python code to a single-line representation."""

    def generate_token_strings(code: str) -> typing.Iterator[str]:
        # I took inspiration from Nabila's code
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            # Strip comments and logically insignificant newlines
            if tok.type == tokenize.NL or tok.type == tokenize.COMMENT:
                continue
            # Replace logically significant whitespace
            elif tok.type == tokenize.NEWLINE:
                yield "$NEWLINE"
            elif tok.type == tokenize.INDENT:
                yield "$INDENT"
            elif tok.type == tokenize.DEDENT:
                yield "$DEDENT"
            else:
                yield tok.string

    # Count tokens after removing NL and COMMENT
    def limit_token_count(token_strings: typing.Iterable[str]) -> typing.Iterator[str]:
        for token_count, tok_str in enumerate(token_strings, start=1):
            # seq2seq accepts <= 50 words per sequence.
            # We could configure the model to accept longer sequences, but it's
            # probably better to stick to what the original authors used
            if token_count > MAX_TOKEN_COUNT:
                raise TooManyTokensError()
            yield tok_str

    one_liner = " ".join(limit_token_count(generate_token_strings(code)))
    assert "\n" not in one_liner, (
        f"Cannot transform code to one-liner:\n"
        + "-" * 80
        + f"\n{code}\n"
        + "-" * 80
        + "\nTransformed to:\n"
        + "-" * 80
        + f"\n{one_liner}"
    )
    return one_liner


def main():
    import pathlib

    CHUNK_NUM = int(input("Enter downloaded chunk number: "))

    output_dir = pathlib.Path("../dataset/")
    output_file_before = output_dir / f"buggy{CHUNK_NUM}.txt"
    output_file_after = output_dir / f"fixed{CHUNK_NUM}.txt"
    output_file_data = output_dir / f"data{CHUNK_NUM}.jsonl"
    lines_written = 0

    output_dir.mkdir(parents=True, exist_ok=True)

    with set_recursion_limit(1500), open(
        output_file_before, mode="wt", newline="\n"
    ) as outfile_before, open(
        output_file_after, mode="wt", newline="\n"
    ) as outfile_after, typing.cast(
        jsonlines.Writer, jsonlines.open(output_file_data, mode="w")
    ) as outfile_data:
        for entry in extract_normalized_function_changes(
            changed_entries_file=f"../github_file_changes/file_changes_chunk{CHUNK_NUM}.jsonl"
        ):
            outfile_before.write(entry["before_code_normalized"])
            outfile_before.write("\n")
            outfile_after.write(entry["after_code_normalized"])
            outfile_after.write("\n")
            outfile_data.write(entry)

            lines_written += 1
            if lines_written % 500 == 0:
                logging.info(f"Processed {lines_written} function pairs")

    logging.info(
        f"Wrote {lines_written} lines to {output_file_before}, {output_file_after}, {output_file_data}"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
