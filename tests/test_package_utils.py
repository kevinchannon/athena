"""Tests for package_utils module."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from athena.package_utils import (
    get_init_file_path,
    get_package_manifest,
    is_package,
)


def test_is_package_true():
    """Test that is_package returns True for directories with __init__.py."""
    with TemporaryDirectory() as tmpdir:
        pkg_path = Path(tmpdir) / "my_package"
        pkg_path.mkdir()
        (pkg_path / "__init__.py").touch()

        assert is_package(pkg_path) is True


def test_is_package_false_no_init():
    """Test that is_package returns False for directories without __init__.py."""
    with TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir) / "not_a_package"
        dir_path.mkdir()

        assert is_package(dir_path) is False


def test_is_package_false_file_not_dir():
    """Test that is_package returns False for files."""
    with TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "some_file.py"
        file_path.touch()

        assert is_package(file_path) is False


def test_get_init_file_path():
    """Test that get_init_file_path returns correct path."""
    with TemporaryDirectory() as tmpdir:
        pkg_path = Path(tmpdir) / "my_package"
        pkg_path.mkdir()

        init_path = get_init_file_path(pkg_path)
        assert init_path == pkg_path / "__init__.py"


def test_get_package_manifest_empty_package():
    """Test manifest for empty package (only __init__.py)."""
    with TemporaryDirectory() as tmpdir:
        pkg_path = Path(tmpdir) / "empty_pkg"
        pkg_path.mkdir()
        (pkg_path / "__init__.py").touch()

        manifest = get_package_manifest(pkg_path)
        assert manifest == []


def test_get_package_manifest_files_only():
    """Test manifest for package with only Python files."""
    with TemporaryDirectory() as tmpdir:
        pkg_path = Path(tmpdir) / "pkg"
        pkg_path.mkdir()
        (pkg_path / "__init__.py").touch()
        (pkg_path / "module_a.py").touch()
        (pkg_path / "module_b.py").touch()

        manifest = get_package_manifest(pkg_path)
        # Files should include .py extension
        assert manifest == ["module_a.py", "module_b.py"]


def test_get_package_manifest_subpackages_only():
    """Test manifest for package with only sub-packages."""
    with TemporaryDirectory() as tmpdir:
        pkg_path = Path(tmpdir) / "pkg"
        pkg_path.mkdir()
        (pkg_path / "__init__.py").touch()

        subpkg1 = pkg_path / "subpkg1"
        subpkg1.mkdir()
        (subpkg1 / "__init__.py").touch()

        subpkg2 = pkg_path / "subpkg2"
        subpkg2.mkdir()
        (subpkg2 / "__init__.py").touch()

        manifest = get_package_manifest(pkg_path)
        # Sub-packages don't have extension
        assert manifest == ["subpkg1", "subpkg2"]


def test_get_package_manifest_mixed():
    """Test manifest for package with both files and sub-packages."""
    with TemporaryDirectory() as tmpdir:
        pkg_path = Path(tmpdir) / "pkg"
        pkg_path.mkdir()
        (pkg_path / "__init__.py").touch()
        (pkg_path / "module_a.py").touch()

        subpkg = pkg_path / "subpkg"
        subpkg.mkdir()
        (subpkg / "__init__.py").touch()

        (pkg_path / "module_b.py").touch()

        manifest = get_package_manifest(pkg_path)
        # Mixed: modules with .py, sub-packages without
        assert manifest == ["module_a.py", "module_b.py", "subpkg"]


def test_get_package_manifest_excludes_pycache():
    """Test that __pycache__ directories are excluded from manifest."""
    with TemporaryDirectory() as tmpdir:
        pkg_path = Path(tmpdir) / "pkg"
        pkg_path.mkdir()
        (pkg_path / "__init__.py").touch()
        (pkg_path / "module.py").touch()

        pycache = pkg_path / "__pycache__"
        pycache.mkdir()
        (pycache / "module.cpython-312.pyc").touch()

        manifest = get_package_manifest(pkg_path)
        assert manifest == ["module.py"]
        assert "__pycache__" not in manifest


def test_get_package_manifest_excludes_hidden():
    """Test that hidden files/directories are excluded from manifest."""
    with TemporaryDirectory() as tmpdir:
        pkg_path = Path(tmpdir) / "pkg"
        pkg_path.mkdir()
        (pkg_path / "__init__.py").touch()
        (pkg_path / "module.py").touch()
        (pkg_path / ".hidden_file.py").touch()

        hidden_dir = pkg_path / ".hidden_dir"
        hidden_dir.mkdir()
        (hidden_dir / "__init__.py").touch()

        manifest = get_package_manifest(pkg_path)
        assert manifest == ["module.py"]
        assert ".hidden_file.py" not in manifest
        assert ".hidden_dir" not in manifest


def test_get_package_manifest_deterministic_sorting():
    """Test that manifest is deterministically sorted."""
    with TemporaryDirectory() as tmpdir:
        pkg_path = Path(tmpdir) / "pkg"
        pkg_path.mkdir()
        (pkg_path / "__init__.py").touch()

        # Create files/packages in non-alphabetical order
        (pkg_path / "z_module.py").touch()
        (pkg_path / "a_module.py").touch()

        subpkg_z = pkg_path / "z_pkg"
        subpkg_z.mkdir()
        (subpkg_z / "__init__.py").touch()

        subpkg_a = pkg_path / "a_pkg"
        subpkg_a.mkdir()
        (subpkg_a / "__init__.py").touch()

        manifest = get_package_manifest(pkg_path)
        assert manifest == ["a_module.py", "a_pkg", "z_module.py", "z_pkg"]


def test_get_package_manifest_namespace_package_excluded():
    """Test that namespace packages (dirs without __init__.py) are excluded."""
    with TemporaryDirectory() as tmpdir:
        pkg_path = Path(tmpdir) / "pkg"
        pkg_path.mkdir()
        (pkg_path / "__init__.py").touch()
        (pkg_path / "module.py").touch()

        # Create a namespace package (no __init__.py)
        namespace_pkg = pkg_path / "namespace_pkg"
        namespace_pkg.mkdir()
        (namespace_pkg / "some_module.py").touch()

        manifest = get_package_manifest(pkg_path)
        assert manifest == ["module.py"]
        assert "namespace_pkg" not in manifest


def test_get_package_manifest_non_python_files_excluded():
    """Test that non-Python files are excluded from manifest."""
    with TemporaryDirectory() as tmpdir:
        pkg_path = Path(tmpdir) / "pkg"
        pkg_path.mkdir()
        (pkg_path / "__init__.py").touch()
        (pkg_path / "module.py").touch()
        (pkg_path / "readme.txt").touch()
        (pkg_path / "data.json").touch()
        (pkg_path / "config.yml").touch()

        manifest = get_package_manifest(pkg_path)
        assert manifest == ["module.py"]


def test_get_package_manifest_not_a_directory():
    """Test that get_package_manifest returns empty list for non-directories."""
    with TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "file.py"
        file_path.touch()

        manifest = get_package_manifest(file_path)
        assert manifest == []
