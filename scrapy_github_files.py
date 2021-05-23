"""Scrapy spider that downloads all before/after files for a commit chunk file.

Run with:

    scrapy runspider scrapy_github_files.py
"""

import gzip
import logging
import os
import pathlib
import re
import typing

import fake_useragent
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


class CrawledFileChange(typing.TypedDict, total=False):
    """Dictionary that stores information about a changed file, extracted from
    BigQuery data and augmented with file contents crawled directly from GitHub.

    This dictionary defines the data format saved by this script.
    """

    repository: str
    commit_before: str
    commit_after: str
    diff_index: int
    file_before: str
    file_after: str
    url_before: str
    url_after: str
    code_before: str
    code_after: str


def generate_diff_infos(*, row: dict) -> typing.Iterator[CrawledFileChange]:
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

        yield CrawledFileChange(
            repository=repo,
            commit_before=parent_sha,
            commit_after=commit_sha,
            diff_index=diff_index,
            file_before=old_file_path,
            file_after=new_file_path,
            url_before=url_before,
            url_after=url_after,
        )


class DownloadedChangeEntry(typing.NamedTuple):
    repository: str
    # Commit SHA before the change
    commit_before: str
    # Commit SHA after the
    commit_after: str
    # Path of the file before the change
    file_before: str
    # Path of the file after the change
    file_after: str

    @classmethod
    def from_dict(cls, raw_entry: typing.Dict[str, str]) -> "DownloadedChangeEntry":
        """Creates a DownloadedChangeEntry from a dictionary."""
        return cls(
            repository=raw_entry["repository"],
            commit_before=raw_entry["commit_before"],
            commit_after=raw_entry["commit_after"],
            file_before=raw_entry["file_before"],
            file_after=raw_entry["file_after"],
        )


def load_downloaded_entry_infos(
    *, downloaded_data_file: typing.Union[str, os.PathLike]
) -> typing.Set[DownloadedChangeEntry]:
    """Returns a set of Change Entries that are already downloaded.

    Loads a JSON Lines file containing Change Entries that have been downloaded
    so far, and extracts a set of DownloadedChangeEntry objects.
    This can be used to skip crawling entries that have already downloaded when
    resuming from a crash.

    If `downloaded_data_file` does not exist, returns an empty set.
    """
    try:
        with jsonlines.open(downloaded_data_file, mode="r") as lines:
            return {DownloadedChangeEntry.from_dict(raw_entry) for raw_entry in lines}
    except FileNotFoundError:
        return set()


# Must request chunk file name here to configure spider before it is picked up
# by Scrapy!
CHUNK_FILE_NAME, CHUNK_NUMBER = select_chunk_file()
OUTPUT_FILE_PATH = pathlib.Path(
    f"../github_file_changes/file_changes_chunk{CHUNK_NUMBER}.jsonl"
)


class GithubFilesSpider(scrapy.Spider):
    name = f"github_files_chunk{CHUNK_NUMBER}"
    allowed_domains = ["raw.githubusercontent.com"]

    custom_settings = {
        # These settings should help us avoid getting banned
        "AUTOTHROTTLE_ENABLED": True,
        # Repositories that have been deleted return 404 errors. These responses
        # are not saved in the output JSON Lines file.
        # When the spider resumes from an interrupted run, it attempts to crawl
        # these repositories again, running into many 404 errors. This is OK.
        # Unfortunately, AutoThrottle ignores 404 errors when adjusting the
        # delay, which causes Scrapy to retain the 5-second delay until the
        # first non-404 response is found. This can cause the spider to slow
        # down a lot.
        # We explicitly set the initial download delay to a small value to avoid
        # this phenomenon.
        # Note: This could also be solved by remembering the 404 result, or by
        # fetching a fork that is still alive. But I don't have time to do
        # either right now.
        "AUTOTHROTTLE_START_DELAY": 0.5,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 5,
        "COOKIES_ENABLED": False,
        "USER_AGENT": fake_useragent.UserAgent().random,
        "FEEDS": {
            OUTPUT_FILE_PATH: {
                "format": "jsonlines",
            },
        },
        # Suppress printing the final item object to stdout
        "LOG_LEVEL": logging.INFO,
    }
    CHUNK_FILE_NAME = CHUNK_FILE_NAME
    OUTPUT_FILE_PATH = OUTPUT_FILE_PATH

    def start_requests(self):
        ROW_COUNT = sum(1 for _ in load_gzipped_lines(file_name=self.CHUNK_FILE_NAME))

        # For resuming interrupted crawling sessions
        downloaded_changes = load_downloaded_entry_infos(
            downloaded_data_file=self.OUTPUT_FILE_PATH
        )
        logging.info(
            f"Found {len(downloaded_changes)} change entries that were downloaded in a previous run"
        )

        for row_index, row in enumerate(
            load_gzipped_lines(file_name=self.CHUNK_FILE_NAME)
        ):
            diff_infos = list(generate_diff_infos(row=row))

            for diff_num, diff_entry in enumerate(
                generate_diff_infos(row=row), start=1
            ):
                if DownloadedChangeEntry.from_dict(diff_entry) in downloaded_changes:
                    logging.info(
                        f"Skipping already downloaded commit {row_index + 1} / {ROW_COUNT}, file {diff_num} / {len(diff_infos)}"
                    )
                    continue

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
        diff_entry: CrawledFileChange = response.meta["diff_entry"]
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
