# Relay Translation Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add provider capability gating and make image translation relay-first when the selected relay model actually supports translation output.

**Architecture:** Introduce a capability matrix helper, route feature availability through it, and use relay text/image clients only when their selected model supports the requested task. Unsupported cases become explicit UI states rather than fake availability.

**Tech Stack:** Streamlit, Python, relay OpenAI-compatible API, existing RelayImageClient and RelayTextClient.

---
