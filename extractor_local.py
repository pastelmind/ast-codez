"""Variant on Adil's extractor.py that uses commit data in gzip files downloaded
from Google BigQuery."""

import gzip
import itertools
import json
import time
import traceback
import typing

import colorama
import jsonlines
import requests
from colorama import Fore, Style

colorama.init()

GIT_TOKEN = ""

GITHUB_FILE_DOWNLOAD_URL = "https://raw.githubusercontent.com/{repo}/{sha}/{path}"

# Crawling params
REQUEST_HEADERS = {
    # "Accept": "application/vnd.github.v3+json",
    # "Authorization": "token " + GIT_TOKEN,
}
REQUEST_TIMEOUT = 30  # seconds


def get_commit_entry(*, gzip_file: str):
    with gzip.open(
        gzip_file,
        mode="rt",
        encoding="utf8",
    ) as gzip_content, jsonlines.Reader(gzip_content) as reader:
        yield from reader


def crawl_commit_file(
    *,
    repo: str,
    parent_sha: str,
    commit_sha: str,
    diff: dict,
    session: requests.Session,
) -> typing.Union[dict, None]:
    """Download before & after code for a single file (diff entry) in a commit.

    If the diff is empty, returns None
    """
    # If the old/new file mode is missing, it means that the file was
    # created or removed in this commit.
    # Such changes are not our concern, so let's skip them
    if "new_mode" not in diff or "old_mode" not in diff:
        return None

    old_file_path = diff["old_path"]
    new_file_path = diff["new_path"]

    # Cut this indirection! We can build a download URL right away!
    url_before = GITHUB_FILE_DOWNLOAD_URL.format(
        repo=repo, sha=parent_sha, path=old_file_path
    )
    url_after = GITHUB_FILE_DOWNLOAD_URL.format(
        repo=repo, sha=commit_sha, path=new_file_path
    )

    print(f"{url_before=}\n{url_after=}")

    response_before = session.get(
        url_before,
        headers=REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    response_before.raise_for_status()
    raw_before = response_before.text

    response_after = session.get(
        url_after, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
    )
    response_after.raise_for_status()
    raw_after = response_after.text

    return {
        "repository": repo,
        "commit_before": parent_sha,
        "commit_after": commit_sha,
        "before_file": old_file_path,
        "after_file": new_file_path,
        "before_code": raw_before,
        "after_code": raw_after,
    }


def do_crawl(*, gzipped_commits: str, output_file: str):
    print(
        f"{Fore.YELLOW}{Style.BRIGHT}Checking file (this can take about a minute)...{Style.RESET_ALL}"
    )
    row_count = sum(1 for _ in get_commit_entry(gzip_file=gzipped_commits))
    print(f"There are {row_count} entries in the file!")

    with jsonlines.open(output_file, mode="a") as writer, requests.Session() as session:
        for row_index, row in enumerate(get_commit_entry(gzip_file=gzipped_commits)):

            commit_sha = row["commit"]
            # A Git commit can have multiple parents (e.g. merges).
            # In this case, we select the first commit (this is a wild guess).
            parent_sha = row["parent"][0]

            repo_name = row["repo_name"]
            repo = repo_name[0] if isinstance(repo_name, list) else repo_name

            for file_index, diff in enumerate(row["difference"]):
                try:
                    result = crawl_commit_file(
                        repo=repo,
                        parent_sha=parent_sha,
                        commit_sha=commit_sha,
                        diff=diff,
                        session=session,
                    )
                    if result is not None:
                        print(f"Downloaded {row_index=} / {row_count}, {file_index=}")
                        print(f"    added to {output_file}")
                        writer.write(result)
                except KeyboardInterrupt:
                    raise
                except:
                    print(
                        f"{Fore.RED}{Style.BRIGHT}Failed to download {row_index=}, {repo=}, {commit_sha=}, {file_index=}, {diff=}{Style.RESET_ALL}"
                    )
                    traceback.print_exc()


if __name__ == "__main__":
    file_number = int(input("Enter file number (0-4): "))
    chunk_number = int(input("Enter chunk number (0-2): "))
    do_crawl(
        gzipped_commits=f"mined_commits/mined_commits_2.00000000000{file_number}.chunk{chunk_number}.jsonl.gz",
        output_file=f"output/data{file_number}.chunk{chunk_number}.jsonl",
    )
