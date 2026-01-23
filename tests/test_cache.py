"""Tests for the SQLite cache database."""

import tempfile
from pathlib import Path

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


def test_database_creation(temp_cache_dir):
    """Test that database and schema are created correctly."""
    db = CacheDatabase(temp_cache_dir)

    # Verify database file exists
    assert (temp_cache_dir / "docstring_cache.db").exists()

    # Verify tables exist
    cursor = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    assert "files" in tables
    assert "entities" in tables

    db.close()


def test_wal_mode_enabled(cache_db):
    """Test that WAL mode is enabled for concurrency."""
    cursor = cache_db.conn.execute("PRAGMA journal_mode")
    mode = cursor.fetchone()[0]
    assert mode.upper() == "WAL"


def test_foreign_keys_enabled(cache_db):
    """Test that foreign key constraints are enabled."""
    cursor = cache_db.conn.execute("PRAGMA foreign_keys")
    enabled = cursor.fetchone()[0]
    assert enabled == 1


def test_file_insertion(cache_db):
    """Test inserting a file record."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    assert file_id is not None
    assert file_id > 0

    # Verify insertion
    result = cache_db.get_file("src/example.py")
    assert result is not None
    assert result[0] == file_id
    assert result[1] == 1234567890.0


def test_file_lookup_nonexistent(cache_db):
    """Test looking up a file that doesn't exist."""
    result = cache_db.get_file("nonexistent.py")
    assert result is None


def test_duplicate_file_insertion(cache_db):
    """Test that duplicate file paths raise an error."""
    cache_db.insert_file("src/example.py", 1234567890.0)

    # Attempting to insert same path should fail
    with pytest.raises(Exception):  # sqlite3.IntegrityError
        cache_db.insert_file("src/example.py", 9999999999.0)


def test_file_mtime_update(cache_db):
    """Test updating file modification time."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    # Update mtime
    cache_db.update_file_mtime(file_id, 9876543210.0)

    # Verify update
    result = cache_db.get_file("src/example.py")
    assert result is not None
    assert result[1] == 9876543210.0


def test_entity_insertion_single(cache_db):
    """Test inserting a single entity."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    entities = [
        CachedEntity(
            file_id=file_id,
            kind="function",
            name="foo",
            entity_path="src/example.py:foo",
            start=10,
            end=20,
            summary="A test function"
        )
    ]

    cache_db.insert_entities(file_id, entities)

    # Verify insertion
    all_entities = cache_db.get_all_entities()
    assert len(all_entities) == 1
    assert all_entities[0][0] == "function"  # kind
    assert all_entities[0][1] == "src/example.py"  # file_path
    assert all_entities[0][2] == 10  # start
    assert all_entities[0][3] == 20  # end
    assert all_entities[0][4] == "A test function"  # summary


def test_entity_insertion_batch(cache_db):
    """Test inserting multiple entities at once."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    entities = [
        CachedEntity(
            file_id=file_id,
            kind="function",
            name="foo",
            entity_path="src/example.py:foo",
            start=10,
            end=20,
            summary="Function foo"
        ),
        CachedEntity(
            file_id=file_id,
            kind="class",
            name="Bar",
            entity_path="src/example.py:Bar",
            start=25,
            end=50,
            summary="Class Bar"
        ),
        CachedEntity(
            file_id=file_id,
            kind="method",
            name="baz",
            entity_path="src/example.py:Bar.baz",
            start=30,
            end=35,
            summary="Method baz"
        )
    ]

    cache_db.insert_entities(file_id, entities)

    # Verify all entities inserted
    all_entities = cache_db.get_all_entities()
    assert len(all_entities) == 3


def test_entity_insertion_empty_list(cache_db):
    """Test that inserting empty entity list doesn't fail."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)
    cache_db.insert_entities(file_id, [])

    all_entities = cache_db.get_all_entities()
    assert len(all_entities) == 0


def test_delete_entities_for_file(cache_db):
    """Test deleting entities for a specific file."""
    # Insert two files with entities
    file_id_1 = cache_db.insert_file("src/file1.py", 1234567890.0)
    file_id_2 = cache_db.insert_file("src/file2.py", 1234567890.0)

    cache_db.insert_entities(file_id_1, [
        CachedEntity(file_id_1, "function", "foo", "src/file1.py:foo", 10, 20, "Foo")
    ])
    cache_db.insert_entities(file_id_2, [
        CachedEntity(file_id_2, "function", "bar", "src/file2.py:bar", 10, 20, "Bar")
    ])

    # Delete entities for file1
    cache_db.delete_entities_for_file(file_id_1)

    # Verify only file2 entities remain
    all_entities = cache_db.get_all_entities()
    assert len(all_entities) == 1
    assert all_entities[0][1] == "src/file2.py"


def test_cascading_delete(cache_db):
    """Test that deleting a file cascades to delete its entities."""
    # Insert file with entities
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    entities = [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, "Foo"),
        CachedEntity(file_id, "class", "Bar", "src/example.py:Bar", 25, 50, "Bar")
    ]
    cache_db.insert_entities(file_id, entities)

    # Verify entities exist
    all_entities = cache_db.get_all_entities()
    assert len(all_entities) == 2

    # Delete the file
    cache_db.conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
    cache_db.conn.commit()

    # Verify entities were automatically deleted via CASCADE
    all_entities = cache_db.get_all_entities()
    assert len(all_entities) == 0


def test_delete_files_not_in(cache_db):
    """Test deleting files not in a given list."""
    # Insert multiple files
    cache_db.insert_file("src/file1.py", 1234567890.0)
    cache_db.insert_file("src/file2.py", 1234567890.0)
    cache_db.insert_file("src/file3.py", 1234567890.0)

    # Keep only file1 and file3
    cache_db.delete_files_not_in(["src/file1.py", "src/file3.py"])

    # Verify file2 was deleted
    assert cache_db.get_file("src/file1.py") is not None
    assert cache_db.get_file("src/file2.py") is None
    assert cache_db.get_file("src/file3.py") is not None


def test_delete_files_not_in_empty_list(cache_db):
    """Test that passing empty list deletes all files."""
    # Insert files
    cache_db.insert_file("src/file1.py", 1234567890.0)
    cache_db.insert_file("src/file2.py", 1234567890.0)

    # Delete all
    cache_db.delete_files_not_in([])

    # Verify all deleted
    assert cache_db.get_file("src/file1.py") is None
    assert cache_db.get_file("src/file2.py") is None


def test_delete_files_not_in_with_cascading_entities(cache_db):
    """Test that deleting files cascades to their entities."""
    # Insert files with entities
    file_id_1 = cache_db.insert_file("src/file1.py", 1234567890.0)
    file_id_2 = cache_db.insert_file("src/file2.py", 1234567890.0)

    cache_db.insert_entities(file_id_1, [
        CachedEntity(file_id_1, "function", "foo", "src/file1.py:foo", 10, 20, "Foo")
    ])
    cache_db.insert_entities(file_id_2, [
        CachedEntity(file_id_2, "function", "bar", "src/file2.py:bar", 10, 20, "Bar")
    ])

    # Keep only file1
    cache_db.delete_files_not_in(["src/file1.py"])

    # Verify only file1 entities remain
    all_entities = cache_db.get_all_entities()
    assert len(all_entities) == 1
    assert all_entities[0][1] == "src/file1.py"


def test_delete_files_not_in_large_batch(cache_db):
    """Test deleting files with >999 files to verify chunking logic works correctly."""
    # Insert 2000 files
    num_files = 2000
    for i in range(num_files):
        cache_db.insert_file(f"src/file{i}.py", 1234567890.0)

    # Keep files 0-1499 (delete files 1500-1999)
    files_to_keep = [f"src/file{i}.py" for i in range(1500)]
    cache_db.delete_files_not_in(files_to_keep)

    # Verify that files 0-1499 still exist
    for i in range(1500):
        result = cache_db.get_file(f"src/file{i}.py")
        assert result is not None, f"File {i} should still exist"

    # Verify that files 1500-1999 were deleted
    for i in range(1500, num_files):
        result = cache_db.get_file(f"src/file{i}.py")
        assert result is None, f"File {i} should have been deleted"


def test_get_all_entities_empty(cache_db):
    """Test retrieving entities from empty database."""
    entities = cache_db.get_all_entities()
    assert entities == []


def test_get_all_entities_multiple_files(cache_db):
    """Test retrieving entities from multiple files."""
    file_id_1 = cache_db.insert_file("src/file1.py", 1234567890.0)
    file_id_2 = cache_db.insert_file("src/file2.py", 1234567890.0)

    cache_db.insert_entities(file_id_1, [
        CachedEntity(file_id_1, "function", "foo", "src/file1.py:foo", 10, 20, "Foo")
    ])
    cache_db.insert_entities(file_id_2, [
        CachedEntity(file_id_2, "class", "Bar", "src/file2.py:Bar", 25, 50, "Bar")
    ])

    entities = cache_db.get_all_entities()
    assert len(entities) == 2

    # Check both files are represented
    file_paths = [e[1] for e in entities]
    assert "src/file1.py" in file_paths
    assert "src/file2.py" in file_paths


def test_context_manager(temp_cache_dir):
    """Test that context manager properly opens and closes database."""
    with CacheDatabase(temp_cache_dir) as db:
        db.insert_file("src/example.py", 1234567890.0)
        assert db.conn is not None

    # After context exit, connection should be closed
    assert db.conn is None


def test_context_manager_cleanup(temp_cache_dir):
    """Test that context manager closes database even on error."""
    try:
        with CacheDatabase(temp_cache_dir) as db:
            db.insert_file("src/example.py", 1234567890.0)
            raise ValueError("Test error")
    except ValueError:
        pass

    # Connection should still be closed
    assert db.conn is None


def test_transaction_commits_on_success(cache_db):
    """Test that transaction commits all operations on success."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    entities = [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, "Foo"),
        CachedEntity(file_id, "class", "Bar", "src/example.py:Bar", 25, 50, "Bar")
    ]

    # Use transaction for multiple operations
    with cache_db.transaction():
        cache_db.insert_entities(file_id, entities)
        cache_db.update_file_mtime(file_id, 9999999999.0)

    # Verify all operations committed
    all_entities = cache_db.get_all_entities()
    assert len(all_entities) == 2

    file_info = cache_db.get_file("src/example.py")
    assert file_info is not None
    assert file_info[1] == 9999999999.0


def test_transaction_rolls_back_on_error(cache_db):
    """Test that transaction rolls back all operations on error."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    entities = [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, "Foo")
    ]

    # Attempt transaction that will fail
    try:
        with cache_db.transaction():
            cache_db.insert_entities(file_id, entities)
            # This should cause an error (invalid file_id)
            cache_db.update_file_mtime(999999, 9999999999.0)
    except Exception:
        pass

    # Verify rollback occurred - entities should not be present
    all_entities = cache_db.get_all_entities()
    assert len(all_entities) == 0


def test_transaction_update_delete_insert_atomicity(cache_db):
    """Test atomic update of file entities (delete old + insert new pattern)."""
    # Initial setup
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)
    old_entities = [
        CachedEntity(file_id, "function", "old_func", "src/example.py:old_func", 10, 20, "Old")
    ]
    cache_db.insert_entities(file_id, old_entities)

    # Verify initial state
    assert len(cache_db.get_all_entities()) == 1

    # Update entities atomically (simulating file change)
    new_entities = [
        CachedEntity(file_id, "function", "new_func", "src/example.py:new_func", 10, 25, "New"),
        CachedEntity(file_id, "class", "NewClass", "src/example.py:NewClass", 30, 50, "Class")
    ]

    with cache_db.transaction():
        cache_db.delete_entities_for_file(file_id)
        cache_db.insert_entities(file_id, new_entities)
        cache_db.update_file_mtime(file_id, 9999999999.0)

    # Verify atomic update
    all_entities = cache_db.get_all_entities()
    assert len(all_entities) == 2
    summaries = [e[4] for e in all_entities]
    assert "New" in summaries
    assert "Class" in summaries
    assert "Old" not in summaries


def test_transaction_prevents_partial_commits(cache_db):
    """Test that individual operations don't commit within a transaction."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    entities = [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, "Foo")
    ]

    # Start transaction but don't complete it (simulate crash)
    try:
        with cache_db.transaction():
            cache_db.insert_entities(file_id, entities)
            # Simulate failure before transaction completes
            raise RuntimeError("Simulated failure")
    except RuntimeError:
        pass

    # Verify nothing was committed
    all_entities = cache_db.get_all_entities()
    assert len(all_entities) == 0


def test_nested_transaction_handling(cache_db):
    """Test that nested transactions are handled correctly."""
    file_id_1 = cache_db.insert_file("src/file1.py", 1234567890.0)
    file_id_2 = cache_db.insert_file("src/file2.py", 1234567890.0)

    entities_1 = [
        CachedEntity(file_id_1, "function", "foo", "src/file1.py:foo", 10, 20, "Foo")
    ]
    entities_2 = [
        CachedEntity(file_id_2, "function", "bar", "src/file2.py:bar", 10, 20, "Bar")
    ]

    # Outer transaction with nested transaction
    with cache_db.transaction():
        cache_db.insert_entities(file_id_1, entities_1)

        # Nested transaction
        with cache_db.transaction():
            cache_db.insert_entities(file_id_2, entities_2)

        # Both should be part of outer transaction

    # Verify both committed
    all_entities = cache_db.get_all_entities()
    assert len(all_entities) == 2


def test_transaction_with_empty_operations(cache_db):
    """Test that transaction with no operations doesn't cause errors."""
    # Empty transaction should work fine
    with cache_db.transaction():
        pass

    # Verify database still functional
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)
    assert file_id is not None


def test_multiple_sequential_transactions(cache_db):
    """Test that multiple transactions can be executed sequentially."""
    # First transaction
    with cache_db.transaction():
        file_id_1 = cache_db.insert_file("src/file1.py", 1234567890.0)
        cache_db.insert_entities(file_id_1, [
            CachedEntity(file_id_1, "function", "foo", "src/file1.py:foo", 10, 20, "Foo")
        ])

    # Second transaction
    with cache_db.transaction():
        file_id_2 = cache_db.insert_file("src/file2.py", 1234567890.0)
        cache_db.insert_entities(file_id_2, [
            CachedEntity(file_id_2, "function", "bar", "src/file2.py:bar", 10, 20, "Bar")
        ])

    # Verify both transactions committed
    all_entities = cache_db.get_all_entities()
    assert len(all_entities) == 2
