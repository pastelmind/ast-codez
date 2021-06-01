"""Scrapy spider that downloads all before/after files for a commit chunk file.

Run with:

    scrapy runspider scrapy_github_files.py
"""

import dataclasses
import gzip
import logging
import os
import pathlib
import re
import typing

import fake_useragent
import jsonlines
import scrapy

from ast_codez_tools.file_change_result import FileChangeResult

if typing.TYPE_CHECKING:
    import scrapy.http


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


class FileChangeResultKey(typing.NamedTuple):
    """NamedTuple that uniquely identifies a FileChangeResult object.

    This consists of fields in a FileChangeResult that uniquely identify it.
    It is meant to act as a unique identifier (or "composite key") when skipping
    file changes that have been already crawled.
    """

    repository: str
    commit_before: str
    commit_after: str
    file_before: str
    file_after: str

    @classmethod
    def from_dict(cls, raw_entry: FileChangeResult) -> "FileChangeResultKey":
        """Creates a FileChangeResultKey from a dictionary (preferably, one that
        conforms to FileChangeResult)."""
        return cls(
            repository=raw_entry["repository"],
            commit_before=raw_entry["commit_before"],
            commit_after=raw_entry["commit_after"],
            file_before=raw_entry["file_before"],
            file_after=raw_entry["file_after"],
        )


class AllRepositoriesInvalidatedError(Exception):
    """Raised when all repositories have been invalidated"""


GITHUB_FILE_DOWNLOAD_URL = "https://raw.githubusercontent.com/{repo}/{sha}/{path}"


@dataclasses.dataclass
class FileChangeData:
    """Dataclass used to store data about a file change being crawled.

    This is an intermediate format and is NOT meant to be stored as the final
    result. Use `FileChangeResult` for that.
    """

    # Names of repositories associated with this change.
    # A repository can have multiple forks.
    repositories: typing.Tuple[str, ...]
    # Index of the repository being crawled in `self.repositories`.
    _current_repository_index: int = dataclasses.field(default=0, init=False)
    # SHA of the commit before the change
    commit_before: str
    # SHA of the commit after the change
    commit_after: str
    # Index of the current file in the list of files that were changed by this
    # change.
    # This is an unimportant field, but is kept around "just in case".
    diff_index: int
    # Path of the file in the repository before the change
    file_before: str
    # Path of the file in the repository after the change
    file_after: str
    # Index of the row in the chunk file that was used to generate this object.
    # This isn't really important; it's kept around "just in case".
    row_index: int
    code_before: typing.Optional[str] = None
    code_after: typing.Optional[str] = None

    def get_current_repository(self) -> str:
        """Returns the currently selected repository.

        Raises:
            AllRepositoriesInvalidatedError: If all repositories were invaliated
        """
        try:
            return self.repositories[self._current_repository_index]
        except IndexError:
            raise AllRepositoriesInvalidatedError() from None

    def select_next_repository(self) -> bool:
        """Selects the next repository and returns True. If there is no next
        repository, returns False."""
        self._current_repository_index += 1
        if self._current_repository_index >= len(self.repositories):
            self._current_repository_index = len(self.repositories)
            return False
        else:
            return True

    def get_url_before(self) -> str:
        return GITHUB_FILE_DOWNLOAD_URL.format(
            repo=self.get_current_repository(),
            sha=self.commit_before,
            path=self.file_before,
        )

    def get_url_after(self) -> str:
        return GITHUB_FILE_DOWNLOAD_URL.format(
            repo=self.get_current_repository(),
            sha=self.commit_after,
            path=self.file_after,
        )


def generate_file_change_data(
    *, row: dict, row_index: int
) -> typing.Iterator[FileChangeData]:
    """Parses a dictionary containing commit info and yields one dict for each
    file that should be crawled."""

    commit_sha = row["commit"]

    # Skip if the commit has no parents (i.e. is the first commit)
    if len(row["parent"]) == 0:
        return
    # A Git commit can have multiple parents (e.g. merges).
    # In this case, we select the first commit (this is a wild guess).
    parent_sha = row["parent"][0]

    repositories: list[str] = row["repo_name"]
    assert isinstance(repositories, list), f"repo_name is not a list: {row=}"
    assert repositories, f"repo_name is empty: {row=}"
    assert len(repositories) == len(
        set(repositories)
    ), f"repo_name contains non-unique repository names: {row=}"

    skipped_commit_count = 0

    # If there are too many changes, the scope is probably too wide for us
    MAX_ALLOWED_FILE_CHANGES = 5
    num_changes = len(row["difference"])
    if num_changes > MAX_ALLOWED_FILE_CHANGES:
        logging.debug(
            f"Repo {repositories[0]}, commit {commit_sha} is skipped because it has too many changes ({num_changes} > {MAX_ALLOWED_FILE_CHANGES} files changes)"
        )
        skipped_commit_count += 1
        if skipped_commit_count % 100 == 0:
            logging.info(
                f"Skipped {skipped_commit_count} commits because they had too many changes (more than {MAX_ALLOWED_FILE_CHANGES} files changed)"
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

        yield FileChangeData(
            repositories=tuple(repositories),
            commit_before=parent_sha,
            commit_after=commit_sha,
            diff_index=diff_index,
            file_before=old_file_path,
            file_after=new_file_path,
            row_index=row_index,
        )


def load_downloaded_changes(
    *, file_path: typing.Union[str, os.PathLike]
) -> typing.Set[FileChangeResultKey]:
    """Returns a set of FileChangeResultKey objects which represent file changes
    in `downloaded_data_file`.

    Loads a JSON Lines file containing FileChangeResult objects that have been
    downloaded so far, and extracts a set of FileChangeResultKey objects.
    This can be used to skip crawling entries that have already downloaded when
    resuming from a crash.

    If `downloaded_data_file` does not exist, returns an empty set.
    """
    try:
        with jsonlines.open(file_path, mode="r") as lines:
            return {FileChangeResultKey.from_dict(raw_entry) for raw_entry in lines}
    except FileNotFoundError:
        return set()


def is_already_downloaded(
    downloaded_entries: typing.Set[FileChangeResultKey], fc_entry: FileChangeData
) -> bool:
    """Checks if the file contents that will be crawled according to `fc` is
    already present in `downloaded_entries`."""
    for repository in fc_entry.repositories:
        # We need to create a NamedTuple for every repository we want to check.
        # This is not ideal, but I wasn't thinking too clear when designing the
        # original output format, and we'd rather reuse existing data rather
        # than crawl GitHub all over again.
        if (
            FileChangeResultKey(
                repository=repository,
                commit_before=fc_entry.commit_before,
                commit_after=fc_entry.commit_after,
                file_before=fc_entry.file_before,
                file_after=fc_entry.file_after,
            )
            in downloaded_entries
        ):
            return True
    return False


# Must request chunk file name here to configure spider before it is picked up
# by Scrapy!
CHUNK_FILE_NAME, CHUNK_NUMBER = select_chunk_file()
OUTPUT_FILE_PATH = pathlib.Path(
    f"../github_file_changes/file_changes_chunk{CHUNK_NUMBER}.jsonl"
)
logging.info(f"Chunk {CHUNK_FILE_NAME} selected, writing to {OUTPUT_FILE_PATH}")


class GithubFilesSpider(scrapy.Spider):
    name = f"github_files_chunk{CHUNK_NUMBER}"
    allowed_domains = ["raw.githubusercontent.com"]

    custom_settings = {
        # We want to try forks in case of 404
        "HTTPERROR_ALLOWED_CODES": [404],
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
        "AUTOTHROTTLE_START_DELAY": 0.01,
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
        # We intentionally read the file twice instead of storing the file in
        # a list. This is because the chunk files eat up a large amount of
        # memory (~300 MB observed).
        ROW_COUNT = sum(1 for _ in load_gzipped_lines(file_name=self.CHUNK_FILE_NAME))

        # For resuming interrupted crawling sessions
        downloaded_changes = load_downloaded_changes(file_path=self.OUTPUT_FILE_PATH)
        logging.info(
            f"Found {len(downloaded_changes)} change entries that were downloaded in a previous run"
        )

        skipped_file_count = 0

        for row_index, row in enumerate(
            load_gzipped_lines(file_name=self.CHUNK_FILE_NAME)
        ):
            file_change_entries = list(
                generate_file_change_data(row=row, row_index=row_index)
            )

            for fc_num, fc_data in enumerate(file_change_entries, start=1):
                if is_already_downloaded(downloaded_changes, fc_data):
                    logging.debug(
                        f"Skipping already downloaded commit {row_index + 1} / {ROW_COUNT}, file {fc_num} / {len(file_change_entries)}"
                    )
                    skipped_file_count += 1
                    if skipped_file_count % 1000 == 0:
                        logging.info(
                            f"Skipped {skipped_file_count} files that were already downloaded"
                        )
                    continue

                logging.debug(
                    f"Crawling commit {row_index + 1} / {ROW_COUNT}, file {fc_num} / {len(file_change_entries)}"
                )

                # Store the fc_data object in the metadata of both requests.
                # This allows us to recombine the requests after they are
                # downloaded.
                yield scrapy.Request(
                    url=fc_data.get_url_before(),
                    cb_kwargs={
                        "fc_data": fc_data,
                        "crawl_for": "url_before",
                        "repository": fc_data.get_current_repository(),
                    },
                )
                yield scrapy.Request(
                    url=fc_data.get_url_after(),
                    cb_kwargs={
                        "fc_data": fc_data,
                        "crawl_for": "url_after",
                        "repository": fc_data.get_current_repository(),
                    },
                )

    def parse(
        self,
        response: "scrapy.http.TextResponse",
        fc_data: FileChangeData,
        crawl_for: str,
        repository: str,
    ):
        if crawl_for == "url_before":
            assert fc_data.code_before is None
            fc_data.code_before = response.text
        elif crawl_for == "url_after":
            assert fc_data.code_after is None
            fc_data.code_after = response.text
        else:
            raise ValueError(f"Unexpected {crawl_for=}, see related {fc_data=}")

        if fc_data.code_before is not None and fc_data.code_after is not None:
            # We are complete
            yield FileChangeResult(
                repository=repository,
                commit_before=fc_data.commit_before,
                commit_after=fc_data.commit_after,
                diff_index=fc_data.diff_index,
                file_before=fc_data.file_before,
                file_after=fc_data.file_after,
                url_before=fc_data.get_url_before(),
                url_after=fc_data.get_url_after(),
                row_index=fc_data.row_index,
                code_before=fc_data.code_before,
                code_after=fc_data.code_after,
            )
        else:
            # Skip this one since it is incomplete
            return
