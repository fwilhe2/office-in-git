# Flat ODF Git Template

This repository provides a simple setup for working with Flat ODF files in Git while keeping them clean, consistent, and diff-friendly.

It uses a pre-commit hook to automatically normalize `.fods`, `.fodt`, `.fodp` files before they are committed. This avoids noisy diffs and ensures that only meaningful changes appear in version control.

## Why this exists

Flat ODF files are XML. LibreOffice apps tend to introduce a lot of irrelevant changes such as:

* unused styles
* reordered elements
* redundant metadata

These changes make Git diffs hard to read and reviews harder than they should be.

This template ensures that every committed file is cleaned in a consistent way, so that diffs stay small and readable.

## How it works

The repository is configured with the pre-commit framework.

On every commit:

1. Staged `.fods`, `.fodt`, `.fodp` files are detected
2. `scripts/flat-odf-cleanup.py` is run on them
3. If the script modifies any files, the commit is stopped
4. You review the changes and commit again

This guarantees that the committed version is always normalized.

## Setup

Clone the repository and install the hook:

```bash
pip install pre-commit
pre-commit install
```

That is all. The hook will now run automatically on every commit.

## Typical workflow

```bash
git add file.fods
git commit -m "Update spreadsheet"
```

If the cleanup script modifies the file, the commit will stop with a message. Simply run the commit again:

```bash
git commit -m "Update spreadsheet"
```

This second commit will succeed.

## Running manually

To clean all files in the repository:

```bash
pre-commit run --all-files
```

## Project structure

```
samples/
  Sample documents in flat odf format
scripts/
  flat-odf-cleanup.py
.pre-commit-config.yaml
```

* `flat-odf-cleanup.py` performs the normalization
* `.pre-commit-config.yaml` defines when it runs

## Customization

You can adjust the behavior by editing:

* `scripts/flat-odf-cleanup.py` for cleanup logic
* `.pre-commit-config.yaml` for hook configuration

## Notes

* The hook only runs on staged `.fods` files
* The cleanup script must modify files in place
* The double commit is expected behavior and ensures that changes are visible before they are recorded
