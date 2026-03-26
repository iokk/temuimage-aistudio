from __future__ import annotations

import unittest

from temu_core.relay_first_logic import (
    build_fallback_anchor,
    analyze_product_with_text_client,
    generate_requirements_with_text_client,
    generate_en_copy_with_text_client,
)


class FakeTextClient:
    def __init__(self, text: str = ""):
        self.text = text
        self.calls = []

    def generate_text(
        self, refs, prompt: str, max_tokens: int = 1800, temperature: float = 0.2
    ):
        self.calls.append((refs, prompt, max_tokens, temperature))
        return self.text

    def parse_json_response(self, text: str, default):
        import json

        try:
            return json.loads(text)
        except Exception:
            return default


class RelayFirstLogicTest(unittest.TestCase):
    def test_build_fallback_anchor_uses_user_input(self):
        anchor = build_fallback_anchor("Bottle", "Steel vacuum cup")
        self.assertEqual(anchor["product_name_en"], "Bottle")
        self.assertIn("Steel", anchor["visual_attrs"][0])

    def test_analyze_product_with_text_client_parses_json(self):
        client = FakeTextClient(
            '{"product_name_en":"Bottle","product_name_zh":"水杯","primary_category":"Drinkware","visual_attrs":["steel","portable"],"confidence":0.8}'
        )
        result = analyze_product_with_text_client(
            client,
            [object()],
            name="Bottle",
            detail="Steel cup",
            prompt_template="Analyze {product_name} {product_detail}",
        )
        self.assertEqual(result["primary_category"], "Drinkware")
        self.assertEqual(result["product_name_zh"], "水杯")

    def test_generate_requirements_with_text_client_returns_list(self):
        client = FakeTextClient(
            '[{"type_key":"hero","type_name":"主图","index":1,"topic":"卖点"}]'
        )
        templates = {"hero": {"name": "主图"}}
        result = generate_requirements_with_text_client(
            client,
            {
                "product_name_zh": "水杯",
                "primary_category": "Drinkware",
                "visual_attrs": ["steel"],
            },
            {"hero": 1},
            templates,
            "Req {product_name} {types}",
            tags=["保温"],
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type_key"], "hero")

    def test_generate_en_copy_with_text_client_maps_fields(self):
        client = FakeTextClient(
            '[{"type_key":"hero","index":1,"headline":"HOT SALE","subline":"STEEL CUP","badge":"BPA FREE"}]'
        )
        requirements = [
            {"type_key": "hero", "index": 1, "type_name": "主图", "topic": "卖点"}
        ]
        updated = generate_en_copy_with_text_client(
            client,
            {"product_name_en": "Bottle", "primary_category": "Drinkware"},
            requirements,
            "Copy {product_name} {requirements}",
        )
        self.assertEqual(updated[0]["headline"], "HOT SALE")
        self.assertEqual(updated[0]["badge"], "BPA FREE")


if __name__ == "__main__":
    unittest.main()
