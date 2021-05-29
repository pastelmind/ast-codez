import dataclasses
from ast_codez_tools.file_change_result import FileChangeResult

if typing.TYPE_CHECKING:
    import scrapy.http

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
    repositories: list[str] = row["repo_name"]
    assert isinstance(repositories, list), f"repo_name is not a list: {row=}"
    assert repositories, f"repo_name is empty: {row=}"
    assert len(repositories) == len(
        set(repositories)
    ), f"repo_name contains non-unique repository names: {row=}"
            f"Repo {repositories[0]}, commit {commit_sha} is skipped because it has too many changes ({num_changes} > {MAX_ALLOWED_FILE_CHANGES} files changes)"
        yield FileChangeData(
            repositories=tuple(repositories),
            commit_before=parent_sha,
            commit_after=commit_sha,
            diff_index=diff_index,
            file_before=old_file_path,
            file_after=new_file_path,
            row_index=row_index,
def load_downloaded_changes(
    *, file_path: typing.Union[str, os.PathLike]
) -> typing.Set[FileChangeResultKey]:
    """Returns a set of FileChangeResultKey objects which represent file changes
    in `downloaded_data_file`.
    Loads a JSON Lines file containing FileChangeResult objects that have been
    downloaded so far, and extracts a set of FileChangeResultKey objects.
        with jsonlines.open(file_path, mode="r") as lines:
            return {FileChangeResultKey.from_dict(raw_entry) for raw_entry in lines}
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


        # We want to try forks in case of 404
        "HTTPERROR_ALLOWED_CODES": [404],
        # We intentionally read the file twice instead of storing the file in
        # a list. This is because the chunk files eat up a large amount of
        # memory (~300 MB observed).
        downloaded_changes = load_downloaded_changes(file_path=self.OUTPUT_FILE_PATH)
            file_change_entries = list(
                generate_file_change_data(row=row, row_index=row_index)
            )
            for fc_num, fc_data in enumerate(file_change_entries, start=1):
                if is_already_downloaded(downloaded_changes, fc_data):
                        f"Skipping already downloaded commit {row_index + 1} / {ROW_COUNT}, file {fc_num} / {len(file_change_entries)}"
                logging.debug(
                    f"Crawling commit {row_index + 1} / {ROW_COUNT}, file {fc_num} / {len(file_change_entries)}"
                # Store the fc_data object in the metadata of both requests.
                    url=fc_data.get_url_before(),
                    cb_kwargs={
                        "fc_data": fc_data,
                        "crawl_for": "url_before",
                        "repository": fc_data.get_current_repository(),
                    },
                    url=fc_data.get_url_after(),
                    cb_kwargs={
                        "fc_data": fc_data,
                        "crawl_for": "url_after",
                        "repository": fc_data.get_current_repository(),
                    },
    def parse(
        self,
        response: "scrapy.http.TextResponse",
        fc_data: FileChangeData,
        crawl_for: str,
        repository: str,
    ):
            assert fc_data.code_before is None
            fc_data.code_before = response.text
            assert fc_data.code_after is None
            fc_data.code_after = response.text
            raise ValueError(f"Unexpected {crawl_for=}, see related {fc_data=}")
        if fc_data.code_before is not None and fc_data.code_after is not None:
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