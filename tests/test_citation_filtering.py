import asyncio
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from deep_research.search import semantic_search
from deep_research.processing import Snippet


class TestCitationFiltering(unittest.TestCase):
    @patch('aiohttp.ClientSession')
    @patch('deep_research.search.check_relevance')
    def test_citation_filtering_below_threshold(self, mock_check_relevance, mock_session_cls):
        """Test that papers with citations below threshold are filtered out."""
        mock_check_relevance.return_value = True # Assume relevant
        async def run_test():
            # Setup mock session
            mock_session = MagicMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session
            
            # Mock API response with papers having different citation counts
            mock_resp = MagicMock()
            mock_resp.status = 200
            
            # Make json() awaitable
            f = asyncio.Future()
            f.set_result({
                "data": [
                    {
                        "title": "Low Citation Paper",
                        "year": 2023,
                        "venue": "Test Journal",
                        "citationCount": 2,  # Below threshold of 3
                        "authors": [{"name": "Author A"}],
                        "abstract": "This paper has only 2 citations and should be filtered out. " * 5,
                        "url": "http://example.com/paper1",
                        "openAccessPdf": None
                    },
                    {
                        "title": "Zero Citation Paper",
                        "year": 2024,
                        "venue": "Another Journal",
                        "citationCount": 0,  # Below threshold
                        "authors": [{"name": "Author B"}],
                        "abstract": "This paper has no citations and should be filtered out. " * 5,
                        "url": "http://example.com/paper2",
                        "openAccessPdf": None
                    }
                ]
            })
            mock_resp.json.return_value = f
            
            # Setup mock context manager
            mock_get_ctx = MagicMock()
            mock_session.get.return_value = mock_get_ctx
            mock_get_ctx.__aenter__.return_value = mock_resp
            
            # Run search
            semaphore = asyncio.Semaphore(1)
            results = await semantic_search("test query", semaphore, subject="test subject", limit=2)
            
            # Verify: both papers should be filtered out
            self.assertEqual(len(results), 0)
        
        asyncio.run(run_test())

    @patch('aiohttp.ClientSession')
    @patch('deep_research.search.check_relevance')
    def test_citation_filtering_above_threshold(self, mock_check_relevance, mock_session_cls):
        """Test that papers with citations at or above threshold are kept."""
        mock_check_relevance.return_value = True # Assume relevant
        async def run_test():
            # Setup mock session
            mock_session = MagicMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session
            
            # Mock API response
            mock_resp = MagicMock()
            mock_resp.status = 200
            
            f = asyncio.Future()
            f.set_result({
                "data": [
                    {
                        "title": "Good Paper",
                        "year": 2022,
                        "venue": "Top Journal",
                        "citationCount": 10,  # Above threshold
                        "authors": [{"name": "Author C"}],
                        "abstract": "This paper has 10 citations and should be kept. It contains important research findings. " * 3,
                        "url": "http://example.com/paper3",
                        "openAccessPdf": None
                    },
                    {
                        "title": "Threshold Paper",
                        "year": 2023,
                        "venue": "Good Journal",
                        "citationCount": 3,  # Exactly at threshold
                        "authors": [{"name": "Author D"}],
                        "abstract": "This paper has exactly 3 citations and should be kept. It provides valuable insights. " * 3,
                        "url": "http://example.com/paper4",
                        "openAccessPdf": None
                    }
                ]
            })
            mock_resp.json.return_value = f
            
            mock_get_ctx = MagicMock()
            mock_session.get.return_value = mock_get_ctx
            mock_get_ctx.__aenter__.return_value = mock_resp
            
            # Run search
            semaphore = asyncio.Semaphore(1)
            results = await semantic_search("test query", semaphore, subject="test subject", limit=2)
            
            # Verify: both papers should be kept
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0].title, "Good Paper")
            self.assertEqual(results[0].metadata["citations"], 10)
            self.assertEqual(results[1].title, "Threshold Paper")
            self.assertEqual(results[1].metadata["citations"], 3)
        
        asyncio.run(run_test())

    @patch('aiohttp.ClientSession')
    @patch('deep_research.search.check_relevance')
    def test_citation_filtering_mixed(self, mock_check_relevance, mock_session_cls):
        """Test filtering with mixed citation counts."""
        mock_check_relevance.return_value = True # Assume relevant
        async def run_test():
            # Setup mock session
            mock_session = MagicMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session
            
            mock_resp = MagicMock()
            mock_resp.status = 200
            
            f = asyncio.Future()
            f.set_result({
                "data": [
                    {
                        "title": "Paper 1",
                        "year": 2023,
                        "venue": "Journal A",
                        "citationCount": 1,  # Below
                        "authors": [{"name": "Author 1"}],
                        "abstract": "Abstract 1 with sufficient length to avoid fetching full text from the URL. " * 3,
                        "url": "http://example.com/1",
                        "openAccessPdf": None
                    },
                    {
                        "title": "Paper 2",
                        "year": 2023,
                        "venue": "Journal B",
                        "citationCount": 5,  # Above
                        "authors": [{"name": "Author 2"}],
                        "abstract": "Abstract 2 with sufficient length to avoid fetching full text from the URL. " * 3,
                        "url": "http://example.com/2",
                        "openAccessPdf": None
                    },
                    {
                        "title": "Paper 3",
                        "year": 2023,
                        "venue": "Journal C",
                        "citationCount": 2,  # Below
                        "authors": [{"name": "Author 3"}],
                        "abstract": "Abstract 3 with sufficient length to avoid fetching full text from the URL. " * 3,
                        "url": "http://example.com/3",
                        "openAccessPdf": None
                    },
                    {
                        "title": "Paper 4",
                        "year": 2023,
                        "venue": "Journal D",
                        "citationCount": 100,  # Above
                        "authors": [{"name": "Author 4"}],
                        "abstract": "Abstract 4 with sufficient length to avoid fetching full text from the URL. " * 3,
                        "url": "http://example.com/4",
                        "openAccessPdf": None
                    }
                ]
            })
            mock_resp.json.return_value = f
            
            mock_get_ctx = MagicMock()
            mock_session.get.return_value = mock_get_ctx
            mock_get_ctx.__aenter__.return_value = mock_resp
            
            # Run search
            semaphore = asyncio.Semaphore(1)
            results = await semantic_search("test query", semaphore, subject="test subject", limit=4)
            
            # Verify: only papers 2 and 4 should be kept
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0].title, "Paper 2")
            self.assertEqual(results[1].title, "Paper 4")
        
        asyncio.run(run_test())

    @patch('aiohttp.ClientSession')
    @patch('deep_research.search.check_relevance')
    def test_missing_citation_count(self, mock_check_relevance, mock_session_cls):
        """Test that papers with missing citationCount are filtered out (default to 0)."""
        mock_check_relevance.return_value = True # Assume relevant
        async def run_test():
            mock_session = MagicMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session
            
            mock_resp = MagicMock()
            mock_resp.status = 200
            
            f = asyncio.Future()
            f.set_result({
                "data": [
                    {
                        "title": "Paper Without Citations Field",
                        "year": 2023,
                        "venue": "Journal",
                        # citationCount is missing
                        "authors": [{"name": "Author"}],
                        "abstract": "Abstract with sufficient length to avoid fetching full text from the URL. " * 3,
                        "url": "http://example.com/paper",
                        "openAccessPdf": None
                    }
                ]
            })
            mock_resp.json.return_value = f
            
            mock_get_ctx = MagicMock()
            mock_session.get.return_value = mock_get_ctx
            mock_get_ctx.__aenter__.return_value = mock_resp
            
            semaphore = asyncio.Semaphore(1)
            results = await semantic_search("test query", semaphore, subject="test subject", limit=1)
            
            # Should be filtered out (defaults to 0)
            self.assertEqual(len(results), 0)
        
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()
