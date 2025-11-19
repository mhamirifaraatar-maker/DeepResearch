import unittest
from deep_research.processing import compress_text, is_quality_page

class TestQualification(unittest.TestCase):
    def test_compress_text_plain(self):
        text = "This is a plain text abstract. It should be preserved."
        result = compress_text(text, 100)
        self.assertEqual(result, text)

    def test_compress_text_html(self):
        html = "<html><body><p>This is HTML content.</p></body></html>"
        result = compress_text(html, 100)
        self.assertEqual(result, "This is HTML content.")

    def test_is_quality_page_academic(self):
        # Short abstract (e.g. 150 chars)
        text = "This is a short abstract for an academic paper. " * 4 
        self.assertTrue(len(text) > 100)
        self.assertTrue(len(text) < 500)
        
        # Should pass for semantic_scholar
        self.assertTrue(is_quality_page(text, "semantic_scholar"))
        
        # Should fail for web
        self.assertFalse(is_quality_page(text, "web"))

    def test_is_quality_page_hype(self):
        text = "Buy now! Limited offer! " * 20
        self.assertFalse(is_quality_page(text, "web"))
        # Hype check applies to all? The code says:
        # if source_type == "semantic_scholar": return len >= 100
        # So hype check is skipped for semantic_scholar if it returns early.
        # Let's verify that behavior.
        self.assertTrue(is_quality_page(text, "semantic_scholar")) 

if __name__ == '__main__':
    unittest.main()
