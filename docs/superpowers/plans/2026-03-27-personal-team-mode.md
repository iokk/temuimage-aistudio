# Personal and Team Mode Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the app into explicit personal/team modes first, then add provider/model prechecks across pages 1/2/3/4.

**Architecture:** Keep Streamlit as the shell, but move mode decisions and credential interpretation into helpers. The login page becomes a strict two-mode entry point. The second phase then adds preflight capability checks before generation/translation/title execution.

**Tech Stack:** Streamlit, Python, relay and Gemini integrations, helper modules under `temu_core/`, unittest.

---
