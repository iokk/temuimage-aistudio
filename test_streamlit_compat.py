import ast
import unittest
from pathlib import Path


class StreamlitCompatibilityTests(unittest.TestCase):
    def test_app_uses_supported_streamlit_width_keyword(self):
        tree = ast.parse(Path("app.py").read_text(encoding="utf-8"))
        deprecated_lines = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and any(
                keyword.arg == "use_container_width" for keyword in node.keywords
            )
        ]

        self.assertEqual(deprecated_lines, [])


if __name__ == "__main__":
    unittest.main()
