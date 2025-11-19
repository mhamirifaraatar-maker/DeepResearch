import asyncio
import unittest
from unittest.mock import MagicMock, patch
from deep_research.search import semantic_search

class TestSemanticRetry(unittest.TestCase):
    @patch('aiohttp.ClientSession')
    @patch('asyncio.sleep')
    def test_semantic_search_retry(self, mock_sleep, mock_session_cls):
        async def run_test():
            # Setup mock response
            mock_session = MagicMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session
            
            # Mock responses: 429, 429, 200 (Success)
            mock_resp_429 = MagicMock()
            mock_resp_429.status = 429
            
            mock_resp_200 = MagicMock()
            mock_resp_200.status = 200
            # Make json() awaitable
            f = asyncio.Future()
            f.set_result({
                "data": [
                    {
                        "title": "Test Paper",
                        "year": 2023,
                        "venue": "Test Journal",
                        "citationCount": 10,
                        "authors": [{"name": "Author One"}],
                        "openAccessPdf": {"url": "http://example.com/pdf"}
                    }
                ]
            })
            mock_resp_200.json.return_value = f
            
            # Configure the get context manager to return different responses
            mock_get_ctx = MagicMock()
            mock_session.get.return_value = mock_get_ctx
            
            # Side effect for __aenter__ to return 429 twice then 200
            mock_get_ctx.__aenter__.side_effect = [mock_resp_429, mock_resp_429, mock_resp_200]
            
            # Run the function
            semaphore = asyncio.Semaphore(1)
            results = await semantic_search("test query", semaphore, limit=1)
            
            # Verify results
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].title, "Test Paper")
            
            # Verify retries happened (called 3 times)
            self.assertEqual(mock_session.get.call_count, 3)
            
        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
