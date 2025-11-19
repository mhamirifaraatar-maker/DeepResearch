import re
import unittest

def parse_line(line):
    prefix = ""
    if line.startswith("* "):
        prefix = "[BULLET] "
        line = line[2:]

    tokens = re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", line)
    results = []
    for tok in tokens:
        if not tok: continue
        if tok.startswith("**") and tok.endswith("**") and len(tok) > 4:
            results.append(f"[BOLD]{tok[2:-2]}[/BOLD]")
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            results.append(f"[ITALIC]{tok[1:-1]}[/ITALIC]")
        else:
            # Simulate the fix in utils.py
            clean_tok = tok.replace(":*", ":")
            results.append(clean_tok)
    return prefix + "".join(results)

class TestDocxParsing(unittest.TestCase):
    def test_simple_italic(self):
        self.assertEqual(parse_line("*Italic*"), "[ITALIC]Italic[/ITALIC]")

    def test_simple_bold(self):
        self.assertEqual(parse_line("**Bold**"), "[BOLD]Bold[/BOLD]")

    def test_mixed(self):
        self.assertEqual(parse_line("*Italic* and **Bold**"), "[ITALIC]Italic[/ITALIC] and [BOLD]Bold[/BOLD]")

    def test_colon_inside(self):
        self.assertEqual(parse_line("*Title:*"), "[ITALIC]Title:[/ITALIC]")

        # "foo:**".replace(":*", ":") -> "foo:*"
        # Wait, logic check:
        # "*Title:**" splits into ["*Title:*", "*"] if regex matches *Title:*?
        # Regex is (\*\*[^*]+\*\*|\*[^*]+\*)
        # *Title:** -> *Title:* matches *[^*]+* ? No, * matches [^*].
        # *Title:** -> *Title:* is valid match for *...*?
        # *Title:* matches. Remaining is *.
        # So tokens: ["*Title:*", "*"]
        # "*Title:*" -> [ITALIC]Title:[/ITALIC]
        # "*" -> replace(":*", ":") -> "*"
        # Result: [ITALIC]Title:[/ITALIC]*
        self.assertEqual(parse_line("*Title:**"), "[ITALIC]Title:[/ITALIC]*")

    def test_nested_ish(self):
        # **Title:** -> [BOLD]Title:[/BOLD]
        self.assertEqual(parse_line("**Title:**"), "[BOLD]Title:[/BOLD]")

    def test_bullet_bold(self):
        # Problem: * **Bold**
        # Should be detected as bullet and parsed as bold
        self.assertEqual(parse_line("* **Bold**"), "[BULLET] [BOLD]Bold[/BOLD]")

    def test_bullet_normal(self):
        self.assertEqual(parse_line("* Normal item"), "[BULLET] Normal item")

if __name__ == '__main__':
    unittest.main()
