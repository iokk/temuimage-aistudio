# Relay-First Batch and Smart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make pages 1 and 2 usable through relay-only system configuration by moving product analysis, requirement generation, and title generation onto relay-compatible text completions.

**Architecture:** Add a small relay text client plus pure helper functions for analysis/requirement generation. Use those helpers from Batch and Smart pages whenever the selected provider is relay, while keeping Gemini behavior unchanged.

**Tech Stack:** Streamlit, Python, requests, OpenAI-compatible relay API, existing prompt/template system.

---
