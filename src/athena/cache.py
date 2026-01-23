"""SQLite-based cache for entity docstrings to improve search performance.

This module provides persistent caching of parsed entity docstrings, significantly
reducing search latency by avoiding repeated AST parsing of unchanged files.
"""

import logging
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CachedEntity:
    """Represents a cached entity with its metadata and docstring."""
    file_id: int
    kind: str
    name: str
    entity_path: str
    start: int
    end: int
    summary: str


class CacheDatabase:
    """SQLite database for caching entity docstrings with file modification tracking.

    The cache uses two tables:
    - files: Tracks Python files and their modification times
    - entities: Stores entity information (functions, classes, methods, modules) with docstrings

    Uses WAL mode for concurrent access support and foreign keys with CASCADE delete
    to automatically clean up entities when files are removed.
    """

    def __init__(self, cache_dir: Path):
        """Initialize the cache database.

        Args:
            cache_dir: Directory to store the cache database (typically .athena-cache)
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / "docstring_cache.db"
        self.conn: sqlite3.Connection | None = None
        self._in_transaction = False
        self._lock = threading.RLock()  # Reentrant lock for thread-safe access
        self._open()

    def _open(self) -> None:
        """Open database connection and initialize schema.

        Raises:
            sqlite3.Error: If database cannot be opened or initialized.
        """
        try:
            self.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=10.0  # 10 second timeout for busy database
            )
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA busy_timeout = 10000")  # 10 seconds in milliseconds
            self.create_tables()
        except sqlite3.Error as e:
            logger.error(f"Failed to open cache database at {self.db_path}: {e}")
            if self.conn:
                self.conn.close()
                self.conn = None
            raise

    def create_tables(self) -> None:
        """Create database schema if it doesn't exist."""
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL UNIQUE,
                mtime REAL NOT NULL
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                entity_path TEXT NOT NULL,
                start INTEGER NOT NULL,
                end INTEGER NOT NULL,
                summary TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
            )
        """)

        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts
            USING fts5(
                entity_id UNINDEXED,
                summary,
                tokenize='porter unicode61'
            )
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_path ON files(file_path)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_id ON entities(file_id)
        """)

        self.conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self) -> "CacheDatabase":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    @contextmanager
    def transaction(self):
        """Context manager for explicit transaction control.

        This allows grouping multiple operations into a single transaction,
        ensuring atomicity and improving performance by reducing commit overhead.

        Usage:
            with cache_db.transaction():
                cache_db.delete_entities_for_file(file_id)
                cache_db.insert_entities(file_id, entities)
                cache_db.update_file_mtime(file_id, mtime)

        If an exception occurs within the context, the transaction is rolled back.
        Otherwise, it's committed on successful exit.

        Yields:
            None

        Raises:
            RuntimeError: If database connection not initialized.
            sqlite3.Error: If transaction fails.
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        with self._lock:
            # Track that we're in a transaction to prevent individual commits
            was_in_transaction = self._in_transaction
            self._in_transaction = True

            try:
                yield
                # Only commit if this is the outermost transaction
                if not was_in_transaction:
                    self.conn.commit()
            except Exception as e:
                logger.error(f"Transaction failed, rolling back: {e}")
                self.conn.rollback()
                raise
            finally:
                self._in_transaction = was_in_transaction

    def insert_file(self, file_path: str, mtime: float) -> int:
        """Insert a new file record.

        Args:
            file_path: Relative path to the file from repository root
            mtime: File modification time

        Returns:
            The file_id of the inserted record

        Raises:
            RuntimeError: If database connection not initialized.
            sqlite3.Error: If database operation fails.
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        with self._lock:
            try:
                cursor = self.conn.execute(
                    "INSERT INTO files (file_path, mtime) VALUES (?, ?)",
                    (file_path, mtime)
                )
                if not self._in_transaction:
                    self.conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                logger.error(f"Failed to insert file {file_path}: {e}")
                if not self._in_transaction:
                    self.conn.rollback()
                raise

    def get_file(self, file_path: str) -> tuple[int, float] | None:
        """Look up a file by path.

        Args:
            file_path: Relative path to the file from repository root

        Returns:
            Tuple of (file_id, mtime) if found, None otherwise

        Raises:
            RuntimeError: If database connection not initialized.
            sqlite3.Error: If database operation fails.
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        with self._lock:
            try:
                cursor = self.conn.execute(
                    "SELECT id, mtime FROM files WHERE file_path = ?",
                    (file_path,)
                )
                result = cursor.fetchone()
                return tuple(result) if result else None
            except sqlite3.Error as e:
                logger.error(f"Failed to get file {file_path}: {e}")
                raise

    def update_file_mtime(self, file_id: int, mtime: float) -> None:
        """Update the modification time of a file.

        Args:
            file_id: ID of the file to update
            mtime: New modification time

        Raises:
            RuntimeError: If database connection not initialized.
            ValueError: If file_id does not exist.
            sqlite3.Error: If database operation fails.
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        with self._lock:
            try:
                cursor = self.conn.execute(
                    "UPDATE files SET mtime = ? WHERE id = ?",
                    (mtime, file_id)
                )
                if cursor.rowcount == 0:
                    raise ValueError(f"File with id {file_id} not found")
                if not self._in_transaction:
                    self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to update mtime for file_id {file_id}: {e}")
                if not self._in_transaction:
                    self.conn.rollback()
                raise

    def delete_files_not_in(self, file_paths: list[str]) -> None:
        """Delete files that are not in the provided list.

        This handles cleanup of deleted files. Thanks to ON DELETE CASCADE,
        associated entities are automatically removed.

        Args:
            file_paths: List of file paths that should be kept

        Raises:
            RuntimeError: If database connection not initialized.
            sqlite3.Error: If database operation fails.
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        with self._lock:
            try:
                if not file_paths:
                    # Delete all files if list is empty
                    self.conn.execute("DELETE FROM files")
                    if not self._in_transaction:
                        self.conn.commit()
                    return

                # Query all existing files
                cursor = self.conn.execute("SELECT file_path FROM files")
                existing_files = {row[0] for row in cursor.fetchall()}

                # Identify files to delete (those in DB but not in keep list)
                files_to_keep = set(file_paths)
                files_to_delete = existing_files - files_to_keep

                if not files_to_delete:
                    return

                # Delete files in chunks to respect SQLite parameter limit
                chunk_size = 999  # SQLite parameter limit
                files_to_delete_list = list(files_to_delete)
                for i in range(0, len(files_to_delete_list), chunk_size):
                    chunk = files_to_delete_list[i:i + chunk_size]
                    placeholders = ",".join("?" * len(chunk))
                    self.conn.execute(
                        f"DELETE FROM files WHERE file_path IN ({placeholders})",
                        chunk
                    )
                if not self._in_transaction:
                    self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to delete stale files: {e}")
                if not self._in_transaction:
                    self.conn.rollback()
                raise

    def insert_entities(self, file_id: int, entities: list[CachedEntity]) -> None:
        """Insert multiple entities for a file.

        Args:
            file_id: ID of the file these entities belong to
            entities: List of entities to insert

        Raises:
            RuntimeError: If database connection not initialized.
            sqlite3.Error: If database operation fails.
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        if not entities:
            return

        with self._lock:
            try:
                # Insert into entities table and collect the IDs
                cursor = self.conn.cursor()
                entity_ids = []
                for e in entities:
                    cursor.execute(
                        """
                        INSERT INTO entities (file_id, kind, name, entity_path, start, end, summary)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (file_id, e.kind, e.name, e.entity_path, e.start, e.end, e.summary)
                    )
                    entity_ids.append(cursor.lastrowid)

                # Insert into FTS5 table
                cursor.executemany(
                    """
                    INSERT INTO entities_fts (entity_id, summary)
                    VALUES (?, ?)
                    """,
                    [(entity_id, e.summary) for entity_id, e in zip(entity_ids, entities)]
                )

                if not self._in_transaction:
                    self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to insert entities for file_id {file_id}: {e}")
                if not self._in_transaction:
                    self.conn.rollback()
                raise

    def delete_entities_for_file(self, file_id: int) -> None:
        """Delete all entities for a specific file.

        Args:
            file_id: ID of the file whose entities should be deleted

        Raises:
            RuntimeError: If database connection not initialized.
            sqlite3.Error: If database operation fails.
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        with self._lock:
            try:
                self.conn.execute("DELETE FROM entities WHERE file_id = ?", (file_id,))
                if not self._in_transaction:
                    self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to delete entities for file_id {file_id}: {e}")
                if not self._in_transaction:
                    self.conn.rollback()
                raise

    def get_all_entities(self) -> list[tuple[str, str, int, int, str]]:
        """Retrieve all entities from the database.

        Returns:
            List of tuples (kind, path, start, end, summary) for all entities

        Raises:
            RuntimeError: If database connection not initialized.
            sqlite3.Error: If database operation fails.
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        with self._lock:
            try:
                cursor = self.conn.execute("""
                    SELECT e.kind, f.file_path, e.start, e.end, e.summary
                    FROM entities e
                    JOIN files f ON e.file_id = f.id
                """)
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Failed to retrieve entities: {e}")
                raise
