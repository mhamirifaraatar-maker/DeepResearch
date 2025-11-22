import asyncio
import unittest
from unittest.mock import MagicMock, patch
from deep_research.search import check_relevance

class TestRelevance(unittest.TestCase):
    @patch('deep_research.search.gemini_complete')
    def test_check_relevance_yes(self, mock_gemini):
        """Test that check_relevance returns True when LLM says YES."""
        async def run_test():
            mock_gemini.return_value = "YES"
            
            result = await check_relevance("topic", "title", "abstract")
            self.assertTrue(result)
            
            # Verify prompt contains topic, title, abstract
            args, _ = mock_gemini.call_args
            prompt = args[0]
            self.assertIn("topic", prompt)
            self.assertIn("title", prompt)
            self.assertIn("abstract", prompt)
            
        asyncio.run(run_test())

    @patch('deep_research.search.gemini_complete')
    def test_check_relevance_no(self, mock_gemini):
        """Test that check_relevance returns False when LLM says NO."""
        async def run_test():
            mock_gemini.return_value = "NO"
            
            result = await check_relevance("topic", "title", "abstract")
            self.assertFalse(result)
            
        asyncio.run(run_test())

    @patch('deep_research.search.gemini_complete')
    def test_check_relevance_empty_abstract(self, mock_gemini):
        """Test that check_relevance returns False for empty abstract."""
        async def run_test():
            result = await check_relevance("topic", "title", "")
            self.assertFalse(result)
            mock_gemini.assert_not_called()
            
        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
