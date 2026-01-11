from pathlib import Path

import pytest

from athena.repository import (
    RepositoryNotFoundError,
    find_python_files,
    find_repository_root,
    get_relative_path,
)


def test_find_repository_root_from_root(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    root = find_repository_root(tmp_path)

    assert root == tmp_path


def test_find_repository_root_from_subdirectory(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    subdir = tmp_path / "src" / "athena"
    subdir.mkdir(parents=True)

    root = find_repository_root(subdir)

    assert root == tmp_path


def test_find_repository_root_from_nested_subdirectory(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    deep_subdir = tmp_path / "a" / "b" / "c" / "d"
    deep_subdir.mkdir(parents=True)

    root = find_repository_root(deep_subdir)

    assert root == tmp_path


def test_find_repository_root_raises_when_no_git_found(tmp_path):
    with pytest.raises(RepositoryNotFoundError) as exc_info:
        find_repository_root(tmp_path)

    assert "No git repository found" in str(exc_info.value)


def test_find_python_files_finds_all_py_files(tmp_path):
    (tmp_path / "file1.py").touch()
    (tmp_path / "file2.py").touch()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module.py").touch()

    files = list(find_python_files(tmp_path))

    assert len(files) == 3
    assert tmp_path / "file1.py" in files
    assert tmp_path / "file2.py" in files
    assert tmp_path / "src" / "module.py" in files


def test_find_python_files_excludes_venv(tmp_path):
    (tmp_path / "included.py").touch()
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "excluded.py").touch()

    files = list(find_python_files(tmp_path))

    assert len(files) == 1
    assert tmp_path / "included.py" in files


def test_find_python_files_excludes_multiple_dirs(tmp_path):
    (tmp_path / "included.py").touch()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.py").touch()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cached.py").touch()
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "output.py").touch()

    files = list(find_python_files(tmp_path))

    assert len(files) == 1
    assert tmp_path / "included.py" in files


def test_get_relative_path_from_root(tmp_path):
    file_path = tmp_path / "file.py"

    relative = get_relative_path(file_path, tmp_path)

    assert relative == "file.py"


def test_get_relative_path_from_subdirectory(tmp_path):
    file_path = tmp_path / "src" / "athena" / "module.py"

    relative = get_relative_path(file_path, tmp_path)

    assert relative == "src/athena/module.py"


def test_get_relative_path_uses_posix_style(tmp_path):
    file_path = tmp_path / "a" / "b" / "c" / "file.py"

    relative = get_relative_path(file_path, tmp_path)

    assert "/" in relative
    assert "\\" not in relative
