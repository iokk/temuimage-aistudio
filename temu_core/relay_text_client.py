from __future__ import annotations

import base64
import io
import json
import re

import requests
from PIL import Image


class RelayTextClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://newapi.aisonnet.org/v1",
        timeout_sec: int = 180,
    ):
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "").strip()
        self.base_url = str(base_url or "https://newapi.aisonnet.org/v1").rstrip("/")
        self.timeout_sec = timeout_sec
        self.last_error = ""
        self.total_tokens = 0

    def get_last_error(self):
        return self.last_error

    def get_tokens_used(self):
        return self.total_tokens

    def _build_messages(self, refs, prompt: str):
        content = [{"type": "text", "text": prompt}]
        for ref in (refs or [])[:5]:
            try:
                buf = io.BytesIO()
                ref.copy().save(buf, format="PNG", optimize=True)
                b64 = base64.b64encode(buf.getvalue()).decode()
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    }
                )
            except Exception:
                continue
        return [{"role": "user", "content": content}]

    def extract_text_from_response(self, payload: dict) -> str:
        if not isinstance(payload, dict):
            return ""
        choices = payload.get("choices", []) or []
        for choice in choices:
            message = choice.get("message", {}) or {}
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    text = item.get("text")
                    if text:
                        parts.append(str(text).strip())
                if parts:
                    return "\n".join(parts)
        return ""

    def parse_json_response(self, text: str, default):
        raw = str(text or "").strip()
        if not raw:
            return default
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines).strip()
        try:
            return json.loads(raw)
        except Exception:
            pass
        for pattern in (r"\{.*\}", r"\[.*\]"):
            match = re.search(pattern, raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    continue
        return default

    def generate_text(
        self, refs, prompt: str, max_tokens: int = 1800, temperature: float = 0.2
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": self._build_messages(refs, prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout_sec,
        )
        text = response.text
        if response.status_code >= 400:
            self.last_error = text
            raise Exception(text)
        data = response.json()
        usage = data.get("usage", {}) or {}
        self.total_tokens += int(usage.get("total_tokens") or 0)
        result = self.extract_text_from_response(data)
        if not result:
            self.last_error = text[:300]
        return result

    def _clean_title_lines(self, text: str):
        lines = [line.strip() for line in str(text or "").split("\n") if line.strip()]
        clean_lines = []
        for line in lines:
            cleaned = re.sub(
                r"^(Title\s*\d*[:.]?\s*|Option\s*\d*[:.]?\s*|\d+[:.]\s*|English[:]\s*|Chinese[:]\s*|中文[:]\s*)",
                "",
                line,
                flags=re.IGNORECASE,
            ).strip()
            if cleaned:
                clean_lines.append(cleaned)
        return clean_lines[:6] if len(clean_lines) >= 6 else clean_lines

    def generate_titles(self, product_info: str, template_prompt: str):
        prompt = template_prompt.replace("{product_info}", product_info)
        text = self.generate_text([], prompt, max_tokens=1200)
        return self._clean_title_lines(text)

    def generate_titles_from_image(
        self, images, product_info: str = "", template_prompt: str = ""
    ):
        prompt = template_prompt.replace(
            "{product_info}", product_info or "No additional info provided"
        )
        text = self.generate_text(images, prompt, max_tokens=1200)
        return self._clean_title_lines(text)

    def extract_text_from_image(self, image, source_lang: str = "auto"):
        prompt = (
            f"Extract visible text from this image. Source language hint: {source_lang}. "
            'Return JSON only: {"language":"detected language","lines":["line1","line2"]}'
        )
        text = self.generate_text([image], prompt, max_tokens=1200)
        parsed = self.parse_json_response(text, {"language": source_lang, "lines": []})
        if not isinstance(parsed, dict):
            return {"language": source_lang, "lines": []}
        return {
            "language": parsed.get("language") or source_lang,
            "lines": [
                str(line).strip()
                for line in (parsed.get("lines") or [])
                if str(line).strip()
            ],
        }

    def translate_lines(
        self,
        lines,
        source_lang="auto",
        target_lang="English",
        style_hint="Literal",
        avoid_terms=None,
        enforce_english=False,
        max_attempts=1,
    ):
        clean_lines = [str(line).strip() for line in (lines or []) if str(line).strip()]
        if not clean_lines:
            return []
        avoid_terms_text = ", ".join(avoid_terms) if avoid_terms else "None"
        prompt = (
            f"Translate the following text lines from {source_lang} to {target_lang}.\n"
            f"Style: {style_hint}.\n"
            f"Avoid these terms if needed: {avoid_terms_text}.\n"
            'Return JSON only: {"translated_lines":["line1","line2"]}\n'
            + "\n".join(clean_lines)
        )
        text = self.generate_text([], prompt, max_tokens=1200)
        parsed = self.parse_json_response(text, {"translated_lines": []})
        if not isinstance(parsed, dict):
            return []
        translated_lines = [
            str(line).strip()
            for line in (parsed.get("translated_lines") or [])
            if str(line).strip()
        ]
        return translated_lines

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
        avoid_terms_text = ", ".join(avoid_terms) if avoid_terms else "None"
        prompt = (
            f"Extract text from this image and translate it from {source_lang} to {target_lang}.\n"
            f"Style: {style_hint}.\n"
            f"Avoid these terms if needed: {avoid_terms_text}.\n"
            'Return JSON only: {"language":"detected language","source_lines":["line1"],"translated_lines":["line1"]}'
        )
        text = self.generate_text([image], prompt, max_tokens=1400)
        parsed = self.parse_json_response(
            text, {"language": source_lang, "source_lines": [], "translated_lines": []}
        )
        if not isinstance(parsed, dict):
            return {"language": source_lang, "source_lines": [], "translated_lines": []}
        return {
            "language": parsed.get("language") or source_lang,
            "source_lines": [
                str(line).strip()
                for line in (parsed.get("source_lines") or [])
                if str(line).strip()
            ],
            "translated_lines": [
                str(line).strip()
                for line in (parsed.get("translated_lines") or [])
                if str(line).strip()
            ],
        }
