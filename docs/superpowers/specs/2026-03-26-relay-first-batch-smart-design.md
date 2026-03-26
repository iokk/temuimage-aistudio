# Relay-First Batch and Smart Design

## Goal

Allow `1 批量出图` and `2 快速出图` to keep working when the system has relay configuration but no Gemini system key.

## Scope

- Batch page product analysis can run through relay text generation.
- Batch page requirement generation and English copy can run through relay text generation.
- Batch page and Smart page title generation can run through relay text generation.
- Image generation on both pages continues to use the selected image backend.

## Approach

Introduce a relay text client for OpenAI-compatible chat completions, then reuse the existing prompt templates and JSON parsing flow so the relay path mirrors the Gemini path. Keep the UI behavior simple: if the selected provider is relay, prefer relay for text-analysis/title steps as well.

## Constraints

- No secrets committed to Git.
- Keep existing Gemini path intact.
- Preserve current result UI and compliance checks.
