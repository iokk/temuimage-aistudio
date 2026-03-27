# Relay Translation Capability Design

## Goal

Push page 4 image translation toward relay-first execution while making provider/model capability boundaries explicit across pages 1/2/3/4.

## Product Rule

- Only show or enable capabilities that the current provider/model actually supports.
- If a task is unsupported, explain that clearly.
- Never silently fall back to a different hidden provider when a user selected relay-first behavior.

## Scope

- Add a provider/model capability matrix.
- Use that matrix to gate translation, title generation, analysis, and image generation.
- Make image translation relay-first when the selected relay model supports it.
- Keep `gemini-3.1-flash-image-preview` as the default relay analysis/title model.

## Constraints

- Keep current relay image generation working.
- Preserve admin-tool mode behavior when there is no database.
- Do not pretend unsupported relay models can translate images or analyze products.
