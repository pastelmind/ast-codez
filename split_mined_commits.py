"""Commit data downloaded from BigQuery is too large to upload on GitHub
(<100 MB per file). This script splits each file into smaller chunks so we
can upload them."""

import gzip


MAX_LINES_PER_CHUNK = 300000


def split_gzipped_text_file(*, source_file: str, target_file_pattern: str) -> None:
    with gzip.open(source_file, mode="rt", encoding="utf8") as source:
        chunk_count = 0
        while True:
            target_file_name = target_file_pattern.format(chunk=chunk_count)
            with gzip.open(
                target_file_name,
                mode="wt",
                encoding="utf8",
            ) as target:
                for line_count, line in enumerate(source):
                    target.write(line)
                    if line_count >= MAX_LINES_PER_CHUNK:
                        chunk_count += 1
                        break
            print(f"Wrote {line_count} lines to {target_file_name}")
            if line_count < MAX_LINES_PER_CHUNK:
                # We haven't reached the end yet
                break


if __name__ == "__main__":
    for i in range(5):
        split_gzipped_text_file(
            source_file=f"mined_commits/mined_commits_2.00000000000{i}.jsonl.gz",
            target_file_pattern=f"mined_commits/mined_commits_2.00000000000{i}.chunk{{chunk}}.jsonl.gz",
        )
