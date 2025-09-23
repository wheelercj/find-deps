# Copyright 2025 Chris Wheeler
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import configparser
import json
import re
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any
from typing import Literal


# https://chriswheeler.dev/posts/how-to-use-colors-in-terminals/
color_reset: str = "\x1b[0m"
yellow: str = "\x1b[33m"
red: str = "\x1b[31m"

# https://packaging.python.org/en/latest/specifications/dependency-specifiers/#grammar
py_dep_spec_pattern: re.Pattern = re.compile(
    r"^\s*(?P<name>[a-zA-Z0-9](?:[a-zA-Z0-9._-]*[a-zA-Z0-9])?)\b\s*(?P<extras>\[[^\[\]]*\])?\s*(?:@.+|(?P<versionspec>[\(<>=!~][^;]*)?).*"
)
pip_file_ref_pattern: re.Pattern = re.compile(r"^-r (\S+\.txt)$")

Language = Literal[
    "py",
    "js",
]
language_choices: list[Language] = [
    "py",
    "js",
]

type NestedStrDict = dict[str, str | NestedStrDict]  # requires Python 3.12 or newer


def main():
    parser = argparse.ArgumentParser(
        prog="find-deps",
        description="Search all JavaScript or Python dependency lists on your device",
        epilog="For more info, visit https://github.com/wheelercj/find-deps",
    )
    parser.add_argument("language", choices=language_choices)
    parser.add_argument("deps", action="extend", nargs="+", type=str)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--no-ansi", action="store_true", help="omit ANSI escape codes")
    parser.add_argument(
        "--exclude",
        action="append",
        default=["Trash"],
        help="name of a file or folder to ignore; this option may be used multiple times",
    )
    parser.add_argument(
        "--pip-req",
        action="append",
        default=["requirements.txt", "requirements-dev.txt"],
        help="name of a pip requirements file to search for; this option may be used multiple times",
    )

    args = parser.parse_args()
    language: Language = args.language
    deps: set[str] = set(args.deps)
    verbose: bool = args.verbose
    no_ansi: bool = args.no_ansi
    excludes: list[str] = args.exclude
    pip_req_file_names: list[str] = [x.lower() for x in args.pip_req]

    if no_ansi:
        global color_reset
        color_reset = ""
        global yellow
        yellow = ""
        global red
        red = ""

    dep_file_names: list[str] = []
    match language:
        case "py":
            if "pyproject.toml" not in excludes:
                dep_file_names.append("pyproject.toml")
            if "setup.cfg" not in excludes:
                dep_file_names.append("setup.cfg")
            if "setup.py" not in excludes:
                dep_file_names.append("setup.py")
            for file_name in pip_req_file_names:
                if file_name not in excludes:
                    dep_file_names.append(file_name)
        case "js":
            if "package.json" not in excludes:
                dep_file_names.append("package.json")
            if "package-lock.json" not in excludes:
                dep_file_names.append("package-lock.json")
            if "npm-shrinkwrap.json" not in excludes:
                dep_file_names.append("npm-shrinkwrap.json")
        case _:
            raise ValueError("outdated match")

    deps_map: defaultdict[str, list[Path]] = defaultdict(list)  # dep name -> dep file paths
    for dirpath, dirnames, filenames in Path.home().walk():
        if dirpath.name in excludes:
            dirnames.clear()
            continue

        for dep_file_name in dep_file_names:
            if dep_file_name in filenames:
                dep_file_path: Path = dirpath / dep_file_name

                match dep_file_name.lower():
                    case "pyproject.toml":
                        if verbose:
                            print(f"Searching {dep_file_path}")
                        pyp_deps: set[str] = get_pyproject_deps(dep_file_path, verbose)
                        matches: set[str] = deps.intersection(pyp_deps)
                        for match in matches:
                            deps_map[match].append(dep_file_path)
                    case "setup.cfg":
                        if verbose:
                            print(f"Searching {dep_file_path}")
                        setup_cfg_deps: set[str] = get_py_setup_cfg_deps(dep_file_path, verbose)
                        matches: set[str] = deps.intersection(setup_cfg_deps)
                        for match in matches:
                            deps_map[match].append(dep_file_path)
                    case "setup.py":
                        if verbose:
                            print(f"Searching {dep_file_path}")
                        setup_py_deps: set[str] = get_setup_py_deps(dep_file_path)
                        matches: set[str] = deps.intersection(setup_py_deps)
                        for match in matches:
                            deps_map[match].append(dep_file_path)
                    case x if x in pip_req_file_names:
                        if verbose:
                            print(f"Searching {dep_file_path}")
                        req_deps: defaultdict[str, list[Path]] = get_pip_req_deps(
                            dep_file_path, verbose, excludes, pip_req_file_names
                        )
                        matches: set[str] = deps.intersection(req_deps.keys())
                        for match in matches:
                            deps_map[match].extend(req_deps[match])
                    case "package.json":
                        if verbose:
                            print(f"Searching {dep_file_path}")
                        pkg_deps: set[str] = get_js_package_json_deps(dep_file_path, verbose)
                        matches: set[str] = deps.intersection(pkg_deps)
                        for match in matches:
                            deps_map[match].append(dep_file_path)
                    case "package-lock.json" | "npm-shrinkwrap.json":
                        if verbose:
                            print(f"Searching {dep_file_path}")
                        pl_deps: set[str] = get_js_package_lock_deps(dep_file_path)
                        matches: set[str] = deps.intersection(pl_deps)
                        for match in matches:
                            deps_map[match].append(dep_file_path)
                    case _:
                        if verbose:
                            print(f"Naively searching {dep_file_path}")
                        matches: set[str] = file_naively_contains(dep_file_path, deps)
                        for match in matches:
                            deps_map[match].append(dep_file_path)

    for dep_name, dep_file_paths in deps_map.items():
        print(f'"{dep_name}" found in {len(dep_file_paths)} files:')
        for p in dep_file_paths:
            print(f"    {p}")


def file_naively_contains(file_path: Path, deps: set[str]) -> set[str]:
    """Returns all naive matches present in the chosen file"""
    try:
        contents: str = file_path.read_text(encoding="utf8", errors="ignore")
    except Exception as err:
        print(f'{red}"{type(err).__name__}: {err}" when reading {file_path}{color_reset}')
        return set()

    return set(dep for dep in deps if dep in contents)


def get_pyproject_deps(pyproject_path: Path, verbose: bool) -> set[str]:
    """Gets the names of all dependencies listed in a pyproject.toml"""
    # https://packaging.python.org/en/latest/specifications/pyproject-toml
    deps: set[str] = set()

    try:
        pyproject: dict[str, Any] = tomllib.loads(
            pyproject_path.read_text(encoding="utf8", errors="ignore")
        )
    except Exception as err:
        print(f'{red}"{type(err).__name__}: {err}" when reading {pyproject_path}{color_reset}')
        return set()

    if "project" in pyproject:
        project: dict[str, Any] = pyproject["project"]
        if "dependencies" in project:
            proj_deps: list[str | dict] = project["dependencies"]
            deps.update(get_py_dep_names(proj_deps, verbose))
        if "optional-dependencies" in project:
            opt_deps: dict[str, list[str | dict]] = project["optional-dependencies"]
            for dg in opt_deps.values():
                deps.update(get_py_dep_names(dg, verbose))
    if "dependency-groups" in pyproject:
        dep_groups: dict[str, list[str | dict]] = pyproject["dependency-groups"]
        # https://packaging.python.org/en/latest/specifications/dependency-groups/
        for dg in dep_groups.values():
            deps.update(get_py_dep_names(dg, verbose))
    if "build-system" in pyproject:
        build_sys: dict[str, Any] = pyproject["build-system"]
        if "requires" in build_sys:
            requires: list[str | dict] = build_sys["requires"]
            deps.update(get_py_dep_names(requires, verbose))

    return deps


def get_py_setup_cfg_deps(setup_cfg_path: Path, verbose: bool) -> set[str]:
    """Gets the names of all dependencies listed in a Python setup.cfg"""
    # https://setuptools.pypa.io/en/latest/userguide/declarative_config.html
    try:
        contents: str = setup_cfg_path.read_text(encoding="utf8", errors="ignore")
    except Exception as err:
        print(f'{red}"{type(err).__name__}: {err}" when reading {setup_cfg_path}{color_reset}')
        return set()
    if not contents:
        return set()

    config = configparser.ConfigParser()
    try:
        config.read_string(contents)
    except Exception as err:
        print(f'{red}"{type(err).__name__}: {err}" when loading {setup_cfg_path}{color_reset}')
        return set()

    if "options" not in config:
        return set()
    if "install_requires" not in config["options"]:
        return set()

    reqs_s: str = config["options"]["install_requires"]
    assert isinstance(reqs_s, str), f"Unexpected {type(reqs_s).__name__}"
    reqs: list[str] = reqs_s.splitlines()

    deps: set[str] = get_py_dep_names(reqs, verbose)
    return deps


def get_setup_py_deps(setup_py_path: Path) -> set[str]:
    """Attempts to get the names of all dependencies listed in a setup.py

    This function only succeeds if install_requires in setup.py is defined with a literal list with
    literal strings that are not f-strings. Otherwise, the returned set may be empty or may be
    missing some dependencies. A warning is printed in those cases.
    """
    try:
        contents: str = setup_py_path.read_text(encoding="utf8", errors="ignore").strip()
    except Exception as err:
        print(f'{red}"{type(err).__name__}: {err}" when reading {setup_py_path}{color_reset}')
        return set()
    if not contents:
        return set()

    try:
        i: int = contents.index("install_requires")
    except ValueError:
        return set()

    i += len("install_requires")

    while i < len(contents) and contents[i] != "=":
        i += 1
    i += 1
    while i < len(contents) and contents[i] in (" ", "\t", "\n", "\r"):
        i += 1
    if contents[i] != "[":
        # it's not a literal list
        print(
            f"{yellow}Warning: unable to parse the dependency list in {setup_py_path}{color_reset}"
        )
        return set()
    # there's still a chance the contents of the list are not literal values
    dep_list_start: int = i
    i += 1

    in_extras: bool = False
    while i < len(contents):
        if contents[i] == "[":
            in_extras = True
        elif contents[i] == "]":
            if in_extras:
                in_extras = False
            else:
                break
        i += 1
    dep_list_end: int = i
    if contents[dep_list_end] != "]":
        return set()

    deps: list[str] = []
    missed_deps: bool = False
    i = dep_list_start + 1
    while i < dep_list_end:
        in_comment: bool = False
        while i < dep_list_end and contents[i] not in ("'", '"'):
            if in_comment:
                if contents[i] == "\n":
                    in_comment = False
            else:
                if contents[i] == "#":
                    in_comment = True
                elif contents[i] not in (" ", "\t", "\n", "\r", ","):
                    missed_deps = True
            i += 1
        if contents[i] not in ("'", '"'):
            return set()
        str_start: int = i
        i += 1
        quote: str = contents[str_start]

        escaped: bool = False
        while i < dep_list_end:
            if contents[i] == "\\":
                escaped = not escaped
            elif contents[i] == quote:
                if escaped:
                    escaped = False
                else:
                    break
            else:
                escaped = False
            i += 1
        str_end: int = i
        i += 1

        dep_spec: str = contents[str_start + 1 : str_end]
        match: re.Match | None = py_dep_spec_pattern.match(dep_spec)
        if match:
            deps.append(match["name"])
        else:
            missed_deps = True

    if missed_deps:
        print(
            f"{yellow}Warning: could not fully parse the dependency list in"
            f" {setup_py_path}{color_reset}"
        )

    return set(deps)


def get_pip_req_deps(
    dep_file_path: Path, verbose: bool, excludes: list[str], pip_req_file_names: list[str]
) -> defaultdict[str, list[Path]]:
    """Gets the names of all dependencies listed in a pip requirements.txt & others it references"""
    # https://pip.pypa.io/en/stable/reference/requirements-file-format/
    deps_map: defaultdict[str, list[Path]] = defaultdict(list)  # dep name -> dep file paths

    try:
        req_lines: list[str] = dep_file_path.read_text(
            encoding="utf8", errors="ignore"
        ).splitlines()
    except Exception as err:
        print(f'{red}"{type(err).__name__}: {err}" when reading {dep_file_path}{color_reset}')
        return defaultdict()

    for line in req_lines:
        dep_spec_match: re.Match | None = py_dep_spec_pattern.match(line.strip())
        if dep_spec_match:
            dep_name: str = dep_spec_match["name"]
            deps_map[dep_name].append(dep_file_path)
        else:
            ref_match: re.Match | None = pip_file_ref_pattern.match(line.strip())
            if ref_match:
                reffed_req_name: str = ref_match[1]
                if reffed_req_name in pip_req_file_names:
                    if verbose:
                        print(
                            f"{reffed_req_name} referenced but skipped this time because it's"
                            " already in the list of file names to search"
                        )
                elif reffed_req_name in excludes:
                    if verbose:
                        print(
                            f"{reffed_req_name} referenced but skipped because it's in the"
                            " excludes list"
                        )
                elif len(Path(reffed_req_name).parts) > 1:
                    print(
                        f"{red}Error: unexpected directory separator in pip requirements file"
                        f" reference in {dep_file_path}{color_reset}"
                    )
                else:
                    reffed_req_path: Path = dep_file_path.parent / reffed_req_name
                    if verbose:
                        print(
                            f"{reffed_req_name} referenced in {dep_file_path}\n"
                            f"    Searching {reffed_req_path}"
                        )
                    deps_map.update(
                        get_pip_req_deps(reffed_req_path, verbose, excludes, pip_req_file_names)
                    )

    return deps_map


def get_py_dep_names(dep_spec_list: list[str] | list[str | dict], verbose: bool) -> set[str]:
    """Gets dependency names from a Python dependency specifiers list"""
    deps: set[str] = set()

    for dep_spec in dep_spec_list:
        if isinstance(dep_spec, dict):
            # Dictionaries in a dep spec list are dep group includes, not deps, so ignore them.
            # https://packaging.python.org/en/latest/specifications/dependency-groups/#dependency-group-include
            continue
        if not isinstance(dep_spec, str):
            if verbose:
                print(
                    f"{yellow}Warning: unexpected {type(dep_spec).__name__} in dependency"
                    f" list{color_reset}"
                )
            continue
        if not dep_spec.strip():
            continue

        spec_match: re.Match | None = py_dep_spec_pattern.match(dep_spec)
        assert spec_match, f'"{dep_spec}" did not match the dependency specification pattern'
        deps.add(spec_match["name"])

        # if spec_match["extras"]:
        #     extras_s: str = str(spec_match["extras"]).strip("[]").strip()
        #     if extras_s:
        #         extras: list[str] = [e.strip() for e in extras_s.split(",")]
        #         print(f"{extras = }")

        # if spec_match["versionspec"]:
        #     versions_s: str = str(spec_match["versionspec"]).strip("()").strip()
        #     versions: list[str] = versions_s.split(",")
        #     print(f"{versions = }")

    return deps


def get_js_package_json_deps(file_path: Path, verbose: bool) -> set[str]:
    """Gets the names of all dependencies listed in a package.json"""
    try:
        text: str = file_path.read_text(encoding="utf8", errors="ignore").strip()
    except Exception as err:
        print(f'{red}"{type(err).__name__}: {err}" when reading {file_path}{color_reset}')
        return set()
    if not text:
        return set()

    try:
        pkg: dict[str, Any] = json.loads(text)
    except Exception as err:
        if verbose:
            print(f'{red}"{type(err).__name__}: {err}" when loading {file_path}{color_reset}')
        return set()
    else:
        if pkg:
            pkg_deps: set[str] = get_js_package_deps(pkg)
            return pkg_deps
        else:
            return set()


def get_js_package_lock_deps(package_lock_file_path: Path) -> set[str]:
    """Gets the names of all dependencies listed in a package-lock.json"""
    # https://docs.npmjs.com/cli/v10/configuring-npm/package-lock-json#dependencies
    deps: set[str] = set()

    try:
        contents: str = package_lock_file_path.read_text(encoding="utf8", errors="ignore")
    except Exception as err:
        print(
            f'{red}"{type(err).__name__}: {err}" when reading'
            f" {package_lock_file_path}{color_reset}"
        )
        return set()
    if not contents:
        return set()

    try:
        pkg_lock: dict[str, Any] = json.loads(contents)
    except Exception as err:
        print(
            f'{red}"{type(err).__name__}: {err}" when loading'
            f" {package_lock_file_path}{color_reset}"
        )
        return set()

    if "packages" in pkg_lock:
        pkgs: dict[str, Any] = pkg_lock["packages"]
        for pkg in pkgs.values():
            deps.update(get_js_package_deps(pkg))

    return deps


def get_js_package_deps(pkg: dict[str, Any]) -> set[str]:
    """Gets the names of all dependencies in a JS package specification"""
    # https://docs.npmjs.com/cli/v11/configuring-npm/package-json#dependencies
    deps: set[str] = set()

    deps.update(get_js_nested_deps(pkg))
    if "devDependencies" in pkg:
        dev_deps: dict[str, str] = pkg["devDependencies"]
        deps.update(dev_deps.keys())
    if "peerDependencies" in pkg:
        peer_deps: dict[str, str] = pkg["peerDependencies"]
        deps.update(peer_deps.keys())
    if "bundleDependencies" in pkg:
        bundle_deps: list[str] = pkg["bundleDependencies"]
        deps.update(bundle_deps)
    if "bundledDependencies" in pkg:
        bundled_deps: list[str] = pkg["bundledDependencies"]
        deps.update(bundled_deps)
    if "optionalDependencies" in pkg:
        optional_deps: dict[str, str] = pkg["optionalDependencies"]
        deps.update(optional_deps.keys())
    if "overrides" in pkg:
        overrides: NestedStrDict = pkg["overrides"]
        deps.update(get_js_override_names(overrides))

    return deps


def get_js_nested_deps(pkg) -> set[str]:
    """Gets the names of all packages in a JS package's dependencies object"""
    if "dependencies" not in pkg:
        return set()

    deps: set[str] = set()

    pkg_deps: dict[str, Any] = pkg["dependencies"]
    deps.update(pkg_deps.keys())
    for pkg_dep in pkg_deps.values():
        deps.update(get_js_nested_deps(pkg_dep))

    return deps


def get_js_override_names(pkg_overrides: NestedStrDict) -> set[str]:
    """Gets the names of all packages in a JS package's overrides object"""
    overrides: set[str] = set()

    overrides.update(pkg_overrides.keys())

    for v in pkg_overrides.values():
        if isinstance(v, dict):
            overrides.update(get_js_override_names(v))

    return overrides


if __name__ == "__main__":
    main()
