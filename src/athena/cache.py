"""SQLite-based cache for entity docstrings to improve search performance.

This module provides persistent caching of parsed entity docstrings, significantly
reducing search latency by avoiding repeated AST parsing of unchanged files.
"""

import logging
import re
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

        Retries on "database is locked" errors to handle concurrent cache creation.

        Raises:
            sqlite3.Error: If database cannot be opened or initialized after retries.
        """
        import time

        max_retries = 3
        retry_delay = 0.1  # 100ms

        for attempt in range(max_retries):
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
                return  # Success
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    # Retry after a brief delay
                    if self.conn:
                        self.conn.close()
                        self.conn = None
                    time.sleep(retry_delay)
                    continue
                # Re-raise if not a lock error or out of retries
                logger.error(f"Failed to open cache database at {self.db_path}: {e}")
                if self.conn:
                    self.conn.close()
                    self.conn = None
                raise
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
            sqlite3.IntegrityError: If file_path already exists (UNIQUE constraint).
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
            except sqlite3.IntegrityError:
                # UNIQUE constraint - file already exists
                # This is expected in concurrent scenarios
                if not self._in_transaction:
                    self.conn.rollback()
                raise
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
        associated entities are automatically removed. FTS5 entries are
        explicitly deleted before removing entities.

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
                    self.conn.execute("DELETE FROM entities_fts")
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
                        f"""
                        DELETE FROM entities_fts
                        WHERE entity_id IN (
                            SELECT e.id FROM entities e
                            JOIN files f ON e.file_id = f.id
                            WHERE f.file_path IN ({placeholders})
                        )
                        """,
                        chunk
                    )

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
                cursor = self.conn.cursor()
                entity_ids = self._insert_entities_and_collect_ids(cursor, file_id, entities)
                self._populate_fts_table(cursor, entity_ids, entities)

                if not self._in_transaction:
                    self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to insert entities for file_id {file_id}: {e}")
                if not self._in_transaction:
                    self.conn.rollback()
                raise

    def _insert_entities_and_collect_ids(
        self, cursor: sqlite3.Cursor, file_id: int, entities: list[CachedEntity]
    ) -> list[int]:
        """Insert entities into the entities table and return their IDs."""
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
        return entity_ids

    def _populate_fts_table(
        self, cursor: sqlite3.Cursor, entity_ids: list[int], entities: list[CachedEntity]
    ) -> None:
        """Populate the FTS5 table with entity IDs and summaries."""
        cursor.executemany(
            """
            INSERT INTO entities_fts (entity_id, summary)
            VALUES (?, ?)
            """,
            [(entity_id, e.summary) for entity_id, e in zip(entity_ids, entities)]
        )

    def delete_entities_for_file(self, file_id: int) -> None:
        """Delete all entities for a specific file.

        Also deletes corresponding FTS5 entries.

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
                self.conn.execute(
                    """
                    DELETE FROM entities_fts
                    WHERE entity_id IN (
                        SELECT id FROM entities WHERE file_id = ?
                    )
                    """,
                    (file_id,)
                )
                self.conn.execute("DELETE FROM entities WHERE file_id = ?", (file_id,))
                if not self._in_transaction:
                    self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to delete entities for file_id {file_id}: {e}")
                if not self._in_transaction:
                    self.conn.rollback()
                raise

    def get_entity_by_id(self, entity_id: int) -> tuple[str, str, int, int, str] | None:
        """Retrieve a single entity by its ID.

        Args:
            entity_id: The entity ID to retrieve

        Returns:
            Tuple (kind, path, start, end, summary) if entity exists, None otherwise

        Raises:
            RuntimeError: If database connection not initialized.
            sqlite3.Error: If database operation fails.
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        with self._lock:
            try:
                cursor = self.conn.execute(
                    """
                    SELECT e.kind, f.file_path, e.start, e.end, e.summary
                    FROM entities e
                    JOIN files f ON e.file_id = f.id
                    WHERE e.id = ?
                    """,
                    (entity_id,)
                )
                result = cursor.fetchone()
                return result if result else None
            except sqlite3.Error as e:
                logger.error(f"Failed to retrieve entity {entity_id}: {e}")
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

    def query_phrase(self, query: str, limit: int) -> list[int]:
        """Query for exact phrase matches.

        Uses FTS5 phrase syntax to find entities where the summary contains
        the exact query string as a phrase. Results are ranked by FTS5's internal scoring.

        Args:
            query: Search query string (will be searched as exact phrase)
            limit: Maximum number of entity IDs to return

        Returns:
            List of entity IDs matching the phrase, ordered by relevance (best first)

        Raises:
            RuntimeError: If database connection not initialized.
            sqlite3.Error: If database operation fails.
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        if not query or not query.strip():
            return []

        with self._lock:
            try:
                # Escape quotes in the query and wrap in FTS5 phrase syntax
                escaped_query = query.replace('"', '""')
                phrase_query = f'"{escaped_query}"'

                cursor = self.conn.execute(
                    """
                    SELECT entity_id
                    FROM entities_fts
                    WHERE summary MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (phrase_query, limit)
                )
                return [row[0] for row in cursor.fetchall()]
            except sqlite3.Error as e:
                logger.error(f"Failed to execute FTS5 phrase query '{query}': {e}")
                raise

    def query_words(self, query: str, limit: int, exclude_ids: set[int]) -> list[int]:
        """Query for individual words (OR'd together).

        Terms can appear anywhere in the text. Results are ranked by FTS5's internal scoring.

        Args:
            query: Search query string (terms will be OR'd together)
            limit: Maximum number of entity IDs to return
            exclude_ids: Set of entity IDs to exclude from results (e.g., already matched by phrase search)

        Returns:
            List of entity IDs matching the query, ordered by relevance (best first),
            excluding any IDs in exclude_ids

        Raises:
            RuntimeError: If database connection not initialized.
            sqlite3.Error: If database operation fails.
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        if not query or not query.strip():
            return []

        with self._lock:
            try:
                # Transform query to OR multiple terms together
                # FTS5 defaults to AND, so we need explicit OR operators
                # Remove FTS5 special characters that could cause syntax errors
                sanitized_query = re.sub(r'[^\w\s-]', ' ', query)
                # Filter out: empty strings, standalone hyphens, FTS5 operators, and tokens that are just punctuation
                terms = [
                    t for t in sanitized_query.split()
                    if t and t != '-' and t.upper() not in ('OR', 'AND', 'NOT') and re.search(r'\w', t)
                ]
                or_query = " OR ".join(terms) if terms else ""

                # Return empty if no valid terms
                if not or_query:
                    return []

                if exclude_ids:
                    placeholders = ",".join("?" * len(exclude_ids))
                    cursor = self.conn.execute(
                        f"""
                        SELECT entity_id
                        FROM entities_fts
                        WHERE summary MATCH ?
                        AND entity_id NOT IN ({placeholders})
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (or_query, *exclude_ids, limit)
                    )
                else:
                    cursor = self.conn.execute(
                        """
                        SELECT entity_id
                        FROM entities_fts
                        WHERE summary MATCH ?
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (or_query, limit)
                    )
                return [row[0] for row in cursor.fetchall()]
            except sqlite3.Error as e:
                logger.error(f"Failed to execute FTS5 standard query '{or_query}' (original: '{query}'): {e}")
                raise
