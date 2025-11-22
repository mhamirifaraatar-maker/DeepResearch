import asyncio
import unittest
from unittest.mock import MagicMock, patch
from deep_research.search import semantic_search

class TestSemanticContent(unittest.TestCase):
    @patch('aiohttp.ClientSession')
    @patch('deep_research.search.check_relevance')
    @patch('deep_research.search.fetch_text')
    def test_semantic_search_fallback(self, mock_fetch_text, mock_check_relevance, mock_session_cls):
        mock_check_relevance.return_value = True
        async def run_test():
            # Mock fetch_text to return full content
            mock_fetch_text.return_value = "This is the full text of the paper fetched from the URL. It is long enough to be considered quality content."
            
            # Setup mock session for API call
            mock_session = MagicMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session
            
            # Mock API response: Paper with no abstract but with URL
            mock_resp = MagicMock()
            mock_resp.status = 200
            
            # Make json() awaitable
            f = asyncio.Future()
            f.set_result({
                "data": [
                    {
                        "title": "Paper Without Abstract",
                        "year": 2024,
                        "venue": "Test Venue",
                        "citationCount": 5,
                        "authors": [{"name": "Author A"}],
                        "abstract": None, # Missing abstract
                        "openAccessPdf": {"url": "http://example.com/paper.pdf"},
                        "url": "http://example.com/paper"
                    }
                ]
            })
            mock_resp.json.return_value = f
            
            mock_session.get.return_value.__aenter__.return_value = mock_resp
            
            # Run search
            semaphore = asyncio.Semaphore(1)
            results = await semantic_search("query", semaphore, subject="test subject", limit=1)
            
            # Verify
            self.assertEqual(len(results), 1)
            snippet = results[0]
            self.assertEqual(snippet.title, "Paper Without Abstract")
            # Should have used the fetched text
            self.assertEqual(snippet.body, "This is the full text of the paper fetched from the URL. It is long enough to be considered quality content.")
            
            # Verify fetch_text was called with correct URL
            mock_fetch_text.assert_called_with(mock_session, "http://example.com/paper.pdf")

        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
