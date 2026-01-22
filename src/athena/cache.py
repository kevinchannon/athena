"""SQLite-based cache for entity docstrings to improve search performance.

This module provides persistent caching of parsed entity docstrings, significantly
reducing search latency by avoiding repeated AST parsing of unchanged files.
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


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
        self._open()

    def _open(self) -> None:
        """Open database connection and initialize schema."""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.create_tables()

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

    def insert_file(self, file_path: str, mtime: float) -> int:
        """Insert a new file record.

        Args:
            file_path: Relative path to the file from repository root
            mtime: File modification time

        Returns:
            The file_id of the inserted record
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.execute(
            "INSERT INTO files (file_path, mtime) VALUES (?, ?)",
            (file_path, mtime)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_file(self, file_path: str) -> tuple[int, float] | None:
        """Look up a file by path.

        Args:
            file_path: Relative path to the file from repository root

        Returns:
            Tuple of (file_id, mtime) if found, None otherwise
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.execute(
            "SELECT id, mtime FROM files WHERE file_path = ?",
            (file_path,)
        )
        result = cursor.fetchone()
        return tuple(result) if result else None

    def update_file_mtime(self, file_id: int, mtime: float) -> None:
        """Update the modification time of a file.

        Args:
            file_id: ID of the file to update
            mtime: New modification time
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        self.conn.execute(
            "UPDATE files SET mtime = ? WHERE id = ?",
            (mtime, file_id)
        )
        self.conn.commit()

    def delete_files_not_in(self, file_paths: list[str]) -> None:
        """Delete files that are not in the provided list.

        This handles cleanup of deleted files. Thanks to ON DELETE CASCADE,
        associated entities are automatically removed.

        Args:
            file_paths: List of file paths that should be kept
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        if not file_paths:
            # Delete all files if list is empty
            self.conn.execute("DELETE FROM files")
            self.conn.commit()
            return

        # For large repos, batch the deletion in chunks
        chunk_size = 999  # SQLite parameter limit
        for i in range(0, len(file_paths), chunk_size):
            chunk = file_paths[i:i + chunk_size]
            placeholders = ",".join("?" * len(chunk))
            self.conn.execute(
                f"DELETE FROM files WHERE file_path NOT IN ({placeholders})",
                chunk
            )
        self.conn.commit()

    def insert_entities(self, file_id: int, entities: list[CachedEntity]) -> None:
        """Insert multiple entities for a file.

        Args:
            file_id: ID of the file these entities belong to
            entities: List of entities to insert
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        if not entities:
            return

        self.conn.executemany(
            """
            INSERT INTO entities (file_id, kind, name, entity_path, start, end, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [(file_id, e.kind, e.name, e.entity_path, e.start, e.end, e.summary)
             for e in entities]
        )
        self.conn.commit()

    def delete_entities_for_file(self, file_id: int) -> None:
        """Delete all entities for a specific file.

        Args:
            file_id: ID of the file whose entities should be deleted
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        self.conn.execute("DELETE FROM entities WHERE file_id = ?", (file_id,))
        self.conn.commit()

    def get_all_entities(self) -> list[tuple[str, str, int, int, str]]:
        """Retrieve all entities from the database.

        Returns:
            List of tuples (kind, path, start, end, summary) for all entities
        """
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.execute("""
            SELECT e.kind, f.file_path, e.start, e.end, e.summary
            FROM entities e
            JOIN files f ON e.file_id = f.id
        """)
        return cursor.fetchall()
