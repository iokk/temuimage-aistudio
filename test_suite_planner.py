import unittest


class SuitePlannerModelTests(unittest.TestCase):
    def test_temu_standard_profile_describes_default_eight_image_suite(self):
        from suite_planner import TEMU_STANDARD_PROFILE

        self.assertEqual(TEMU_STANDARD_PROFILE["id"], "temu-standard")
        self.assertEqual(TEMU_STANDARD_PROFILE["default_count"], 8)
        self.assertEqual(TEMU_STANDARD_PROFILE["max_count"], 10)
        self.assertFalse(TEMU_STANDARD_PROFILE["default_logo_enabled"])
        self.assertEqual(
            TEMU_STANDARD_PROFILE["default_type_counts"],
            {
                "main-front": 1,
                "back-side": 1,
                "detail": 3,
                "scene": 1,
                "dimension": 1,
                "selling-point": 1,
            },
        )

    def test_temu_standard_profile_and_nested_counts_are_immutable(self):
        from suite_planner import TEMU_STANDARD_PROFILE

        with self.assertRaises(TypeError):
            TEMU_STANDARD_PROFILE["default_count"] = 10
        with self.assertRaises(TypeError):
            TEMU_STANDARD_PROFILE["default_type_counts"]["detail"] = 1

        self.assertEqual(TEMU_STANDARD_PROFILE["default_count"], 8)
        self.assertEqual(TEMU_STANDARD_PROFILE["default_type_counts"]["detail"], 3)

    def test_default_counts_sum_to_requested_target_and_never_exceed_ten(self):
        from suite_planner import build_default_type_counts

        self.assertEqual(sum(build_default_type_counts().values()), 8)
        self.assertEqual(sum(build_default_type_counts(10).values()), 10)
        with self.assertRaises(ValueError):
            build_default_type_counts(11)

    def test_normalize_type_counts_preserves_known_counts_and_fills_to_target(self):
        from suite_planner import normalize_type_counts

        counts = normalize_type_counts({"main-front": 1, "detail": 2}, 8)

        self.assertEqual(counts["main-front"], 1)
        self.assertEqual(counts["detail"], 2)
        self.assertEqual(sum(counts.values()), 8)
        self.assertEqual(
            set(counts),
            {
                "main-front",
                "back-side",
                "detail",
                "scene",
                "dimension",
                "selling-point",
                "package",
                "compare",
                "steps",
            },
        )

    def test_validate_suite_draft_accepts_one_to_fourteen_references(self):
        from suite_planner import build_default_type_counts, validate_suite_draft

        for reference_count in (1, 14):
            draft = {
                "target_count": 8,
                "assets": [{}] * reference_count,
                "selected_type_counts": build_default_type_counts(),
            }
            self.assertEqual(validate_suite_draft(draft), [])

    def test_validate_suite_draft_reports_explicit_count_errors(self):
        from suite_planner import validate_suite_draft

        errors = validate_suite_draft(
            {
                "target_count": 11,
                "assets": [],
                "selected_type_counts": {"main-front": 1},
            }
        )

        self.assertIn("target_count must be between 1 and 10", errors)
        self.assertIn("assets must contain between 1 and 14 reference images", errors)
        self.assertIn("selected_type_counts must sum to target_count", errors)


if __name__ == "__main__":
    unittest.main()
