"""Merges all preprocessed entries into single files."""

import re
import typing
from itertools import zip_longest
from os import name
from pathlib import Path

import jsonlines

from ast_codez_tools.function_change_entry import FunctionChangeEntry


def main():
    dataset_dir = Path("../dataset/")

    chunks_seen: dict[int, Path] = {}
    for file_data_path in dataset_dir.glob("data*.jsonl"):
        if not (match := re.match(r"^data(\d+)\.jsonl$", file_data_path.name)):
            continue
        chunks_seen[int(match[1])] = file_data_path

    print(
        f"Chunks seen: {', '.join(str(chunk_num) for chunk_num in sorted(chunks_seen))}"
    )

    file_before_all_path = dataset_dir / "buggy_all.txt"
    file_after_all_path = dataset_dir / "fixed_all.txt"
    file_data_all_path = dataset_dir / "data_all.jsonl"
    total_count = 0

    with open(file_before_all_path, mode="w", encoding="utf8") as file_before_all, open(
        file_after_all_path, mode="w", encoding="utf8"
    ) as file_after_all, typing.cast(
        jsonlines.Writer, jsonlines.open(file_data_all_path, mode="w")
    ) as file_data_all:

        for chunk_num, file_data_path in sorted(chunks_seen.items()):
            file_before_path = dataset_dir / f"buggy{chunk_num}.txt"
            file_after_path = dataset_dir / f"fixed{chunk_num}.txt"
            count = 0

            with open(file_before_path, encoding="utf8") as file_before, open(
                file_after_path, encoding="utf8"
            ) as file_after, typing.cast(
                jsonlines.Reader, jsonlines.open(file_data_path, mode="r")
            ) as file_data:

                for count, (before_code, after_code, entry) in enumerate(
                    zip_longest(file_before, file_after, file_data)
                ):
                    # Bunch of sanity checks
                    assert (
                        before_code is not None
                    ), f"File length mismatch: {file_before_path} terminated before {file_after_path}, {file_data_path}"
                    assert (
                        after_code is not None
                    ), f"File length mismatch: {file_after_path} terminated before {file_before_path}, {file_data_path}"
                    assert (
                        entry is not None
                    ), f"File length mismatch: {file_data_path} terminated before {file_before_path}, {file_after_path}"

                    entry = typing.cast(FunctionChangeEntry, entry)
                    assert (
                        entry["before_code_normalized"].rstrip() == before_code.rstrip()
                    ), f"Mismatch in before_code of {entry['name']} in {file_data_path}"
                    assert (
                        entry["after_code_normalized"].rstrip() == after_code.rstrip()
                    ), f"Mismatch in after_code of {entry['name']} in {file_data_path}"

                    file_before_all.write(before_code)
                    file_after_all.write(after_code)
                    file_data_all.write(entry)

            print(
                f"Copied {count} lines from {file_before_path}, {file_after_path}, {file_data_path}"
            )
            total_count += count

    print(
        f"Saved {total_count} lines to {file_before_all_path}, {file_after_all_path}, {file_data_all_path}"
    )


if __name__ == "__main__":
    main()
