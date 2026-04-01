from __future__ import annotations

from pathlib import Path
import importlib.util
import sys
from types import ModuleType
from types import SimpleNamespace
import unittest


MODULE_PATH = Path("apps/api/task_execution.py")


class _FakeImageCall(dict):
    refs: list[object]
    prompt: str
    aspect: str
    size: str


class _FakeImageClient:
    def __init__(self, total_tokens: int = 7):
        self._total_tokens = total_tokens
        self.generate_calls: list[_FakeImageCall] = []

    def generate_image(self, refs, prompt: str, aspect: str = "1:1", size: str = "1K"):
        self.generate_calls.append(
            _FakeImageCall(
                {
                    "refs": list(refs or []),
                    "prompt": prompt,
                    "aspect": aspect,
                    "size": size,
                }
            )
        )
        return object()

    def translate_image(
        self,
        image,
        translated_lines,
        *,
        source_lines=None,
        preserve_ratio=True,
        size="1K",
        remove_overlay_text=True,
    ):
        del (
            image,
            translated_lines,
            source_lines,
            preserve_ratio,
            size,
            remove_overlay_text,
        )
        return object()

    def get_tokens_used(self) -> int:
        return self._total_tokens


class _FakeTextClient:
    def __init__(self, total_tokens: int = 5):
        self._total_tokens = total_tokens

    def translate_lines(
        self,
        lines,
        source_lang: str = "auto",
        target_lang: str = "English",
        style_hint: str = "Literal",
        avoid_terms=None,
        enforce_english: bool = False,
        max_attempts: int = 1,
    ) -> list[str]:
        del (
            source_lang,
            target_lang,
            style_hint,
            avoid_terms,
            enforce_english,
            max_attempts,
        )
        return [
            f"EN:{str(line).strip()}" for line in (lines or []) if str(line).strip()
        ]

    def extract_and_translate_image_text(
        self,
        image,
        source_lang="auto",
        target_lang="English",
        style_hint="Literal",
        avoid_terms=None,
        enforce_english=False,
        max_attempts=1,
    ):
        del (
            image,
            source_lang,
            target_lang,
            style_hint,
            avoid_terms,
            enforce_english,
            max_attempts,
        )
        return {
            "language": "Chinese",
            "source_lines": ["原文一", "原文二"],
            "translated_lines": ["English line 1", "English line 2"],
        }

    def get_tokens_used(self) -> int:
        return self._total_tokens

    def get_last_error(self) -> str:
        return ""


def _analyze_product_with_text_client(*, images, product_name, text_client):
    del product_name, text_client
    return {
        "primary_category": "portable blender",
        "product_name_en": "Portable Blender",
        "product_name_zh": "便携搅拌机",
        "visual_attrs": ["white studio", "usb portable", f"refs={len(images)}"],
        "confidence": 0.92,
    }


def _install_stub_modules() -> None:
    system_config = ModuleType("apps.api.core.system_config")
    setattr(
        system_config,
        "get_system_execution_config",
        lambda: SimpleNamespace(
            title_model="title-model",
            translate_provider="gemini",
            translate_image_model="translate-image-model",
            translate_analysis_model="translate-analysis-model",
            quick_image_model="quick-image-model",
            batch_image_model="batch-image-model",
            relay_api_base="",
            relay_api_key="",
            relay_default_image_model="",
            gemini_api_key="gemini-key",
        ),
    )

    personal_config = ModuleType("apps.api.core.personal_config")
    setattr(
        personal_config,
        "get_effective_execution_config_for_user",
        lambda user_id: system_config.get_system_execution_config(),
    )

    ai_clients = ModuleType("temu_core.ai_clients")
    setattr(ai_clients, "build_image_client", lambda **kwargs: _FakeImageClient())
    setattr(ai_clients, "build_text_client", lambda **kwargs: _FakeTextClient())
    setattr(ai_clients, "image_to_data_url", lambda image: "data:image/png;base64,fake")
    setattr(ai_clients, "image_from_data_url", lambda data_url: {"decoded": data_url})

    provider_capabilities = ModuleType("temu_core.provider_capabilities")
    setattr(
        provider_capabilities,
        "get_translation_provider_message",
        lambda *args, **kwargs: "",
    )
    setattr(provider_capabilities, "model_supports", lambda *args, **kwargs: True)

    provider_precheck = ModuleType("temu_core.provider_precheck")
    setattr(
        provider_precheck, "describe_capability_reasons", lambda *args, **kwargs: []
    )

    title_logic = ModuleType("temu_core.title_logic")
    setattr(
        title_logic,
        "generate_compliant_titles_or_raise",
        lambda **kwargs: (
            ["stub title"],
            [],
        ),
    )

    relay_first_logic = ModuleType("temu_core.relay_first_logic")
    setattr(
        relay_first_logic,
        "analyze_product_with_text_client",
        _analyze_product_with_text_client,
    )

    sys.modules["apps.api.core.system_config"] = system_config
    sys.modules["apps.api.core.personal_config"] = personal_config
    sys.modules["temu_core.ai_clients"] = ai_clients
    sys.modules["temu_core.provider_capabilities"] = provider_capabilities
    sys.modules["temu_core.provider_precheck"] = provider_precheck
    sys.modules["temu_core.title_logic"] = title_logic
    sys.modules["temu_core.relay_first_logic"] = relay_first_logic


def _load_task_execution_module(module_name: str):
    _install_stub_modules()
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TaskExecutionResilienceTest(unittest.TestCase):
    def test_execution_config_prefers_owner_scoped_personal_config(self):
        module = _load_task_execution_module("task_execution_personal_config_test")
        module.get_effective_execution_config_for_user = lambda user_id: {
            "user_id": user_id,
            "source": "personal",
        }
        module.get_system_execution_config = lambda: {"source": "system"}

        result = module._get_execution_config({"ownerId": "user-personal-1"})

        self.assertEqual(result["source"], "personal")
        self.assertEqual(result["user_id"], "user-personal-1")

    def test_optional_titles_forward_owner_id(self):
        module = _load_task_execution_module(
            "task_execution_optional_titles_owner_test"
        )
        payloads: list[dict[str, object]] = []
        module.execute_title_task = lambda payload: (
            payloads.append(payload)
            or {
                "titles": ["stub title"],
                "warnings": [],
                "tokens_used": 3,
            }
        )

        titles, warnings, tokens_used, error = module._generate_optional_titles(
            product_info="portable blender",
            extra_requirements="clean marketplace",
            count=1,
            owner_id="user-personal-1",
        )

        self.assertEqual(titles, ["stub title"])
        self.assertEqual(warnings, [])
        self.assertEqual(tokens_used, 3)
        self.assertEqual(error, "")
        self.assertEqual(payloads[0]["ownerId"], "user-personal-1")

    def test_title_provider_prefers_relay_for_non_gemini_title_model(self):
        module = _load_task_execution_module("task_execution_title_provider_test")

        provider = module._resolve_title_provider(
            SimpleNamespace(
                title_model="seedream-5.0",
                gemini_api_key="gemini-key",
                relay_api_key="relay-key",
                relay_api_base="https://relay.example/v1",
            )
        )

        self.assertEqual(provider, "relay")

    def test_quick_task_keeps_images_when_title_generation_fails(self):
        module = _load_task_execution_module("task_execution_quick_test")
        setattr(
            module,
            "execute_title_task",
            lambda payload: (_ for _ in ()).throw(
                ValueError("title credentials missing")
            ),
        )

        result = module.execute_quick_task(
            {
                "productInfo": "portable blender",
                "imageType": "main_visual",
                "count": 2,
                "includeTitles": True,
            }
        )

        self.assertEqual(result["source"], "execution")
        self.assertEqual(len(result["outputs"]), 2)
        self.assertTrue(
            all(item["status"] == "completed" for item in result["outputs"])
        )
        self.assertEqual(result["titles"], [])
        self.assertTrue(result["title_warnings"])
        self.assertIn("已保留图片结果", result["title_warnings"][0])
        self.assertTrue(any("已保留图片结果" in item for item in result["errors"]))

    def test_batch_task_keeps_images_when_title_generation_fails(self):
        module = _load_task_execution_module("task_execution_batch_test")
        setattr(
            module,
            "execute_title_task",
            lambda payload: (_ for _ in ()).throw(
                ValueError("title model unavailable")
            ),
        )

        result = module.execute_batch_task(
            {
                "productInfo": "portable blender",
                "selectedTypes": ["main_visual", "detail_card"],
                "includeTitles": True,
            }
        )

        self.assertEqual(result["source"], "execution")
        self.assertEqual(len(result["outputs"]), 2)
        self.assertTrue(
            all(item["status"] == "completed" for item in result["outputs"])
        )
        self.assertEqual(result["titles"], [])
        self.assertTrue(result["title_warnings"])
        self.assertTrue(any("已保留图片结果" in item for item in result["errors"]))
        self.assertTrue(all(item.get("title", "") == "" for item in result["outputs"]))

    def test_title_task_uses_uploaded_images_as_bounded_refs(self):
        module = _load_task_execution_module("task_execution_title_refs_test")
        captured: dict[str, object] = {}
        module._resolve_title_provider = lambda config: "gemini"

        def generate_titles_or_raise(**kwargs):
            captured.update(kwargs)
            return ["EN title 1", "ZH 标题 1", "EN title 2", "ZH 标题 2"], []

        module.generate_compliant_titles_or_raise = generate_titles_or_raise

        result = module.execute_title_task(
            {
                "uploadItems": [
                    {
                        "id": f"img-{index + 1}",
                        "rawName": f"ref-{index + 1}.png",
                        "mimeType": "image/png",
                        "sizeBytes": 1024,
                        "imageDataUrl": f"data:image/png;base64,{index + 1}",
                    }
                    for index in range(6)
                ],
                "productInfo": "portable blender",
                "extraRequirements": "highlight portability",
                "templateKey": "image_analysis",
                "count": 4,
                "projectId": "project_1",
                "projectName": "Default Workspace",
                "projectSlug": "default-workspace",
            }
        )

        self.assertEqual(result["source"], "execution")
        self.assertEqual(result["execution_mode"], "image_refs")
        self.assertEqual(result["upload_count"], 6)
        self.assertEqual(result["reference_count"], 5)
        self.assertEqual(result["template_key"], "image_analysis")
        self.assertEqual(result["template_name"], "图片智能分析（中英双语）")
        self.assertEqual(result["compliance_mode"], "strict")
        self.assertEqual(
            result["titles"], ["EN title 1", "ZH 标题 1", "EN title 2", "ZH 标题 2"]
        )
        self.assertEqual(result["title_pairs"][0]["english"], "EN title 1")
        self.assertEqual(result["title_pairs"][0]["chinese"], "ZH 标题 1")
        self.assertEqual(len(captured["images"]), 5)
        self.assertIn("portable blender", captured["product_info"])
        self.assertIn(
            "Analyze the product image references", captured["template_prompt"]
        )
        self.assertEqual(
            result["execution_context"]["project_slug"], "default-workspace"
        )

    def test_title_task_allows_image_only_generation(self):
        module = _load_task_execution_module("task_execution_title_image_only_test")
        captured: dict[str, object] = {}
        module._resolve_title_provider = lambda config: "gemini"

        def generate_titles_or_raise(**kwargs):
            captured.update(kwargs)
            return ["EN title 1", "ZH 标题 1"], []

        module.generate_compliant_titles_or_raise = generate_titles_or_raise

        result = module.execute_title_task(
            {
                "uploadItems": [
                    {
                        "id": "img-1",
                        "rawName": "ref-1.png",
                        "mimeType": "image/png",
                        "sizeBytes": 1024,
                        "imageDataUrl": "data:image/png;base64,1",
                    }
                ],
                "count": 2,
            }
        )

        self.assertEqual(result["execution_mode"], "image_refs")
        self.assertEqual(result["upload_count"], 1)
        self.assertEqual(result["reference_count"], 1)
        self.assertEqual(result["template_key"], "image_analysis")
        self.assertEqual(captured["product_info"], "No additional info provided")

    def test_title_task_returns_compliance_warnings_for_filtered_pairs(self):
        module = _load_task_execution_module("task_execution_title_compliance_test")
        module._resolve_title_provider = lambda config: "gemini"
        module.generate_compliant_titles_or_raise = lambda **kwargs: (
            ["Travel Water Bottle", "旅行水瓶"],
            ["标题 1 未通过合规检测: 风险词: best"],
        )

        result = module.execute_title_task(
            {
                "productInfo": "portable blender for travel use",
                "templateKey": "default",
                "count": 3,
            }
        )

        self.assertEqual(result["template_key"], "default")
        self.assertEqual(result["titles"], ["Travel Water Bottle", "旅行水瓶"])
        self.assertEqual(result["title_pairs"][0]["label"], "搜索优化")
        self.assertTrue(result["warnings"])
        self.assertIn("风险词: best", result["warnings"][0])

    def test_translate_task_keeps_partial_success_for_bounded_image_batch(self):
        module = _load_task_execution_module("task_execution_translate_image_test")

        class _PartialImageClient(_FakeImageClient):
            def __init__(self):
                super().__init__(total_tokens=11)
                self.calls = 0
                self.last_error = ""

            def translate_image(self, image, translated_lines, **kwargs):
                del image, translated_lines, kwargs
                self.calls += 1
                if self.calls == 2:
                    self.last_error = "第二张图片生成失败"
                    return None
                return object()

            def get_last_error(self) -> str:
                return self.last_error

        image_client = _PartialImageClient()
        setattr(module, "build_image_client", lambda **kwargs: image_client)

        result = module.execute_translate_task(
            {
                "sourceLang": "auto",
                "targetLang": "English",
                "uploadItems": [
                    {
                        "id": "img-1",
                        "rawName": "first.png",
                        "mimeType": "image/png",
                        "sizeBytes": 1024,
                        "imageDataUrl": "data:image/png;base64,first",
                    },
                    {
                        "id": "img-2",
                        "rawName": "second.png",
                        "mimeType": "image/png",
                        "sizeBytes": 1024,
                        "imageDataUrl": "data:image/png;base64,second",
                    },
                ],
            }
        )

        self.assertEqual(result["execution_mode"], "image_batch")
        self.assertEqual(result["total_outputs"], 2)
        self.assertEqual(result["completed_outputs"], 1)
        self.assertEqual(result["failed_outputs"], 1)
        self.assertEqual(result["outputs"][0]["status"], "completed")
        self.assertEqual(
            result["outputs"][0]["artifact_data_url"], "data:image/png;base64,fake"
        )
        self.assertEqual(
            result["outputs"][0]["translated_lines"],
            ["English line 1", "English line 2"],
        )
        self.assertEqual(result["outputs"][1]["status"], "failed")
        self.assertIn("第二张图片生成失败", result["outputs"][1]["error"])
        self.assertTrue(result["errors"])
        self.assertEqual(result["source_lines"], ["原文一", "原文二"])
        self.assertEqual(
            result["translated_lines"], ["English line 1", "English line 2"]
        )
        self.assertEqual(result["source"], "execution")

    def test_translate_task_keeps_text_mode_without_uploads(self):
        module = _load_task_execution_module("task_execution_translate_text_test")

        result = module.execute_translate_task(
            {
                "sourceText": "原文一\n原文二",
                "sourceLang": "auto",
                "targetLang": "English",
            }
        )

        self.assertEqual(result["execution_mode"], "text")
        self.assertEqual(result["source_lines"], ["原文一", "原文二"])
        self.assertEqual(result["translated_lines"], ["EN:原文一", "EN:原文二"])

    def test_quick_task_uses_uploaded_images_as_bounded_refs(self):
        module = _load_task_execution_module("task_execution_quick_refs_test")
        image_client = _FakeImageClient(total_tokens=13)
        setattr(module, "build_image_client", lambda **kwargs: image_client)

        result = module.execute_quick_task(
            {
                "uploadItems": [
                    {
                        "id": f"img-{index + 1}",
                        "rawName": f"ref-{index + 1}.png",
                        "mimeType": "image/png",
                        "sizeBytes": 1024,
                        "imageDataUrl": f"data:image/png;base64,{index + 1}",
                    }
                    for index in range(6)
                ],
                "productInfo": "portable blender",
                "imageType": "selling_point",
                "count": 2,
                "includeTitles": False,
            }
        )

        self.assertEqual(result["source"], "execution")
        self.assertEqual(result["execution_mode"], "image_refs")
        self.assertEqual(result["upload_count"], 6)
        self.assertEqual(result["reference_count"], 5)
        self.assertEqual(result["image_type"], "selling_point")
        self.assertEqual(len(result["outputs"]), 2)
        self.assertEqual(len(image_client.generate_calls), 2)
        self.assertEqual(len(image_client.generate_calls[0]["refs"]), 5)
        self.assertEqual(result["outputs"][0]["filename"], "selling-point-1.png")
        self.assertEqual(
            result["outputs"][0]["artifact_data_url"], "data:image/png;base64,fake"
        )

    def test_batch_task_uses_uploaded_images_and_returns_anchor_summary(self):
        module = _load_task_execution_module("task_execution_batch_refs_test")
        image_client = _FakeImageClient(total_tokens=17)
        setattr(module, "build_image_client", lambda **kwargs: image_client)

        result = module.execute_batch_task(
            {
                "uploadItems": [
                    {
                        "id": f"img-{index + 1}",
                        "rawName": f"ref-{index + 1}.png",
                        "mimeType": "image/png",
                        "sizeBytes": 1024,
                        "imageDataUrl": f"data:image/png;base64,{index + 1}",
                    }
                    for index in range(6)
                ],
                "productInfo": "portable blender",
                "selectedTypes": ["main", "feature"],
                "includeTitles": False,
                "briefNotes": "突出便携和厨房使用场景",
            }
        )

        self.assertEqual(result["source"], "execution")
        self.assertEqual(result["execution_mode"], "image_refs")
        self.assertEqual(result["upload_count"], 6)
        self.assertEqual(result["reference_count"], 5)
        self.assertEqual(result["analysis_model"], "translate-analysis-model")
        self.assertEqual(result["anchor"]["primary_category"], "portable blender")
        self.assertEqual(result["anchor"]["product_name_en"], "Portable Blender")
        self.assertEqual(result["total_outputs"], 2)
        self.assertEqual(len(image_client.generate_calls), 2)
        self.assertEqual(len(image_client.generate_calls[0]["refs"]), 5)
        self.assertEqual(result["outputs"][0]["type"], "main")
        self.assertEqual(result["outputs"][0]["filename"], "main-1.png")
        self.assertEqual(
            result["outputs"][0]["artifact_data_url"], "data:image/png;base64,fake"
        )


if __name__ == "__main__":
    unittest.main()
