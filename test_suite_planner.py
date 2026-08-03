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


class SuitePlannerRuleTests(unittest.TestCase):
    def _draft(self, type_counts, assets=None, **overrides):
        draft = {
            "target_count": sum(type_counts.values()),
            "assets": assets
            if assets is not None
            else [
                {"id": "front-1", "path": "front.jpg", "role": "front"},
                {"id": "detail-1", "path": "detail.jpg", "role": "detail"},
            ],
            "selected_type_counts": type_counts,
        }
        draft.update(overrides)
        return draft

    def test_normalize_assets_assigns_stable_ids_and_known_roles(self):
        from suite_planner import normalize_assets

        assets = normalize_assets(
            [
                {"path": "front.jpg", "role": "Front", "is_primary": True},
                {"id": "front-1", "path": "duplicate.jpg", "role": "unsupported"},
            ]
        )

        self.assertEqual([asset["id"] for asset in assets], ["asset-01", "front-1"])
        self.assertEqual([asset["role"] for asset in assets], ["front", "unknown"])
        self.assertTrue(assets[0]["is_primary"])

    def test_missing_back_evidence_is_safely_replaced_with_reason(self):
        from suite_planner import plan_suite

        plan = plan_suite(self._draft({"main-front": 1, "back-side": 1}))
        items = plan["plan_items"]

        self.assertEqual(len(items), 2)
        self.assertNotIn("back-side", [item["type_key"] for item in items])
        replacement = next(item for item in items if item["replacement_reason"])
        self.assertIn("back", replacement["replacement_reason"].lower())
        self.assertNotEqual(replacement["type_key"], "back-side")

    def test_missing_dimension_data_replaces_dimension_with_reason(self):
        from suite_planner import plan_suite

        plan = plan_suite(self._draft({"dimension": 1}))
        item = plan["plan_items"][0]

        self.assertNotEqual(item["type_key"], "dimension")
        self.assertIn("dimension", item["replacement_reason"].lower())

    def test_insufficient_detail_evidence_does_not_invent_extra_detail_items(self):
        from suite_planner import plan_suite

        plan = plan_suite(self._draft({"detail": 3}))
        items = plan["plan_items"]

        self.assertEqual(sum(item["type_key"] == "detail" for item in items), 1)
        self.assertEqual(len(items), 3)
        self.assertTrue(all(item["replacement_reason"] for item in items[1:]))

    def test_each_plan_item_has_one_to_three_relevant_references(self):
        from suite_planner import plan_suite, select_reference_assets

        assets = [
            {"id": "front-1", "path": "front.jpg", "role": "front"},
            {"id": "detail-1", "path": "detail-1.jpg", "role": "detail"},
            {"id": "detail-2", "path": "detail-2.jpg", "role": "detail"},
            {"id": "detail-3", "path": "detail-3.jpg", "role": "detail"},
            {"id": "back-1", "path": "back.jpg", "role": "back"},
        ]
        plan = plan_suite(
            self._draft(
                {"main-front": 1, "back-side": 1, "detail": 3, "scene": 1},
                assets,
            )
        )

        for item in plan["plan_items"]:
            self.assertGreaterEqual(len(item["reference_asset_ids"]), 1)
            self.assertLessEqual(len(item["reference_asset_ids"]), 3)
            self.assertEqual(
                item["reference_asset_ids"],
                select_reference_assets(item["type_key"], assets, limit=3),
            )

    def test_repeated_type_items_rotate_theme_shot_and_composition(self):
        from suite_planner import plan_suite

        assets = [
            {"id": f"detail-{index}", "path": f"detail-{index}.jpg", "role": "detail"}
            for index in range(3)
        ]
        items = plan_suite(self._draft({"detail": 3}, assets))["plan_items"]

        for field in ("theme", "scene", "shot", "composition"):
            self.assertEqual(len({item[field] for item in items}), 3)

    def test_invalid_ai_result_falls_back_to_deterministic_safe_plan(self):
        from suite_planner import plan_suite

        draft = self._draft({"main-front": 1, "detail": 1})
        ai_plan = {
            "plan_items": [
                {
                    "type_key": "main-front",
                    "reference_asset_ids": ["missing-asset"],
                    "scene": "studio",
                    "composition": "centered",
                },
                {
                    "type_key": "detail",
                    "reference_asset_ids": ["detail-1"],
                    "scene": "",
                    "composition": "macro",
                },
            ]
        }

        plan = plan_suite(draft, ai_plan=ai_plan)

        self.assertFalse(plan["used_ai_plan"])
        self.assertEqual(
            [item["reference_asset_ids"] for item in plan["plan_items"]],
            [["front-1", "detail-1"], ["detail-1"]],
        )

    def test_plan_suite_rejects_empty_or_unresolvable_assets(self):
        from suite_planner import plan_suite

        for assets in (
            [],
            [None],
            [{}],
            [{"path": "package.jpg", "role": "package"}],
        ):
            with self.subTest(assets=assets):
                with self.assertRaisesRegex(ValueError, "assets"):
                    plan_suite(self._draft({"scene": 1}, assets))

    def test_placeholder_whitespace_and_unknown_dimensions_are_not_evidence(self):
        from suite_planner import plan_suite

        invalid_dimension_data = (
            {"width": "TBD"},
            {"width": "   "},
            {"marketing_size": 12},
        )
        for dimension_data in invalid_dimension_data:
            with self.subTest(dimension_data=dimension_data):
                item = plan_suite(
                    self._draft({"dimension": 1}, dimension_data=dimension_data)
                )["plan_items"][0]
                self.assertNotEqual(item["type_key"], "dimension")
                self.assertIn("dimension", item["replacement_reason"].lower())

    def test_recognized_positive_dimensions_retain_dimension_item(self):
        from suite_planner import plan_suite

        valid_dimension_data = (
            {"width": 12},
            {"height_cm": "12.5 cm"},
            {"depth": {"value": 8, "unit": "in"}},
        )
        for dimension_data in valid_dimension_data:
            with self.subTest(dimension_data=dimension_data):
                item = plan_suite(
                    self._draft({"dimension": 1}, dimension_data=dimension_data)
                )["plan_items"][0]
                self.assertEqual(item["type_key"], "dimension")
                self.assertEqual(item["replacement_reason"], "")

    def test_near_duplicate_ai_variations_fall_back_to_deterministic_plan(self):
        from suite_planner import plan_suite

        assets = [
            {"id": "detail-1", "path": "detail-1.jpg", "role": "detail"},
            {"id": "detail-2", "path": "detail-2.jpg", "role": "detail"},
        ]
        ai_plan = {
            "plan_items": [
                {
                    "type_key": "detail",
                    "reference_asset_ids": ["detail-1"],
                    "theme": "Material focus",
                    "scene": "Studio",
                    "shot": "Macro close-up",
                    "composition": "Centered",
                },
                {
                    "type_key": "detail",
                    "reference_asset_ids": ["detail-2"],
                    "theme": " material focus! ",
                    "scene": "studio!",
                    "shot": "macro close up.",
                    "composition": "CENTERED.",
                },
            ]
        }

        plan = plan_suite(self._draft({"detail": 2}, assets), ai_plan=ai_plan)

        self.assertFalse(plan["used_ai_plan"])

    def test_valid_differentiated_ai_plan_is_accepted(self):
        from suite_planner import plan_suite

        assets = [
            {"id": "detail-1", "path": "detail-1.jpg", "role": "detail"},
            {"id": "detail-2", "path": "detail-2.jpg", "role": "detail"},
        ]
        ai_items = [
            {
                "type_key": "detail",
                "reference_asset_ids": ["detail-1"],
                "theme": "Material texture",
                "scene": "Neutral tabletop studio",
                "shot": "Macro surface close-up",
                "composition": "Diagonal crop",
            },
            {
                "type_key": "detail",
                "reference_asset_ids": ["detail-2"],
                "theme": "Functional construction",
                "scene": "Soft daylight workshop",
                "shot": "Three-quarter feature view",
                "composition": "Offset framing",
            },
        ]

        plan = plan_suite(
            self._draft({"detail": 2}, assets),
            ai_plan={"plan_items": ai_items},
        )

        self.assertTrue(plan["used_ai_plan"])
        self.assertEqual(
            [item["scene"] for item in plan["plan_items"]],
            ["Neutral tabletop studio", "Soft daylight workshop"],
        )

    def test_plan_returns_normalized_assets_that_resolve_generated_ids(self):
        from suite_planner import plan_suite

        plan = plan_suite(
            self._draft(
                {"main-front": 1},
                [{"path": "front.jpg", "role": "front"}],
            )
        )

        asset_ids = {asset["id"] for asset in plan["assets"]}
        reference_ids = set(plan["plan_items"][0]["reference_asset_ids"])
        self.assertEqual(asset_ids, {"asset-01"})
        self.assertEqual(reference_ids, {"asset-01"})
        self.assertTrue(reference_ids.issubset(asset_ids))


class SuitePromptTests(unittest.TestCase):
    def _draft(self, type_counts, assets=None, **overrides):
        draft = {
            "target_count": sum(type_counts.values()),
            "assets": assets
            if assets is not None
            else [
                {"id": "front-1", "path": "front.jpg", "role": "front"},
                {"id": "detail-1", "path": "detail.jpg", "role": "detail"},
            ],
            "selected_type_counts": type_counts,
            "product_identity": "stainless steel travel mug",
            "target_language": "Brazilian Portuguese",
        }
        draft.update(overrides)
        return draft

    def test_compose_prompt_uses_the_required_semantic_order(self):
        from suite_planner import compose_suite_prompt, plan_suite

        draft = self._draft({"main-front": 1})
        item = plan_suite(draft)["plan_items"][0]
        item.update(
            {
                "scene": "bright kitchen counter",
                "shot": "three-quarter product view",
                "composition": "centered framing",
                "lighting": "soft daylight",
                "copy_enabled": True,
                "copy_text": "Keeps drinks warm",
            }
        )

        prompt = compose_suite_prompt(item, draft, draft["assets"])

        ordered_sections = (
            "Product identity:",
            "Image type:",
            "Scene, shot, composition, and lighting:",
            "User copy:",
            "Target-language emphasis:",
            "Reference material roles:",
            "Type requirements:",
            "Platform requirements:",
            "Truthfulness requirements:",
        )
        positions = [prompt.index(section) for section in ordered_sections]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("stainless steel travel mug", prompt)
        self.assertIn("Brazilian Portuguese", prompt)
        self.assertIn("front", prompt)
        self.assertIn("1600x1600", prompt)

    def test_empty_copy_is_omitted_and_logo_is_disabled_by_default(self):
        from suite_planner import compose_suite_prompt, plan_suite

        draft = self._draft({"detail": 1})
        item = plan_suite(draft)["plan_items"][0]
        item.update({"copy_enabled": True, "copy_text": "   "})

        prompt = compose_suite_prompt(item, draft, draft["assets"])

        self.assertNotIn("User copy:", prompt)
        self.assertIn("Do not add a logo", prompt)

    def test_finalized_plan_freezes_prompts_and_uses_freeform_target_language(self):
        from suite_planner import finalize_suite_plan

        plan = finalize_suite_plan(
            self._draft(
                {"main-front": 1, "detail": 1},
                target_language="Klingon for all visible text",
            )
        )

        self.assertEqual(len(plan["plan_items"]), 2)
        self.assertTrue(all(item["final_prompt"] for item in plan["plan_items"]))
        self.assertTrue(
            all("Klingon for all visible text" in item["final_prompt"] for item in plan["plan_items"])
        )

    def test_finalized_plan_replaces_unsupported_dimension_and_removes_placeholders(self):
        from suite_planner import finalize_suite_plan

        plan = finalize_suite_plan(
            self._draft(
                {"dimension": 1},
                dimension_data={"width": "XX cm"},
                user_instruction="Use XX inch labels only when available.",
            )
        )

        self.assertNotIn("dimension", [item["type_key"] for item in plan["plan_items"]])
        final_prompts = [item["final_prompt"] for item in plan["plan_items"]]
        self.assertTrue(all("XX cm" not in prompt for prompt in final_prompts))
        self.assertTrue(all("XX inch" not in prompt for prompt in final_prompts))

    def test_dimension_prompt_includes_only_verified_dimension_values(self):
        from suite_planner import finalize_suite_plan

        plan = finalize_suite_plan(
            self._draft(
                {"dimension": 1},
                dimension_data={"depth": {"value": 8, "unit": "in"}},
            )
        )

        item = plan["plan_items"][0]
        self.assertEqual(item["type_key"], "dimension")
        self.assertIn("depth 8 in", item["final_prompt"])


if __name__ == "__main__":
    unittest.main()
