"""Tests for cache database error handling."""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from athena.cache import CacheDatabase, CachedEntity


@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for cache testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def cache_db(temp_cache_dir):
    """Create a cache database instance for testing."""
    db = CacheDatabase(temp_cache_dir)
    yield db
    db.close()


def test_database_open_failure(temp_cache_dir):
    """Test that database open failures are handled gracefully."""
    # Create a file where the database should be to cause a failure
    db_path = temp_cache_dir / "docstring_cache.db"
    temp_cache_dir.mkdir(parents=True, exist_ok=True)

    # Make the cache dir read-only to trigger permission error
    with patch("sqlite3.connect", side_effect=sqlite3.Error("Permission denied")):
        with pytest.raises(sqlite3.Error, match="Permission denied"):
            CacheDatabase(temp_cache_dir)


def test_insert_file_database_error(cache_db):
    """Test that insert_file handles database errors."""
    # Replace connection with a mock that raises errors
    original_conn = cache_db.conn
    mock_conn = Mock()
    mock_conn.execute.side_effect = sqlite3.Error("DB locked")
    mock_conn.rollback = Mock()
    cache_db.conn = mock_conn

    try:
        with pytest.raises(sqlite3.Error, match="DB locked"):
            cache_db.insert_file("test.py", 1234567890.0)
        # Verify rollback was called
        mock_conn.rollback.assert_called_once()
    finally:
        cache_db.conn = original_conn


def test_get_file_database_error(cache_db):
    """Test that get_file handles database errors."""
    # Replace connection with a mock that raises errors
    original_conn = cache_db.conn
    mock_conn = Mock()
    mock_conn.execute.side_effect = sqlite3.Error("DB corrupted")
    cache_db.conn = mock_conn

    try:
        with pytest.raises(sqlite3.Error, match="DB corrupted"):
            cache_db.get_file("test.py")
    finally:
        cache_db.conn = original_conn


def test_update_file_mtime_database_error(cache_db):
    """Test that update_file_mtime handles database errors."""
    # First insert a file successfully
    file_id = cache_db.insert_file("test.py", 1234567890.0)

    # Then cause an error on update
    original_conn = cache_db.conn
    mock_conn = Mock()
    mock_conn.execute.side_effect = sqlite3.Error("Constraint violation")
    mock_conn.rollback = Mock()
    cache_db.conn = mock_conn

    try:
        with pytest.raises(sqlite3.Error, match="Constraint violation"):
            cache_db.update_file_mtime(file_id, 1234567900.0)
        # Verify rollback was called
        mock_conn.rollback.assert_called_once()
    finally:
        cache_db.conn = original_conn


def test_delete_files_not_in_database_error(cache_db):
    """Test that delete_files_not_in handles database errors."""
    # Insert some files first
    cache_db.insert_file("file1.py", 123.0)
    cache_db.insert_file("file2.py", 456.0)

    # Cause an error during delete
    original_conn = cache_db.conn
    mock_conn = Mock()
    mock_conn.execute.side_effect = sqlite3.Error("Delete failed")
    mock_conn.rollback = Mock()
    cache_db.conn = mock_conn

    try:
        with pytest.raises(sqlite3.Error, match="Delete failed"):
            cache_db.delete_files_not_in(["file1.py"])
        # Verify rollback was called
        mock_conn.rollback.assert_called_once()
    finally:
        cache_db.conn = original_conn


def test_insert_entities_database_error(cache_db):
    """Test that insert_entities handles database errors."""
    file_id = cache_db.insert_file("test.py", 123.0)

    entities = [
        CachedEntity(
            file_id=file_id,
            kind="function",
            name="test_func",
            entity_path="test.py",
            start=1,
            end=5,
            summary="Test function"
        )
    ]

    # Replace connection with a mock that raises errors
    original_conn = cache_db.conn
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_cursor.lastrowid = 1  # Return a valid ID for entity insertion
    mock_cursor.executemany.side_effect = sqlite3.Error("Insert failed")
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.rollback = Mock()
    cache_db.conn = mock_conn

    try:
        with pytest.raises(sqlite3.Error, match="Insert failed"):
            cache_db.insert_entities(file_id, entities)
        # Verify rollback was called
        mock_conn.rollback.assert_called_once()
    finally:
        cache_db.conn = original_conn


def test_delete_entities_for_file_database_error(cache_db):
    """Test that delete_entities_for_file handles database errors."""
    file_id = cache_db.insert_file("test.py", 123.0)

    entities = [
        CachedEntity(
            file_id=file_id,
            kind="function",
            name="test_func",
            entity_path="test.py",
            start=1,
            end=5,
            summary="Test function"
        )
    ]
    cache_db.insert_entities(file_id, entities)

    # Replace connection with a mock that raises errors
    original_conn = cache_db.conn
    mock_conn = Mock()
    mock_conn.execute.side_effect = sqlite3.Error("Delete failed")
    mock_conn.rollback = Mock()
    cache_db.conn = mock_conn

    try:
        with pytest.raises(sqlite3.Error, match="Delete failed"):
            cache_db.delete_entities_for_file(file_id)
        # Verify rollback was called
        mock_conn.rollback.assert_called_once()
    finally:
        cache_db.conn = original_conn


def test_get_all_entities_database_error(cache_db):
    """Test that get_all_entities handles database errors."""
    # Replace connection with a mock that raises errors
    original_conn = cache_db.conn
    mock_conn = Mock()
    mock_conn.execute.side_effect = sqlite3.Error("Query failed")
    cache_db.conn = mock_conn

    try:
        with pytest.raises(sqlite3.Error, match="Query failed"):
            cache_db.get_all_entities()
    finally:
        cache_db.conn = original_conn


def test_database_connection_not_initialized():
    """Test that operations fail gracefully when connection is not initialized."""
    cache_db = CacheDatabase.__new__(CacheDatabase)
    cache_db.conn = None

    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        cache_db.insert_file("test.py", 123.0)

    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        cache_db.get_file("test.py")

    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        cache_db.update_file_mtime(1, 123.0)

    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        cache_db.delete_files_not_in(["test.py"])

    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        cache_db.insert_entities(1, [])

    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        cache_db.delete_entities_for_file(1)

    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        cache_db.get_all_entities()


def test_transaction_rollback_on_error(cache_db):
    """Test that transactions are rolled back on error."""
    # Insert a file successfully
    file_id = cache_db.insert_file("test.py", 123.0)

    # Try to insert entities with an error
    entities = [
        CachedEntity(
            file_id=file_id,
            kind="function",
            name="test_func",
            entity_path="test.py",
            start=1,
            end=5,
            summary="Test function"
        )
    ]

    # Replace connection with a mock that raises errors
    original_conn = cache_db.conn
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_cursor.lastrowid = 1  # Return a valid ID for entity insertion
    mock_cursor.executemany.side_effect = sqlite3.Error("Insert failed")
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.rollback = Mock()
    cache_db.conn = mock_conn

    try:
        with pytest.raises(sqlite3.Error):
            cache_db.insert_entities(file_id, entities)
        # Verify rollback was called
        mock_conn.rollback.assert_called_once()
    finally:
        cache_db.conn = original_conn

    # Verify no entities were inserted (transaction was rolled back)
    cursor = original_conn.execute("SELECT COUNT(*) FROM entities WHERE file_id = ?", (file_id,))
    count = cursor.fetchone()[0]
    assert count == 0


def test_database_timeout_configuration(temp_cache_dir):
    """Test that database timeout is configured correctly."""
    # Verify that sqlite3.connect is called with timeout parameter
    with patch("athena.cache.sqlite3.connect") as mock_connect:
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        db = CacheDatabase(temp_cache_dir)

        # Verify connect was called with timeout
        mock_connect.assert_called_once()
        call_kwargs = mock_connect.call_args.kwargs
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == 10.0
