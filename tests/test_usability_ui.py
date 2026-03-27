from __future__ import annotations

import unittest

from temu_core.usability_ui import (
    build_core_function_nav,
    build_page_switch_targets,
    get_thumbnail_sizes,
)


class UsabilityUITest(unittest.TestCase):
    def test_core_function_nav_always_returns_four_primary_features(self):
        items = build_core_function_nav()
        self.assertEqual(
            [item["key"] for item in items], ["combo", "smart", "title", "translate"]
        )

    def test_page_switch_targets_exclude_current_page(self):
        targets = build_page_switch_targets("批量出图")
        labels = [item["label"] for item in targets]
        self.assertNotIn("批量出图", labels)
        self.assertIn("快速出图", labels)

    def test_thumbnail_sizes_are_compact(self):
        size_map = get_thumbnail_sizes()
        self.assertLessEqual(size_map["combo"], 96)
        self.assertLessEqual(size_map["smart"], 96)
        self.assertLessEqual(size_map["title"], 80)
        self.assertLessEqual(size_map["translate"], 96)


if __name__ == "__main__":
    unittest.main()
