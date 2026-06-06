"""Tests for CopyFile task in Prefecture."""

import pathlib

from prefecture.operations import copyfile
import pytest


def test_copy_file_relative_paths(tmp_path):
    """Test CopyFile with both paths relative to run_dir."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    # Create source file in run_dir
    src_file = run_dir / "source.txt"
    with open(src_file, "w") as f:
        f.write("test content")

    task = copyfile.CopyFile(
        config_dir=config_dir,
        from_path="source.txt",
        to_path="dest.txt",
    )
    task(run_dir=run_dir)

    dest_file = run_dir / "dest.txt"
    assert dest_file.exists()
    with open(dest_file, "r") as f:
        assert f.read() == "test content"


def test_copy_file_absolute_paths(tmp_path):
    """Test CopyFile with absolute paths."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    # Create source file outside run_dir
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    src_file = external_dir / "source.txt"
    with open(src_file, "w") as f:
        f.write("absolute content")

    dest_file = external_dir / "dest.txt"

    task = copyfile.CopyFile(
        config_dir=config_dir,
        from_path=str(src_file),
        to_path=str(dest_file),
    )
    task(run_dir=run_dir)

    assert dest_file.exists()
    with open(dest_file, "r") as f:
        assert f.read() == "absolute content"


def test_copy_file_mixed_paths(tmp_path):
    """Test CopyFile with one relative and one absolute path."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    # Create source file in run_dir (relative)
    src_file = run_dir / "source.txt"
    with open(src_file, "w") as f:
        f.write("mixed content")

    # Dest file absolute
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    dest_file = external_dir / "dest.txt"

    task = copyfile.CopyFile(
        config_dir=config_dir,
        from_path="source.txt",
        to_path=str(dest_file),
    )
    task(run_dir=run_dir)

    assert dest_file.exists()
    with open(dest_file, "r") as f:
        assert f.read() == "mixed content"


def test_copy_file_creates_dest_directory(tmp_path):
    """Test CopyFile creates destination directory if it doesn't exist."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    src_file = run_dir / "source.txt"
    with open(src_file, "w") as f:
        f.write("nested content")

    # Dest file in nested relative directory
    task = copyfile.CopyFile(
        config_dir=config_dir,
        from_path="source.txt",
        to_path="nested/dir/dest.txt",
    )
    task(run_dir=run_dir)

    dest_file = run_dir / "nested" / "dir" / "dest.txt"
    assert dest_file.exists()
    with open(dest_file, "r") as f:
        assert f.read() == "nested content"
