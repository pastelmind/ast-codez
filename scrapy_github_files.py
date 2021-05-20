"""Scrapy spider that downloads all before/after files for a commit chunk file.

Run with:

    scrapy runspider scrapy_github_files.py
"""

import gzip
import logging
import os
import pathlib
import random
import re
import typing

import jsonlines
import scrapy


def select_chunk_file() -> typing.Tuple[pathlib.Path, int]:
    """Asks the user to pick a chunk number, then returns a tuple of
    (selected chunk file name, chunk number)."""
    files_found: typing.Dict[int, pathlib.Path] = {}

    for file_name in sorted(pathlib.Path("./mined_commits").glob("*.jsonl.gz")):
        match = re.search(r"chunk(\d+)", str(file_name))
        assert match
        chunk_number = int(match[1])
        files_found[chunk_number] = file_name

    chunk_number_selected = int(
        input(f"Choose a chunk # to process ({min(files_found)}-{max(files_found)}): ")
    )
    return (files_found[chunk_number_selected], chunk_number_selected)


def load_gzipped_lines(
    *, file_name: typing.Union[str, os.PathLike]
) -> typing.Iterator[dict]:
    """Loads each line from a gzipped JSON Lines file."""
    with gzip.open(file_name, mode="rt", encoding="utf8") as gzipped_file:
        with jsonlines.Reader(gzipped_file) as lines:
            yield from lines


def generate_diff_infos(*, row: dict) -> typing.Iterator[dict]:
    """Parses a dictionary containing commit info and yields one dict for each
    file that should be crawled."""

    commit_sha = row["commit"]

    # Skip if the commit has no parents (i.e. is the first commit)
    if len(row["parent"]) == 0:
        return
    # A Git commit can have multiple parents (e.g. merges).
    # In this case, we select the first commit (this is a wild guess).
    parent_sha = row["parent"][0]

    repo_name = row["repo_name"]
    repo = repo_name[0] if isinstance(repo_name, list) else repo_name

    # If there are too many changes, the scope is probably too wide for us
    MAX_ALLOWED_FILE_CHANGES = 5
    num_changes = len(row["difference"])
    if num_changes > MAX_ALLOWED_FILE_CHANGES:
        logging.info(
            f"Repo {repo}, commit {commit_sha} is skipped because it has too many changes ({num_changes} > {MAX_ALLOWED_FILE_CHANGES} files changes)"
        )
        return

    for diff_index, diff in enumerate(row["difference"]):
        # If the old/new file mode is missing, it means that the file was
        # created or removed in this commit.
        # Such changes are not our concern, so let's skip them
        if "new_mode" not in diff or "old_mode" not in diff:
            continue

        old_file_path = diff["old_path"]
        new_file_path = diff["new_path"]

        GITHUB_FILE_DOWNLOAD_URL = (
            "https://raw.githubusercontent.com/{repo}/{sha}/{path}"
        )
        url_before = GITHUB_FILE_DOWNLOAD_URL.format(
            repo=repo, sha=parent_sha, path=old_file_path
        )
        url_after = GITHUB_FILE_DOWNLOAD_URL.format(
            repo=repo, sha=commit_sha, path=new_file_path
        )

        yield {
            "repository": repo,
            "commit_before": parent_sha,
            "commit_after": commit_sha,
            "diff_index": diff_index,
            "file_before": old_file_path,
            "file_after": new_file_path,
            "url_before": url_before,
            "url_after": url_after,
        }


# Must request chunk file name here to configure spider before it is picked up
# by Scrapy!
CHUNK_FILE_NAME, CHUNK_NUMBER = select_chunk_file()


class GithubFilesSpider(scrapy.Spider):
    name = f"github_files_chunk{CHUNK_NUMBER}"
    allowed_domains = ["raw.githubusercontent.com"]

    custom_settings = {
        # These settings should help us avoid getting banned
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 10,
        "COOKIES_ENABLED": False,
        "USER_AGENT": random.choice(
            [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36 Edg/90.0.818.62",
            ]
        ),
        "FEEDS": {
            f"../github_file_changes/file_changes_chunk{CHUNK_NUMBER}.jsonl": {
                "format": "jsonlines",
            },
        },
        # Suppress printing the final item object to stdout
        "LOG_LEVEL": logging.INFO,
    }
    CHUNK_FILE_NAME = CHUNK_FILE_NAME

    def start_requests(self):
        ROW_COUNT = sum(1 for _ in load_gzipped_lines(file_name=self.CHUNK_FILE_NAME))

        for row_index, row in enumerate(
            load_gzipped_lines(file_name=self.CHUNK_FILE_NAME)
        ):
            diff_infos = list(generate_diff_infos(row=row))

            for diff_num, diff_entry in enumerate(
                generate_diff_infos(row=row), start=1
            ):
                logging.info(
                    f"Crawling commit {row_index + 1} / {ROW_COUNT}, file {diff_num} / {len(diff_infos)}"
                )
                diff_entry["row_index"] = row_index

                # Pass the entry dict as the diff_entry for both requests.
                # This allows us to recombine the requests after they are
                # downloaded.
                yield scrapy.Request(
                    url=diff_entry["url_before"],
                    meta={"diff_entry": diff_entry, "crawl_for": "url_before"},
                )
                yield scrapy.Request(
                    url=diff_entry["url_after"],
                    meta={"diff_entry": diff_entry, "crawl_for": "url_after"},
                )

    def parse(self, response):
        diff_entry: dict = response.meta["diff_entry"]
        crawl_for: str = response.meta["crawl_for"]

        if crawl_for == "url_before":
            assert "code_before" not in diff_entry
            diff_entry["code_before"] = response.text
        elif crawl_for == "url_after":
            assert "code_after" not in diff_entry
            diff_entry["code_after"] = response.text
        else:
            raise ValueError(f"Unexpected {crawl_for=}, see related {diff_entry=}")

        if "code_before" in diff_entry and "code_after" in diff_entry:
            # We are complete
            yield diff_entry
        else:
            # Skip this one since it is incomplete
            return
