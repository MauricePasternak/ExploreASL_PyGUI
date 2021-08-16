import re
import os
from pathlib import Path
from typing import Union
from more_itertools import peekable


def pathcheck_aspath(path: Union[str, Path]) -> Union[Path, None]:
    if not isinstance(path, (str, Path)):
        return None
    path = Path(path) if isinstance(path, str) else path
    if path.exists():
        return path
    return None


def pathcheck_valid_file(path: Path) -> bool:
    if not path:
        return False
    return all([path.exists(), path.is_file()])


def pathcheck_valid_dir(path: Path) -> bool:
    if not path:
        return False
    return all([path.exists(), path.is_dir()])


def pathcheck_filechild_exists(parent_path: Path, child_basename: str) -> bool:
    if not parent_path:
        return False
    return all([parent_path.exists(),
                (parent_path / child_basename).exists(),
                (parent_path / child_basename).is_file()
                ])


def pathcheck_dirchild_exists(parent_path: Path, child_basename: str) -> bool:
    if not parent_path:
        return False
    return all([parent_path.exists(),
                (parent_path / child_basename).exists(),
                (parent_path / child_basename).is_dir()
                ])


def pathcheck_basename_equals(path: Path, basename: str) -> bool:
    if not path:
        return False
    return path.name == basename


def pathcheck_basename_regex(path: Path, regex_str: Union[str, re.Pattern]) -> bool:
    if not path:
        return False
    pattern = re.compile(regex_str) if isinstance(regex_str, str) else regex_str
    return bool(pattern.search(path.name))


def pathcheck_self_fits_regex(path: Path, regex_str: Union[str, re.Pattern]) -> bool:
    if not path:
        return False
    pattern = re.compile(regex_str) if isinstance(regex_str, str) else regex_str
    return bool(pattern.search(str(path)))


def pathcheck_child_fits_regex(parent_path: Path, regex_str: Union[str, re.Pattern]) -> bool:
    if not parent_path:
        return False
    pattern = re.compile(regex_str) if isinstance(regex_str, str) else regex_str
    return any([pattern.search(str(path.name)) for path in parent_path.iterdir()])


def pathcheck_childfile_fits_regex(parent_path: Path, regex_str: Union[str, re.Pattern]) -> bool:
    if not parent_path:
        return False
    pattern = re.compile(regex_str) if isinstance(regex_str, str) else regex_str
    return any([pattern.search(str(path.name)) for path in parent_path.iterdir() if path.is_file()])


def pathcheck_childdir_fits_regex(parent_path: Path, regex_str: Union[str, re.Pattern]) -> bool:
    if not parent_path:
        return False
    pattern = re.compile(regex_str) if isinstance(regex_str, str) else regex_str
    return any([pattern.search(str(path.name)) for path in parent_path.iterdir() if path.is_dir()])


def pathcheck_contains_glob(path: Path, glob_pat: Union[str, list, tuple]) -> bool:
    if not path:
        return False
    if isinstance(glob_pat, (list, tuple)):
        glob_pat = os.sep.join(glob_pat)
    if peekable(path.glob(glob_pat)):
        return True
    return False


def pathcheck_contains_rglob(path: Path, glob_pat: Union[str, list, tuple]) -> bool:
    if not path:
        return False
    if isinstance(glob_pat, (list, tuple)):
        glob_pat = os.sep.join(glob_pat)
    if peekable(path.rglob(glob_pat)):
        return True
    return False


def pathcheck_dispatch(action: str, *args, **kwargs) -> bool:
    dispatch = {
        "filechild_exists": pathcheck_filechild_exists,
        "dirchild_exists": pathcheck_dirchild_exists,
        "basename_equals": pathcheck_basename_equals,
        "basename_regex": pathcheck_basename_regex,
        "child_fits_regex": pathcheck_child_fits_regex,
        "childfile_fits_regex": pathcheck_childfile_fits_regex,
        "childdir_fits_regex": pathcheck_childdir_fits_regex,
        "self_fits_regex": pathcheck_self_fits_regex,
        "contains": pathcheck_contains_glob,
        "rcontains": pathcheck_contains_rglob
    }
    return dispatch[action.lower()](*args, **kwargs)
