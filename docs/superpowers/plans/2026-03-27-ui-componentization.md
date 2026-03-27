# UI Componentization and Action Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Componentize credential/system config surfaces, explain disabled actions clearly on pages 1/2/3/4, and deepen the visual polish into a more consistent admin-tool dashboard.

**Architecture:** Add small helper modules for config panel metadata and action-state reasoning, then feed those helpers into the existing Streamlit pages. Keep Streamlit as the rendering layer while shifting repeated UI decisions into pure Python helpers that can be tested.

**Tech Stack:** Streamlit, Python, existing UI helper layer, unittest.

---
