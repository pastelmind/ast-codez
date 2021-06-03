# Codez

This repository is the codebase for our project, **Mutation Testing Based on Mining GitHub Commits**.
We are Team 1 of CS453 Automated Software Testing course at KAIST.

## Organization

Our work consists of: Data mining, data preparation, and clustering.

### Data preparation

1. We collected commits from open-source Python projects on GitHub. To do so, we used Google BigQuery to mine the `bigquery-public-data.github_repos` dataset for commits.
   - The mined commits are available under the `/mined_commits/` directory, in the form of gzipped JSON Lines files. These have been split into chunks to facilitate parallel processing.
2. For each commit data, we downloaded the contents of every Python source file affected by the commit, both before and after.
   - We wrote a Scrapy spider (`scrapy_github_files.py`) to perform the task. To run the spider, use `scrapy runspider scrapy_github_files.py`.
   - The spider creates a directory _outside_ the repository at `../github_file_changes/`. It stores the crawled data in a large JSON Lines file named `file_changes_chunk<num>.jsonl`, where `<num>` is the chunk number.

Also check out the original instructions added by our teammate Adil:

> ### How to extract raw data:
>
> 1. Install requirements through requirements-dev.txt
> 2. [Create a service account for Google Big Query API](https://cloud.google.com/docs/authentication/getting-started)
> 3. [Create a GitHUb Access Token](https://github.com/settings/tokens)
> 4. Export variables as such: \
>    `export GOOGLE_APPLICATION_CREDENTIALS=<Path to your key file> ` \
>    `export GITHUB_TOKEN=<Your GitHub Access Token>`
> 5. Create a `data` folder in the root directory of this project
> 6. You are ready to use `extractor.py`

### Preprocessing

For each changed file, we extracted pairs of functions changed by the commit. We used GumTree to derive a series of edit actions to transform the function from the "before" code to the "after" code. We also normalized the functions' source code, so that each function fits in a single line, which is needed for processing with seq2seq.

- This preprocessing is done by `transform_change_entries.py`. It reads file changes stored under `../github_file_changes/`, and saves the preprocessed result to `../dataset/`.
- We used JPype1 to invoke GumTree from Python.

### Training / Clustering

To be added. See the `dat-clustering-trained-model` branch for our work on clustering.
