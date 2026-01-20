"""BM25-based search functionality for docstring search.

This module wraps the rank-bm25 library and integrates it with
athena's code-aware tokenization.
"""

from rank_bm25 import BM25Okapi

from athena.tokenizer import tokenize


class BM25Searcher:
    """BM25 search engine for document ranking.

    Uses BM25Okapi algorithm with code-aware tokenization to rank
    documents based on query relevance.

    Attributes:
        bm25: BM25Okapi instance for scoring documents.
    """

    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        """Initialize BM25 searcher with document corpus.

        Args:
            documents: List of document strings to index.
            k1: Term frequency saturation parameter. Higher values give
                more weight to term frequency. Range: [1.2, 2.0].
            b: Document length normalization parameter. Higher values
                penalize longer documents more. Range: [0.5, 0.75].

        Examples:
            >>> docs = ["handle JWT authentication", "parse user tokens"]
            >>> searcher = BM25Searcher(docs)
            >>> results = searcher.search("JWT", k=1)
            >>> len(results)
            1
            >>> results[0][0]  # Index of best match
            0
        """
        self.tokenized_corpus = [tokenize(doc) for doc in documents]
        # BM25Okapi can't handle empty corpus, so only initialize if we have documents
        self.bm25 = BM25Okapi(self.tokenized_corpus, k1=k1, b=b) if documents else None

    def search(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        """Search documents for query and return top-k ranked results.

        Args:
            query: Search query string (natural language or code identifiers).
            k: Number of top results to return.

        Returns:
            List of (document_index, score) tuples sorted by score descending.
            Empty list if query is empty or no documents match.

        Examples:
            >>> docs = ["JWT authentication handler", "User login API"]
            >>> searcher = BM25Searcher(docs)
            >>> results = searcher.search("authentication", k=1)
            >>> results[0][0]  # Index of best match
            0
            >>> results[0][1] > 0  # Score is positive
            True
        """
        if not query:
            return []

        # Handle empty corpus
        if self.bm25 is None:
            return []

        tokenized_query = tokenize(query)
        if not tokenized_query:
            return []

        scores = self.bm25.get_scores(tokenized_query)

        # Create (index, score) pairs and sort by score descending
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        # Return top-k results
        if k <= 0:
            return []
        return indexed_scores[:k]
