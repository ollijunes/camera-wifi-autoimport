# T1 README: move the blog post link to the top; keep ledger tooling out of language stats

- Status: done
- Lane: docs/blog-link-language-20261020
- Evidence: `python3 scripts/check_public_tree.py` → 16 canaries passed, 0 findings; both blog URLs return 200; the story line appears once in README.md. Language change shows on GitHub after merge.

## Plan

Goal: people who land on the repository see the project story first, and GitHub shows the project as Python.

- Move the existing "Read the project story" line (English and Finnish blog posts) from below the introduction to directly under the badges.
- Mark `ledger/**` as `linguist-vendored` in .gitattributes. The ledger tooling (`ledger/scripts/records.mjs`, ~380 KB of JavaScript) currently makes GitHub report the repository as JavaScript, although the importer is Python.

Checks: both URLs return 200; the README line appears once; `python3 scripts/check_public_tree.py` passes; after merge the repository language shows Python.
