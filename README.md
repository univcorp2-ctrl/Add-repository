# Add-repository

Create new GitHub repositories automatically from a list of names.

`create_repos.py` takes one or more repository names from the user, infers a
sensible description for each one based on keywords in the name, and creates
the repositories on GitHub via the REST API.

## Setup

1. Create a [GitHub personal access token](https://github.com/settings/tokens)
   with the `repo` scope (or `public_repo` for public-only).
2. Export it before running the script:
   ```bash
   export GITHUB_TOKEN=ghp_your_token_here
   ```

The script uses only the Python standard library — no `pip install` needed.

## Usage

### Interactive mode

```bash
python3 create_repos.py
```

You will be prompted for one repository per line. Press Enter on a blank line
(or Ctrl-D) to start creating them.

### Pass names as arguments

```bash
python3 create_repos.py weather-app my-cli-tool notes-api
```

### Override description or visibility per repo

Each line / argument supports the following forms:

```
my-repo
my-repo: short description here
my-repo (private): short description here
```

### Pipe a list from a file

```bash
cat repos.txt | python3 create_repos.py
```

### Other flags

| Flag         | Effect                                                         |
|--------------|----------------------------------------------------------------|
| `--private`  | Create every repo as private (overridable per line).           |
| `--no-init`  | Do not auto-initialise repos with a README.                    |
| `--dry-run`  | Print what would be created without calling the GitHub API.    |

## How descriptions are inferred

If you don't supply a description, the script looks for common keywords in the
name (`api`, `cli`, `bot`, `web`, `app`, `ml`, `bot`, `dashboard`, `lib`, ...)
and uses them to build a short purpose-aware description, e.g.:

| Repo name        | Generated description                                |
|------------------|------------------------------------------------------|
| `weather-app`    | Weather App - Application.                           |
| `orders-api`     | Orders Api - REST API service.                       |
| `news-scraper`   | News Scraper - Web scraping tool.                    |
| `my-portfolio`   | My Portfolio - Personal portfolio site.              |

If no keyword matches, a generic description is generated from the name.
