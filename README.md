# Codez


## How to extract raw data:

1. Install requirements through requirements-dev.txt

2. [Create a service account for Google Big Query API](https://cloud.google.com/docs/authentication/getting-started)

3. [Create a GitHUb Access Token](https://github.com/settings/tokens)

4. Export variables as such: <br>
    ```export GOOGLE_APPLICATION_CREDENTIALS=<Path to your key file> ``` <br>
    ``` export GITHUB_TOKEN=<Your GitHub Access Token> ```

5. Create a `data` folder in the root directory of this project

6. You are ready to use `extractor.py`


Data preparation code for the AST team project

- `function_extractor.py`: Don't use directly
- `function_pair_extractor.py`: I'm working on it
