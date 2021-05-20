"""Commit data downloaded from BigQuery is too large to upload on GitHub
(<100 MB per file). This script splits each file into smaller chunks so we
can upload them."""

import gzip
import typing


def yield_line_from_files(
    *, source_files: typing.Iterable[str]
) -> typing.Iterator[str]:
    """Opens multiple gzipped text files in succession and yields each line."""
    for source_file in source_files:
        print(f"---- Loading lines from {source_file}...")
        with gzip.open(source_file, mode="rt", encoding="utf8") as source:
            yield from source
        print(f"---- All lines read from {source_file}")


def split_gzipped_text_files(
    *,
    source_files: typing.Iterable[str],
    target_file_pattern: str,
    max_lines_per_chunk: int,
) -> None:
    """Extracts lines from one or more gzipped text files and creates new
    (usually smaller) chunks from them.

    `target_file_pattern` must contain a `str.format()` parameter named `{chunk}`.
    """
    assert max_lines_per_chunk > 0

    chunk_count = 0
    lines = yield_line_from_files(source_files=source_files)
    while True:
        target_file_name = target_file_pattern.format(chunk=chunk_count)
        print(f"Saving to {target_file_name}...")

        with gzip.open(target_file_name, mode="wt", encoding="utf8") as target:

            for line_count, line in enumerate(lines, start=1):
                target.write(line)
                if line_count >= max_lines_per_chunk:
                    chunk_count += 1
                    break

        if line_count < max_lines_per_chunk:
            # If we reach here, the 'lines' iterator is very likely empty.
            print(
                f"Saved and closed {target_file_name} since all lines were extracted, wrote {line_count} lines"
            )
            break
        else:
            # If we reach here, the 'lines' iterator is probably not empty yet.
            # There is a very small chance that it is empty at this point, which
            # would cause the next chunk to be empty.
            # But it only happens when the total # of lines is a multiple of
            # max_lines_per_chunk, which is (1 / max_lines_per_chunk) chance.
            # Therefore, let's not care about it.
            print(
                f"Saved and closed {target_file_name} since it is full, wrote {line_count} lines"
            )


if __name__ == "__main__":
    split_gzipped_text_files(
        source_files=[
            "../mined_commits/mined_commits_2.000000000000.jsonl.gz",
            "../mined_commits/mined_commits_2.000000000001.jsonl.gz",
            "../mined_commits/mined_commits_2.000000000002.jsonl.gz",
            "../mined_commits/mined_commits_2.000000000003.jsonl.gz",
            "../mined_commits/mined_commits_2.000000000004.jsonl.gz",
        ],
        target_file_pattern="mined_commits/mined_commits_chunk{chunk:>02}.jsonl.gz",
        max_lines_per_chunk=100000,
    )
