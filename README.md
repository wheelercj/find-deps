# find-deps

Search all JavaScript or Python dependency lists on your device.

```text
$ find-deps py mypy black
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
