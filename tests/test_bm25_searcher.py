"""Tests for BM25Searcher class."""

import pytest
from athena.bm25_searcher import BM25Searcher


class TestBM25SearcherInit:
    """Tests for BM25Searcher initialization."""

    def test_init_with_documents(self):
        """Test that BM25Searcher initializes with document corpus."""
        docs = ["handle JWT authentication", "parse user tokens"]
        searcher = BM25Searcher(docs)
        assert searcher.tokenized_corpus == [
            ["handle", "jwt", "authentication"],
            ["parse", "user", "tokens"],
        ]

    def test_init_with_custom_parameters(self):
        """Test that BM25Searcher accepts custom k1 and b parameters."""
        docs = ["test document"]
        searcher = BM25Searcher(docs, k1=2.0, b=0.5)
        assert searcher.bm25.k1 == 2.0
        assert searcher.bm25.b == 0.5

    def test_init_with_empty_documents(self):
        """Test that BM25Searcher handles empty document list."""
        searcher = BM25Searcher([])
        assert searcher.tokenized_corpus == []

    def test_init_with_documents_containing_code_identifiers(self):
        """Test tokenization of documents with code identifiers."""
        docs = ["handle_jwt_auth function", "handleJwtAuth method"]
        searcher = BM25Searcher(docs)
        assert searcher.tokenized_corpus == [
            ["handle", "jwt", "auth", "function"],
            ["handle", "jwt", "auth", "method"],
        ]


class TestBM25SearcherSearch:
    """Tests for BM25Searcher.search() method."""

    def test_exact_match_scores_highest(self):
        """Test that exact query match scores highest."""
        docs = [
            "JWT authentication handler",
            "User login system",
            "Password reset flow",
        ]
        searcher = BM25Searcher(docs)
        results = searcher.search("JWT authentication handler", k=3)

        # First result should be the exact match
        assert results[0][0] == 0
        assert results[0][1] > results[1][1]  # Higher score than other matches

    def test_partial_match_ranks(self):
        """Test that partial matches score lower than full matches."""
        docs = [
            "JWT authentication and authorization",
            "JWT authentication",
            "User authentication",
        ]
        searcher = BM25Searcher(docs)
        results = searcher.search("JWT authentication", k=3)

        # Document with exact match should score higher than partial
        idx_exact = results[0][0]
        idx_partial = results[1][0]
        assert idx_exact in [0, 1]  # One of the docs with "JWT authentication"
        assert idx_partial != idx_exact

    def test_term_frequency_saturation(self):
        """Test that repeated terms don't linearly increase score."""
        docs = [
            "JWT JWT JWT authentication",  # Many repetitions
            "JWT authentication",  # Single occurrence
            "User login",  # No match
        ]
        searcher = BM25Searcher(docs)
        results = searcher.search("JWT", k=2)

        # First doc should score higher but not 3x the score
        score_many = results[0][1]
        score_one = results[1][1]
        assert score_many > score_one
        # Due to saturation, score_many should be less than 3x score_one
        assert score_many < 3 * score_one

    def test_no_matches_returns_low_scores(self):
        """Test that no-match queries return low scores."""
        docs = ["JWT authentication", "User login"]
        searcher = BM25Searcher(docs)
        results = searcher.search("completely unrelated terms", k=2)

        # Should still return results but with very low scores
        assert len(results) == 2
        assert all(score < 0.1 for _, score in results)

    def test_ranking_order(self):
        """Test that results are returned in descending score order."""
        docs = [
            "User login system",
            "JWT JWT authentication handler",
            "JWT authentication",
        ]
        searcher = BM25Searcher(docs)
        results = searcher.search("JWT", k=3)

        # Verify descending order
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    def test_case_insensitive(self):
        """Test that queries match regardless of case."""
        docs = ["JWT Authentication Handler", "User Login"]
        searcher = BM25Searcher(docs)

        results_upper = searcher.search("JWT", k=1)
        results_lower = searcher.search("jwt", k=1)
        results_mixed = searcher.search("Jwt", k=1)

        # All should match the same document with similar scores
        assert results_upper[0][0] == results_lower[0][0] == results_mixed[0][0]
        assert abs(results_upper[0][1] - results_lower[0][1]) < 0.01

    def test_returns_top_k_results(self):
        """Test that search returns exactly k results."""
        docs = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        searcher = BM25Searcher(docs)
        results = searcher.search("doc", k=3)
        assert len(results) == 3

    def test_returns_fewer_than_k_if_corpus_smaller(self):
        """Test that search returns fewer results if corpus is smaller than k."""
        docs = ["doc1", "doc2"]
        searcher = BM25Searcher(docs)
        results = searcher.search("doc", k=10)
        assert len(results) == 2

    def test_returns_document_indices(self):
        """Test that results include valid document indices."""
        docs = ["JWT auth", "User login", "Password reset"]
        searcher = BM25Searcher(docs)
        results = searcher.search("auth", k=3)

        # All indices should be valid
        assert all(0 <= idx < len(docs) for idx, _ in results)

    def test_returns_scores(self):
        """Test that results include BM25 scores."""
        docs = ["JWT authentication", "User login"]
        searcher = BM25Searcher(docs)
        results = searcher.search("JWT", k=2)

        # Scores should be numeric and non-negative
        assert all(isinstance(score, (int, float)) for _, score in results)
        assert all(score >= 0 for _, score in results)

    def test_empty_query_returns_empty(self):
        """Test that empty query returns empty results."""
        docs = ["JWT authentication", "User login"]
        searcher = BM25Searcher(docs)
        results = searcher.search("", k=10)
        assert results == []

    def test_whitespace_only_query_returns_empty(self):
        """Test that whitespace-only query returns empty results."""
        docs = ["JWT authentication", "User login"]
        searcher = BM25Searcher(docs)
        results = searcher.search("   \n\t  ", k=10)
        assert results == []

    def test_query_with_code_identifiers(self):
        """Test that queries with code identifiers are tokenized correctly."""
        docs = [
            "handle_jwt_auth function implementation",
            "handleJwtAuth method in class",
            "User authentication flow",
        ]
        searcher = BM25Searcher(docs)

        # Query with snake_case
        results_snake = searcher.search("handle_jwt_auth", k=3)
        # Query with camelCase
        results_camel = searcher.search("handleJwtAuth", k=3)

        # Both should match the JWT-related docs highly
        assert results_snake[0][0] in [0, 1]
        assert results_camel[0][0] in [0, 1]

    def test_search_with_special_characters(self):
        """Test that queries with special characters are handled."""
        docs = ["JWT authentication handler", "User login system"]
        searcher = BM25Searcher(docs)
        results = searcher.search("JWT (authentication)", k=2)

        # Should match despite special characters
        assert results[0][0] == 0

    def test_search_with_numbers(self):
        """Test that queries with numbers work correctly."""
        docs = ["v2_auth_handler implementation", "v1_auth_handler old version"]
        searcher = BM25Searcher(docs)
        results = searcher.search("v2 auth", k=2)

        # Should match v2 handler
        assert results[0][0] == 0


class TestBM25SearcherEdgeCases:
    """Edge case tests for BM25Searcher."""

    def test_single_document_corpus(self):
        """Test search with single document."""
        docs = ["JWT authentication"]
        searcher = BM25Searcher(docs)
        results = searcher.search("JWT", k=1)
        assert len(results) == 1
        assert results[0][0] == 0

    def test_all_documents_identical(self):
        """Test search when all documents are identical."""
        docs = ["JWT auth", "JWT auth", "JWT auth"]
        searcher = BM25Searcher(docs)
        results = searcher.search("JWT", k=3)

        # All should have same score
        scores = [score for _, score in results]
        assert len(set(scores)) == 1  # All scores identical

    def test_very_long_document(self):
        """Test search with very long document."""
        long_doc = " ".join(["word"] * 1000)
        docs = [long_doc, "JWT authentication"]
        searcher = BM25Searcher(docs)
        results = searcher.search("JWT", k=2)

        # Should still work and prefer the shorter relevant doc
        assert results[0][0] == 1

    def test_document_with_only_stopwords(self):
        """Test document containing common words."""
        docs = ["the and or but", "JWT authentication"]
        searcher = BM25Searcher(docs)
        results = searcher.search("JWT", k=2)

        # Should prefer document with JWT
        assert results[0][0] == 1

    def test_query_longer_than_documents(self):
        """Test query that is longer than corpus documents."""
        docs = ["JWT", "auth"]
        searcher = BM25Searcher(docs)
        results = searcher.search(
            "JWT authentication handler for API endpoints", k=2
        )

        # Should still match and rank by relevance
        assert len(results) == 2
        assert results[0][1] > 0

    def test_unicode_in_documents(self):
        """Test that Unicode characters are handled gracefully."""
        docs = ["JWT 認証 handler", "User login"]
        searcher = BM25Searcher(docs)
        results = searcher.search("JWT", k=2)

        # Should match despite Unicode (ASCII-only tokenization)
        assert results[0][0] == 0

    def test_k_equals_zero(self):
        """Test that k=0 returns empty results."""
        docs = ["JWT authentication", "User login"]
        searcher = BM25Searcher(docs)
        results = searcher.search("JWT", k=0)
        assert results == []

    def test_negative_k_returns_empty(self):
        """Test that negative k returns empty results."""
        docs = ["JWT authentication", "User login"]
        searcher = BM25Searcher(docs)
        results = searcher.search("JWT", k=-1)
        assert results == []


class TestBM25SearcherIntegration:
    """Integration tests combining multiple features."""

    def test_realistic_docstring_search(self):
        """Test search with realistic docstring corpus."""
        docs = [
            "Handle JWT authentication and token validation for API requests",
            "Parse and validate user credentials from request headers",
            "Generate secure JWT tokens with configurable expiration",
            "Refresh expired JWT tokens using refresh token flow",
            "Revoke JWT tokens and maintain blacklist for security",
        ]
        searcher = BM25Searcher(docs)

        # Search for JWT-related docs
        results = searcher.search("JWT token management", k=3)

        # Should return JWT-related docs first
        top_indices = [idx for idx, _ in results]
        assert all(idx in [0, 2, 3, 4] for idx in top_indices[:3])

    def test_search_with_mixed_case_identifiers(self):
        """Test search with mixture of snake_case and camelCase."""
        docs = [
            "handle_jwt_auth function for JWT authentication",
            "handleJwtAuth method implements authentication",
            "validateUserCredentials checks user login",
        ]
        searcher = BM25Searcher(docs)

        results = searcher.search("JWT authentication handler", k=3)

        # First two should be top matches
        top_indices = [idx for idx, _ in results[:2]]
        assert set(top_indices) == {0, 1}

    def test_parameter_tuning_affects_ranking(self):
        """Test that k1 and b parameters affect ranking."""
        docs = [
            "JWT JWT JWT auth",  # High term frequency
            "JWT authentication handler implementation system",  # Long doc
            "JWT auth",  # Short and relevant
        ]

        # Default parameters
        searcher_default = BM25Searcher(docs, k1=1.5, b=0.75)
        results_default = searcher_default.search("JWT", k=3)

        # High k1 (more weight to term frequency)
        searcher_high_k1 = BM25Searcher(docs, k1=2.0, b=0.75)
        results_high_k1 = searcher_high_k1.search("JWT", k=3)

        # Rankings might differ based on parameters
        # Just verify that scoring is affected
        assert results_default[0][1] != results_high_k1[0][1]
