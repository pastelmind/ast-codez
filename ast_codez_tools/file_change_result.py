"""Provides the FileChangeResult type.

This is used by both the scraping spider, and the data transformer.
"""
import typing


class FileChangeResult(typing.TypedDict):
    """Dictionary that stores information about a changed file, extracted from
    BigQuery data and augmented with file contents crawled directly from GitHub.

    This dictionary defines the data format saved by this script.
    """

    # Name of the repository, of format `<user_or_org>/<project_name>`
    repository: str
    # Commit SHA before the change
    commit_before: str
    # Commit SHA after the change
    commit_after: str
    diff_index: int
    # Path of the file before the change
    file_before: str
    # Path of the file after the change
    file_after: str
    # Download URL for the file before the change
    url_before: str
    # Download URL for the file after the change
    url_after: str
    # Index of the row in the chunk file that was used to generate this object.
    # This isn't really important; it's kept around "just in case".
    row_index: int
    # Contents of the file before the change
    code_before: str
    # Contents of the file after the change
    code_after: str
