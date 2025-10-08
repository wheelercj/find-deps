# find-deps

Search all JavaScript or Python dependency lists on your device.

```text
$ find-deps py mypy black
Searched 262 dependency list files
Found 205 unique dependencies
"mypy" found in 5 files:
    /home/chris/Downloads/Python-3.13.1/Tools/requirements-dev.txt
    /home/chris/Downloads/Python-3.12.8/Tools/requirements-dev.txt
    /home/chris/Downloads/Python-3.13.0/Tools/requirements-dev.txt
    /home/chris/.cache/pre-commit/repono13er6s/setup.py
    /home/chris/.cache/pre-commit/repoul88aqli/setup.py
"black" found in 1 files:
    /home/chris/Documents/programming/archive/Python/wrap/requirements-dev.txt
```

Find-deps searches dependency files like `package-lock.json` and `pyproject.toml` by parsing the files and scanning their dependency lists.

## Install

3 ways to install:

- Download or copy [main.py](https://github.com/wheelercj/find-deps/blob/main/main.py) and run it. I've been using Python 3.13, but it might work with Python 3.12 as well.
- `uv tool install git+https://github.com/wheelercj/find-deps@main` and then `find-deps --help`
- `git clone https://github.com/wheelercj/find-deps.git` and then `python3.13 find-deps/main.py --help`

Find-deps has no third-party dependencies.

## Files searched by find-deps

**Python**

- ✅ pyproject.toml
- ✅ [inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/)
- ✅ setup.cfg
- ✅ setup.py
- ✅ uv.lock
- ✅ requirements.txt
- ✅ requirements-dev.txt
- ✅ any pip requirements files referenced in a searched pip requirements file
- ✅ more pip requirements files can be searched by using the `--pip-req` option
- 🚧 poetry.lock
- 🚧 .pre-commit-config.yaml
- 🚧 ...and many others

**JavaScript**

- ✅ package.json
- ✅ package-lock.json
- ✅ npm-shrinkwrap.json
- ✅ deno.json
- ✅ deno.jsonc
- 🚧 deno.lock
- 🚧 yarn.lock
- 🚧 pnpm-lock.yaml
- 🚧 bun.lock
- 🚧 hidden lockfiles
- 🚧 ...and many others
