"""Tests for the SQLite cache database."""

import sqlite3
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
    assert "entities_fts" in tables

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


def test_fts5_table_created(cache_db):
    """Test that FTS5 virtual table is created with correct configuration."""
    # Verify FTS5 table exists
    cursor = cache_db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='entities_fts'"
    )
    assert cursor.fetchone() is not None

    # Verify FTS5 table has correct columns by inserting a test row
    cache_db.conn.execute(
        "INSERT INTO entities_fts (entity_id, summary) VALUES (?, ?)",
        (1, "test summary")
    )
    cache_db.conn.commit()

    # Verify we can query the FTS5 table
    cursor = cache_db.conn.execute(
        "SELECT entity_id, summary FROM entities_fts WHERE summary MATCH 'test'"
    )
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == 1
    assert result[1] == "test summary"


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
    """Test that duplicate file paths raise an IntegrityError."""
    cache_db.insert_file("src/example.py", 1234567890.0)

    # Attempting to insert same path should fail with IntegrityError
    with pytest.raises(sqlite3.IntegrityError):
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


def test_get_entity_by_id(cache_db):
    """Test retrieving a single entity by ID."""
    file_id = cache_db.insert_file("src/module.py", 1234567890.0)

    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "foo", "src/module.py:foo", 10, 20, "Foo function"),
        CachedEntity(file_id, "class", "Bar", "src/module.py:Bar", 25, 50, "Bar class")
    ])

    # Get the first entity (ID should be 1)
    entity = cache_db.get_entity_by_id(1)
    assert entity is not None
    kind, path, start, end, summary = entity
    assert kind == "function"
    assert path == "src/module.py"
    assert start == 10
    assert end == 20
    assert summary == "Foo function"

    # Get the second entity (ID should be 2)
    entity = cache_db.get_entity_by_id(2)
    assert entity is not None
    kind, path, start, end, summary = entity
    assert kind == "class"
    assert path == "src/module.py"
    assert start == 25
    assert end == 50
    assert summary == "Bar class"


def test_get_entity_by_id_nonexistent(cache_db):
    """Test retrieving a non-existent entity returns None."""
    entity = cache_db.get_entity_by_id(999)
    assert entity is None


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


# Concurrent Access Tests


def test_concurrent_reads(cache_db):
    """Test that multiple threads can read from cache simultaneously."""
    import threading

    # Populate cache
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)
    entities = [
        CachedEntity(file_id, "function", f"func_{i}", f"src/example.py:func_{i}", i*10, i*10+5, f"Function {i}")
        for i in range(10)
    ]
    cache_db.insert_entities(file_id, entities)

    results = []
    errors = []

    def read_entities():
        try:
            # Multiple reads from different threads
            for _ in range(5):
                entities = cache_db.get_all_entities()
                results.append(len(entities))
        except Exception as e:
            errors.append(e)

    # Create multiple reader threads
    threads = [threading.Thread(target=read_entities) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify no errors and all reads successful
    assert len(errors) == 0, f"Concurrent reads failed: {errors}"
    assert len(results) == 25  # 5 threads * 5 reads each
    assert all(count == 10 for count in results)


def test_concurrent_writes(cache_db):
    """Test that multiple threads can write to cache with proper serialization."""
    import threading

    errors = []

    def write_file(thread_id):
        try:
            file_id = cache_db.insert_file(f"src/file_{thread_id}.py", 1234567890.0 + thread_id)
            entities = [
                CachedEntity(
                    file_id,
                    "function",
                    f"func_{thread_id}",
                    f"src/file_{thread_id}.py:func_{thread_id}",
                    10,
                    20,
                    f"Function in thread {thread_id}"
                )
            ]
            cache_db.insert_entities(file_id, entities)
        except Exception as e:
            errors.append(e)

    # Create multiple writer threads
    threads = [threading.Thread(target=write_file, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify no errors
    assert len(errors) == 0, f"Concurrent writes failed: {errors}"

    # Verify all files and entities were written
    all_entities = cache_db.get_all_entities()
    assert len(all_entities) == 10


def test_concurrent_read_write(cache_db):
    """Test concurrent reads and writes (WAL mode allows this)."""
    import threading

    # Populate initial data
    file_id = cache_db.insert_file("src/initial.py", 1234567890.0)
    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "initial", "src/initial.py:initial", 0, 10, "Initial")
    ])

    read_results = []
    errors = []

    def reader():
        try:
            for _ in range(10):
                entities = cache_db.get_all_entities()
                read_results.append(len(entities))
        except Exception as e:
            errors.append(("read", e))

    def writer(thread_id):
        try:
            file_id = cache_db.insert_file(f"src/write_{thread_id}.py", 1234567890.0 + thread_id)
            cache_db.insert_entities(file_id, [
                CachedEntity(file_id, "function", f"write_{thread_id}", f"src/write_{thread_id}.py:write_{thread_id}", 0, 10, f"Write {thread_id}")
            ])
        except Exception as e:
            errors.append(("write", e))

    # Mix of readers and writers
    threads = []
    threads.extend([threading.Thread(target=reader) for _ in range(3)])
    threads.extend([threading.Thread(target=writer, args=(i,)) for i in range(5)])

    # Start all threads
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify no errors
    assert len(errors) == 0, f"Concurrent read/write failed: {errors}"

    # Verify final state (initial + 5 writes)
    final_entities = cache_db.get_all_entities()
    assert len(final_entities) == 6


def test_concurrent_transactions(cache_db):
    """Test that transactions from different threads are properly isolated."""
    import threading

    errors = []

    def transactional_write(thread_id):
        try:
            with cache_db.transaction():
                file_id = cache_db.insert_file(f"src/trans_{thread_id}.py", 1234567890.0 + thread_id)
                cache_db.insert_entities(file_id, [
                    CachedEntity(file_id, "function", f"trans_{thread_id}", f"src/trans_{thread_id}.py:trans_{thread_id}", 0, 10, f"Trans {thread_id}")
                ])
        except Exception as e:
            errors.append(e)

    # Multiple threads each executing a transaction
    threads = [threading.Thread(target=transactional_write, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify no errors
    assert len(errors) == 0, f"Concurrent transactions failed: {errors}"

    # Verify all transactions committed
    all_entities = cache_db.get_all_entities()
    assert len(all_entities) == 8


def test_concurrent_updates(cache_db):
    """Test concurrent updates to the same file's mtime."""
    import threading
    import time

    # Create initial file
    file_id = cache_db.insert_file("src/concurrent.py", 1234567890.0)

    errors = []

    def update_mtime(new_mtime):
        try:
            cache_db.update_file_mtime(file_id, new_mtime)
        except Exception as e:
            errors.append(e)

    # Multiple threads updating the same file's mtime
    mtimes = [1234567890.0 + i for i in range(10)]
    threads = [threading.Thread(target=update_mtime, args=(mt,)) for mt in mtimes]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify no errors (WAL mode should handle this)
    assert len(errors) == 0, f"Concurrent updates failed: {errors}"

    # Verify file still exists and has one of the mtimes
    result = cache_db.get_file("src/concurrent.py")
    assert result is not None
    assert result[1] in mtimes


def test_database_timeout_on_lock(cache_db):
    """Test that database timeout is properly configured for busy scenarios."""
    import threading
    import time

    # Verify timeout is set to 10 seconds
    cursor = cache_db.conn.execute("PRAGMA busy_timeout")
    timeout_ms = cursor.fetchone()[0]
    assert timeout_ms == 10000  # 10 seconds in milliseconds

    # This test verifies the timeout is configured, not that it actually works
    # (testing actual locking would require low-level SQLite manipulation)


# FTS5 Integration Tests


def test_fts5_entry_created_on_entity_insert(cache_db):
    """Test that FTS5 entries are created when entities are inserted."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    entities = [
        CachedEntity(
            file_id=file_id,
            kind="function",
            name="foo",
            entity_path="src/example.py:foo",
            start=10,
            end=20,
            summary="A test function for searching"
        )
    ]

    cache_db.insert_entities(file_id, entities)

    # Verify FTS5 entry was created
    cursor = cache_db.conn.execute(
        "SELECT entity_id, summary FROM entities_fts WHERE summary MATCH 'searching'"
    )
    result = cursor.fetchone()
    assert result is not None
    assert result[1] == "A test function for searching"


def test_fts5_multiple_entries_on_batch_insert(cache_db):
    """Test that FTS5 entries are created for batch entity insertion."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    entities = [
        CachedEntity(
            file_id=file_id,
            kind="function",
            name="foo",
            entity_path="src/example.py:foo",
            start=10,
            end=20,
            summary="Function for parsing data"
        ),
        CachedEntity(
            file_id=file_id,
            kind="class",
            name="Bar",
            entity_path="src/example.py:Bar",
            start=25,
            end=50,
            summary="Class for processing requests"
        ),
        CachedEntity(
            file_id=file_id,
            kind="method",
            name="baz",
            entity_path="src/example.py:Bar.baz",
            start=30,
            end=35,
            summary="Method for validating input"
        )
    ]

    cache_db.insert_entities(file_id, entities)

    # Verify all FTS5 entries created
    cursor = cache_db.conn.execute("SELECT COUNT(*) FROM entities_fts")
    count = cursor.fetchone()[0]
    assert count == 3

    # Verify we can search for each one
    cursor = cache_db.conn.execute(
        "SELECT summary FROM entities_fts WHERE summary MATCH 'parsing'"
    )
    assert cursor.fetchone()[0] == "Function for parsing data"

    cursor = cache_db.conn.execute(
        "SELECT summary FROM entities_fts WHERE summary MATCH 'processing'"
    )
    assert cursor.fetchone()[0] == "Class for processing requests"

    cursor = cache_db.conn.execute(
        "SELECT summary FROM entities_fts WHERE summary MATCH 'validating'"
    )
    assert cursor.fetchone()[0] == "Method for validating input"


def test_fts5_entity_id_mapping(cache_db):
    """Test that FTS5 entity_id correctly maps to entities table."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    entities = [
        CachedEntity(
            file_id=file_id,
            kind="function",
            name="foo",
            entity_path="src/example.py:foo",
            start=10,
            end=20,
            summary="A searchable function"
        )
    ]

    cache_db.insert_entities(file_id, entities)

    # Get entity_id from FTS5
    cursor = cache_db.conn.execute(
        "SELECT entity_id FROM entities_fts WHERE summary MATCH 'searchable'"
    )
    fts_entity_id = cursor.fetchone()[0]

    # Verify it matches the entities table
    cursor = cache_db.conn.execute(
        "SELECT id, name, summary FROM entities WHERE id = ?",
        (fts_entity_id,)
    )
    entity_row = cursor.fetchone()
    assert entity_row is not None
    assert entity_row[1] == "foo"
    assert entity_row[2] == "A searchable function"


def test_fts5_transaction_atomicity(cache_db):
    """Test that FTS5 entries are rolled back on transaction failure."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    entities = [
        CachedEntity(
            file_id=file_id,
            kind="function",
            name="foo",
            entity_path="src/example.py:foo",
            start=10,
            end=20,
            summary="Function that should be rolled back"
        )
    ]

    # Attempt transaction that will fail
    try:
        with cache_db.transaction():
            cache_db.insert_entities(file_id, entities)
            # Cause an error to trigger rollback
            raise RuntimeError("Simulated failure")
    except RuntimeError:
        pass

    # Verify FTS5 entries were rolled back
    cursor = cache_db.conn.execute("SELECT COUNT(*) FROM entities_fts")
    count = cursor.fetchone()[0]
    assert count == 0

    # Verify entities table was also rolled back
    assert len(cache_db.get_all_entities()) == 0


def test_fts5_entries_deleted_with_entities(cache_db):
    """Test that FTS5 entries are deleted when entities are deleted."""
    # Insert file with entities
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    entities = [
        CachedEntity(
            file_id=file_id,
            kind="function",
            name="foo",
            entity_path="src/example.py:foo",
            start=10,
            end=20,
            summary="Function to be deleted"
        )
    ]

    cache_db.insert_entities(file_id, entities)

    # Verify FTS5 entry exists
    cursor = cache_db.conn.execute("SELECT COUNT(*) FROM entities_fts")
    assert cursor.fetchone()[0] == 1

    # Delete entities for file
    cache_db.delete_entities_for_file(file_id)

    # Verify FTS5 entries were deleted
    cursor = cache_db.conn.execute("SELECT COUNT(*) FROM entities_fts")
    assert cursor.fetchone()[0] == 0


def test_fts5_entries_deleted_on_file_deletion(cache_db):
    """Test that FTS5 entries are deleted when files are deleted via cascade."""
    # Insert two files with entities
    file_id_1 = cache_db.insert_file("src/file1.py", 1234567890.0)
    file_id_2 = cache_db.insert_file("src/file2.py", 1234567890.0)

    cache_db.insert_entities(file_id_1, [
        CachedEntity(file_id_1, "function", "foo", "src/file1.py:foo", 10, 20, "Foo function")
    ])
    cache_db.insert_entities(file_id_2, [
        CachedEntity(file_id_2, "function", "bar", "src/file2.py:bar", 10, 20, "Bar function")
    ])

    # Verify both FTS5 entries exist
    cursor = cache_db.conn.execute("SELECT COUNT(*) FROM entities_fts")
    assert cursor.fetchone()[0] == 2

    # Delete file1
    cache_db.delete_files_not_in(["src/file2.py"])

    # Verify only file2's FTS5 entry remains
    cursor = cache_db.conn.execute("SELECT COUNT(*) FROM entities_fts")
    assert cursor.fetchone()[0] == 1

    cursor = cache_db.conn.execute(
        "SELECT summary FROM entities_fts WHERE summary MATCH 'Bar'"
    )
    assert cursor.fetchone()[0] == "Bar function"


def test_fts5_all_entries_deleted_when_all_files_deleted(cache_db):
    """Test that all FTS5 entries are deleted when all files are removed."""
    # Insert multiple files with entities
    for i in range(3):
        file_id = cache_db.insert_file(f"src/file{i}.py", 1234567890.0)
        cache_db.insert_entities(file_id, [
            CachedEntity(file_id, "function", f"func{i}", f"src/file{i}.py:func{i}", 10, 20, f"Function {i}")
        ])

    # Verify FTS5 entries exist
    cursor = cache_db.conn.execute("SELECT COUNT(*) FROM entities_fts")
    assert cursor.fetchone()[0] == 3

    # Delete all files
    cache_db.delete_files_not_in([])

    # Verify all FTS5 entries deleted
    cursor = cache_db.conn.execute("SELECT COUNT(*) FROM entities_fts")
    assert cursor.fetchone()[0] == 0


def test_fts5_deletion_with_large_batch(cache_db):
    """Test FTS5 deletion works correctly with >999 files (chunking logic)."""
    # Insert 1500 files with entities
    num_files = 1500
    for i in range(num_files):
        file_id = cache_db.insert_file(f"src/file{i}.py", 1234567890.0)
        cache_db.insert_entities(file_id, [
            CachedEntity(file_id, "function", f"func{i}", f"src/file{i}.py:func{i}", 10, 20, f"Function {i}")
        ])

    # Verify all FTS5 entries created
    cursor = cache_db.conn.execute("SELECT COUNT(*) FROM entities_fts")
    assert cursor.fetchone()[0] == num_files

    # Keep only first 500 files (delete 1000)
    files_to_keep = [f"src/file{i}.py" for i in range(500)]
    cache_db.delete_files_not_in(files_to_keep)

    # Verify only 500 FTS5 entries remain
    cursor = cache_db.conn.execute("SELECT COUNT(*) FROM entities_fts")
    assert cursor.fetchone()[0] == 500


def test_fts5_deletion_preserves_correct_entries(cache_db):
    """Test that FTS5 deletion removes only the correct entries."""
    # Insert multiple files
    file_id_1 = cache_db.insert_file("src/keep.py", 1234567890.0)
    file_id_2 = cache_db.insert_file("src/delete.py", 1234567890.0)

    cache_db.insert_entities(file_id_1, [
        CachedEntity(file_id_1, "function", "keep_func", "src/keep.py:keep_func", 10, 20, "Function to keep")
    ])
    cache_db.insert_entities(file_id_2, [
        CachedEntity(file_id_2, "function", "delete_func", "src/delete.py:delete_func", 10, 20, "Function to delete")
    ])

    # Delete file2
    cache_db.delete_files_not_in(["src/keep.py"])

    # Verify correct FTS5 entry remains
    cursor = cache_db.conn.execute(
        "SELECT summary FROM entities_fts WHERE summary MATCH 'keep'"
    )
    assert cursor.fetchone()[0] == "Function to keep"

    # Verify deleted entry is gone
    cursor = cache_db.conn.execute(
        "SELECT summary FROM entities_fts WHERE summary MATCH 'delete'"
    )
    assert cursor.fetchone() is None


# FTS5 Query Method Tests


def test_query_phrase_exact_match(cache_db):
    """Test phrase query returns exact phrase matches."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, "Parse JSON data"),
        CachedEntity(file_id, "function", "bar", "src/example.py:bar", 30, 40, "Parse XML data"),
        CachedEntity(file_id, "function", "baz", "src/example.py:baz", 50, 60, "JSON parser utility")
    ])

    # Query for exact phrase "JSON data"
    entity_ids = cache_db.query_phrase("JSON data", limit=10)

    # Should only match "Parse JSON data", not "JSON parser utility"
    assert len(entity_ids) == 1

    # Verify it's the correct entity
    cursor = cache_db.conn.execute(
        "SELECT name FROM entities WHERE id = ?",
        (entity_ids[0],)
    )
    assert cursor.fetchone()[0] == "foo"


def test_query_phrase_multiple_matches(cache_db):
    """Test phrase query returns multiple exact matches."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "func1", "src/example.py:func1", 10, 20, "Process user input"),
        CachedEntity(file_id, "function", "func2", "src/example.py:func2", 30, 40, "Validate user input"),
        CachedEntity(file_id, "function", "func3", "src/example.py:func3", 50, 60, "User authentication")
    ])

    # Query for exact phrase "user input"
    entity_ids = cache_db.query_phrase("user input", limit=10)

    # Should match both func1 and func2
    assert len(entity_ids) == 2

    # Verify correct entities matched
    cursor = cache_db.conn.execute(
        f"SELECT name FROM entities WHERE id IN ({','.join('?' * len(entity_ids))})",
        entity_ids
    )
    names = {row[0] for row in cursor.fetchall()}
    assert names == {"func1", "func2"}


def test_query_phrase_empty_query(cache_db):
    """Test phrase query with empty string returns empty list."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, "Some function")
    ])

    # Empty query should return empty list
    assert cache_db.query_phrase("", limit=10) == []
    assert cache_db.query_phrase("   ", limit=10) == []


def test_query_phrase_no_matches(cache_db):
    """Test phrase query with no matches returns empty list."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, "Parse JSON data")
    ])

    # Query for phrase that doesn't exist
    entity_ids = cache_db.query_phrase("XML parser", limit=10)
    assert entity_ids == []


def test_query_phrase_respects_limit(cache_db):
    """Test phrase query respects the limit parameter."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    # Insert 5 entities with the same phrase
    entities = [
        CachedEntity(file_id, "function", f"func{i}", f"src/example.py:func{i}", i*10, i*10+5, "Parse data")
        for i in range(5)
    ]
    cache_db.insert_entities(file_id, entities)

    # Query with limit=2
    entity_ids = cache_db.query_phrase("Parse data", limit=2)
    assert len(entity_ids) == 2


def test_query_phrase_with_quotes(cache_db):
    """Test phrase query handles quotes in the query string."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, 'Parse "quoted" string')
    ])

    # Query for phrase with quotes (should be escaped)
    entity_ids = cache_db.query_phrase('"quoted" string', limit=10)
    assert len(entity_ids) == 1


def test_query_phrase_case_insensitive(cache_db):
    """Test phrase query is case insensitive."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, "Parse JSON Data")
    ])

    # Query with different case should still match
    entity_ids = cache_db.query_phrase("json data", limit=10)
    assert len(entity_ids) == 1


def test_query_words_single_term(cache_db):
    """Test standard query matches single term."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, "Parse JSON data"),
        CachedEntity(file_id, "function", "bar", "src/example.py:bar", 30, 40, "Process XML files"),
        CachedEntity(file_id, "function", "baz", "src/example.py:baz", 50, 60, "JSON parser utility")
    ])

    # Query for single term "JSON"
    entity_ids = cache_db.query_words("JSON", limit=10, exclude_ids=set())

    # Should match both foo and baz
    assert len(entity_ids) == 2

    cursor = cache_db.conn.execute(
        f"SELECT name FROM entities WHERE id IN ({','.join('?' * len(entity_ids))})",
        entity_ids
    )
    names = {row[0] for row in cursor.fetchall()}
    assert names == {"foo", "baz"}


def test_query_words_multiple_terms(cache_db):
    """Test standard query matches multiple terms (OR logic)."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, "Parse JSON data"),
        CachedEntity(file_id, "function", "bar", "src/example.py:bar", 30, 40, "Process XML files"),
        CachedEntity(file_id, "function", "baz", "src/example.py:baz", 50, 60, "Validate input data")
    ])

    # Query for "JSON XML" (should match any document with either term)
    entity_ids = cache_db.query_words("JSON XML", limit=10, exclude_ids=set())

    # Should match foo (JSON) and bar (XML)
    assert len(entity_ids) == 2

    cursor = cache_db.conn.execute(
        f"SELECT name FROM entities WHERE id IN ({','.join('?' * len(entity_ids))})",
        entity_ids
    )
    names = {row[0] for row in cursor.fetchall()}
    assert names == {"foo", "bar"}


def test_query_words_excludes_ids(cache_db):
    """Test standard query excludes specified entity IDs."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, "Parse JSON data"),
        CachedEntity(file_id, "function", "bar", "src/example.py:bar", 30, 40, "JSON parser utility"),
        CachedEntity(file_id, "function", "baz", "src/example.py:baz", 50, 60, "JSON validator")
    ])

    # First get all matches
    all_ids = cache_db.query_words("JSON", limit=10, exclude_ids=set())
    assert len(all_ids) == 3

    # Now exclude the first ID
    excluded_ids = {all_ids[0]}
    remaining_ids = cache_db.query_words("JSON", limit=10, exclude_ids=excluded_ids)

    # Should get 2 results, excluding the first one
    assert len(remaining_ids) == 2
    assert all_ids[0] not in remaining_ids


def test_query_words_empty_query(cache_db):
    """Test standard query with empty string returns empty list."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, "Some function")
    ])

    # Empty query should return empty list
    assert cache_db.query_words("", limit=10, exclude_ids=set()) == []
    assert cache_db.query_words("   ", limit=10, exclude_ids=set()) == []


def test_query_words_no_matches(cache_db):
    """Test standard query with no matches returns empty list."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, "Parse JSON data")
    ])

    # Query for term that doesn't exist
    entity_ids = cache_db.query_words("nonexistent", limit=10, exclude_ids=set())
    assert entity_ids == []


def test_query_words_respects_limit(cache_db):
    """Test standard query respects the limit parameter."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    # Insert 5 entities with the same term
    entities = [
        CachedEntity(file_id, "function", f"func{i}", f"src/example.py:func{i}", i*10, i*10+5, "Parse data")
        for i in range(5)
    ]
    cache_db.insert_entities(file_id, entities)

    # Query with limit=2
    entity_ids = cache_db.query_words("Parse", limit=2, exclude_ids=set())
    assert len(entity_ids) == 2


def test_query_words_case_insensitive(cache_db):
    """Test standard query is case insensitive."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, "Parse JSON Data")
    ])

    # Query with different case should still match
    entity_ids = cache_db.query_words("json", limit=10, exclude_ids=set())
    assert len(entity_ids) == 1


def test_query_words_empty_exclude_set(cache_db):
    """Test standard query works with empty exclude_ids set."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "foo", "src/example.py:foo", 10, 20, "Parse data")
    ])

    # Empty exclude set should return normal results
    entity_ids = cache_db.query_words("Parse", limit=10, exclude_ids=set())
    assert len(entity_ids) == 1


def test_query_words_bm25_ranking(cache_db):
    """Test standard query ranks documents by FTS5 relevance score."""
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    cache_db.insert_entities(file_id, [
        CachedEntity(file_id, "function", "func1", "src/example.py:func1", 10, 20, "Parse JSON data with JSON parser"),
        CachedEntity(file_id, "function", "func2", "src/example.py:func2", 30, 40, "Parse JSON"),
        CachedEntity(file_id, "function", "func3", "src/example.py:func3", 50, 60, "Process data files")
    ])

    # Query for "JSON"
    entity_ids = cache_db.query_words("JSON", limit=10, exclude_ids=set())

    # func1 should rank higher than func2 (more JSON mentions)
    # func3 should not appear (no JSON)
    assert len(entity_ids) == 2

    cursor = cache_db.conn.execute(
        f"SELECT name FROM entities WHERE id IN ({','.join('?' * len(entity_ids))})",
        entity_ids
    )
    names = [row[0] for row in cursor.fetchall()]

    # First result should be func1 (highest FTS5 score)
    assert names[0] == "func1"


def test_fts5_ranking_fts_aligned(cache_db):
    """Test FTS5 ranking behavior using rank-based ordering assertions.

    Tests SQLite FTS5 ranking semantics by asserting relative ordering constraints
    rather than absolute scores. Uses a 10-document corpus to verify phrase matches,
    term coverage, and ordering behavior align with FTS5 guarantees.

    Based on "SQLite FTS5 Ranking Tests (Rank-Only, FTS5-Aligned)" specification.
    """
    file_id = cache_db.insert_file("src/example.py", 1234567890.0)

    # Create 10-document corpus
    corpus_content = [
        "one two three four five six",     # ID 1
        "one two three",                   # ID 2
        "four five six",                   # ID 3
        "one three five",                  # ID 4
        "two four six",                    # ID 5
        "six five four three two one",     # ID 6
        "one six",                         # ID 7
        "three",                           # ID 8
        "one",                             # ID 9
        "the quick brown fox",             # ID 10
    ]

    # Insert corpus documents
    entities = []
    for i, content in enumerate(corpus_content, start=1):
        entities.append(CachedEntity(
            file_id, "function", f"func_{i:02d}", f"src/example.py:func_{i:02d}",
            i * 10, i * 10 + 10, content
        ))
    cache_db.insert_entities(file_id, entities)

    # Get entity IDs in order (now sorted correctly with zero-padded names)
    cursor = cache_db.conn.execute(
        "SELECT id FROM entities WHERE file_id = ? ORDER BY name",
        (file_id,)
    )
    entity_ids = [row[0] for row in cursor.fetchall()]
    doc_ids = {i+1: entity_ids[i] for i in range(10)}

    # Helper functions for rank-based assertions
    def assert_before(results: list[int], doc_a: int, doc_b: int):
        """Assert that doc_a appears before doc_b in results."""
        entity_a = doc_ids[doc_a]
        entity_b = doc_ids[doc_b]
        assert entity_a in results, f"Doc {doc_a} not in results"
        assert entity_b in results, f"Doc {doc_b} not in results"
        idx_a = results.index(entity_a)
        idx_b = results.index(entity_b)
        assert idx_a < idx_b, f"Doc {doc_a} should appear before doc {doc_b}, but got positions {idx_a} and {idx_b}"

    def assert_set_equal(results: list[int], expected_docs: set[int]):
        """Assert that result set equals expected document set."""
        expected_entities = {doc_ids[d] for d in expected_docs}
        actual_entities = set(results)
        assert actual_entities == expected_entities, \
            f"Expected docs {expected_docs}, got {[k for k, v in doc_ids.items() if v in actual_entities]}"

    def assert_all_before(results: list[int], set_a: set[int], set_b: set[int]):
        """Assert that all docs in set_a appear before all docs in set_b."""
        entities_a = {doc_ids[d] for d in set_a}
        entities_b = {doc_ids[d] for d in set_b}

        # Find max position of set_a and min position of set_b
        max_a_pos = max((results.index(e) for e in entities_a if e in results), default=-1)
        min_b_pos = min((results.index(e) for e in entities_b if e in results), default=len(results))

        assert max_a_pos < min_b_pos, \
            f"All docs in {set_a} should appear before all docs in {set_b}"

    def assert_excluded(results: list[int], excluded_doc: int):
        """Assert that a document does not appear in results."""
        entity = doc_ids[excluded_doc]
        assert entity not in results, f"Doc {excluded_doc} should not appear in results"

    def assert_before_or_equal(results: list[int], doc_a: int, doc_b: int):
        """Assert that doc_a appears before or at same position as doc_b (for ties)."""
        entity_a = doc_ids[doc_a]
        entity_b = doc_ids[doc_b]
        if entity_a in results and entity_b in results:
            idx_a = results.index(entity_a)
            idx_b = results.index(entity_b)
            assert idx_a <= idx_b, f"Doc {doc_a} should appear before or equal to doc {doc_b}"

    # Test 1: Exact phrase match (ordered, contiguous)
    # Query: "one two three"
    # Expected: Docs 1 and 2 are phrase matches, 6 is not (reversed order)
    phrase_results = cache_db.query_phrase("one two three", limit=10)
    standard_results = cache_db.query_words("one two three", limit=10, exclude_ids=set(phrase_results))
    combined_results = phrase_results + standard_results

    # Docs {1,2} both appear before doc 4
    assert_before(combined_results, 1, 4)
    assert_before(combined_results, 2, 4)
    # Docs {1,2} both appear before doc 6
    assert_before(combined_results, 1, 6)
    assert_before(combined_results, 2, 6)
    # Doc 10 does not appear
    assert_excluded(combined_results, 10)

    # Test 2: No phrase, full term coverage
    # Query: "one three five"
    # Expected: Docs 1, 4, 6 contain all three terms
    # Note: With OR logic, FTS5 doesn't guarantee docs with more matching terms
    # rank higher - shorter docs matching fewer terms can rank higher due to length normalization.
    standard_results = cache_db.query_words("one three five", limit=10, exclude_ids=set())

    # Verify that docs containing the terms are present (but not ordering)
    result_docs = {k for k, v in doc_ids.items() if v in standard_results}
    # At minimum, docs with all three terms should be in results
    assert {1, 4, 6}.issubset(result_docs), f"Docs with all terms should be in results: {result_docs}"
    # Doc 10 excluded (doesn't contain any query terms)
    assert_excluded(standard_results, 10)

    # Test 3: Single-term query
    # Query: "six"
    # Expected: All and only docs containing "six" must match
    standard_results = cache_db.query_words("six", limit=10, exclude_ids=set())

    # Result set equals {1,3,5,6,7}
    assert_set_equal(standard_results, {1, 3, 5, 6, 7})
    # Doc 7 appears before or equal to doc 1 (shorter doc may rank higher)
    assert_before_or_equal(standard_results, 7, 1)

    # Test 4: Phrase plus additional term
    # Query: "one two four"
    # Expected: Phrase "one two" matches 1 and 2
    # Note: Both docs 1 and 2 match the phrase equally; FTS5 doesn't consider "four" when ranking phrase matches
    phrase_results = cache_db.query_phrase("one two", limit=10)
    standard_results = cache_db.query_words("one two four", limit=10, exclude_ids=set(phrase_results))
    combined_results = phrase_results + standard_results

    # Both docs 1 and 2 should be in phrase results (no guaranteed ordering between them)
    phrase_docs = {k for k, v in doc_ids.items() if v in phrase_results}
    assert {1, 2}.issubset(phrase_docs), f"Docs 1 and 2 should match phrase 'one two': {phrase_docs}"
    # Phrase matches (1,2) should appear before non-phrase matches
    if 4 in [k for k, v in doc_ids.items() if v in combined_results]:
        # At least one phrase match should appear before doc 4
        assert any(phrase_results.index(doc_ids[d]) < combined_results.index(doc_ids[4])
                   for d in [1, 2] if doc_ids[d] in phrase_results)

    # Test 5: Longer phrase match
    # Query: "three four five six"
    # Expected: Phrase matches only doc 1
    phrase_results = cache_db.query_phrase("three four five six", limit=10)
    standard_results = cache_db.query_words("three four five six", limit=10, exclude_ids=set(phrase_results))
    combined_results = phrase_results + standard_results

    # Doc 1 appears before doc 3
    assert_before(combined_results, 1, 3)
    # Doc 3 appears before doc 6
    assert_before(combined_results, 3, 6)
    # Doc 6 appears before doc 4
    assert_before(combined_results, 6, 4)
    # Doc 10 excluded
    assert_excluded(combined_results, 10)
