from google.cloud import bigquery
import pandas
import requests
import os
from pprint import pprint
import json
import jsonlines
import time

git_token = os.getenv('GITHUB_TOKEN', '...')

# Construct a BigQuery client object.
client = bigquery.Client()

lang_query = """
    SELECT commit, subject, repo_name, ARRAY(
    SELECT AS STRUCT *
    FROM UNNEST(difference)
    WHERE (new_path LIKE "%.py")
    ) AS difference
    FROM `bigquery-public-data.github_repos.commits`
    WHERE EXISTS (
    SELECT new_path FROM UNNEST(difference)
    WHERE (new_path LIKE "%.py")
    )
    AND regexp_contains(subject, 'bug|fix|issue|error')
"""


query_job = client.query(lang_query)  # Make an API request.

print("Querying languages:")
counter = 0

headers = {'Accept': 'application/vnd.github.v3+json', 'Authorization': 'token ' + git_token}

with jsonlines.open('data/data.jsonl', mode='w') as writer:
    for row in query_job:
        commit_sha = row.commit
        
        repo = row.repo_name[0] if (isinstance(row.repo_name, list)) else row.repo_name

        for diff in row.difference:
            
            old_file_path = diff['old_path']
            new_file_path = diff['new_path']

            url_before = "https://api.github.com/repos/%s/contents/%s?ref=%s" % (repo, old_file_path, commit_sha)
            url_after = "https://api.github.com/repos/%s/contents/%s?ref=%s" % (repo, new_file_path, commit_sha + '^')
            
            try:

                response1 = requests.get(url_before, headers=headers)

                download_url_before = json.loads(response1.content.decode())
                download_url_before = download_url_before['download_url']

                response2 = requests.get(url_after, headers=headers)

                download_url_after = json.loads(response2.content.decode())
                download_url_after = download_url_after['download_url']

                response_before = requests.get(download_url_before)
                response_after = requests.get(download_url_after)

                raw_before = response_before.content.decode()
                raw_after = response_after.content.decode()
            except:
                # pprint(download_url_before)
                # pprint(download_url_after)
                
                error = response1.content.decode() 

                if("rate limit" in error.lower()):
                    time.sleep(3600)
                
                continue
            
            writer.write({
                "repository": repo,
                "commit_before": commit_sha + "^",
                "commit_after": commit_sha,
                "before_file": old_file_path,
                "after_file": new_file_path,
                "before_code": raw_before,
                "after_code": raw_after
            })   

            

            

