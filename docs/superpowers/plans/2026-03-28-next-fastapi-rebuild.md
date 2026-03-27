# Next.js + FastAPI Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the initial production-grade monorepo skeleton for the full Next.js + FastAPI replacement system.

**Architecture:** Keep the current Streamlit product untouched in the root for now, but add a new monorepo structure under `apps/` and `packages/` that becomes the replacement target. Phase 1 establishes web, API, worker, shared schema, and deployment shape so later feature migration can happen in a controlled sequence.

**Tech Stack:** Next.js 15, TypeScript, Tailwind, shadcn/ui, FastAPI, Celery, Redis, PostgreSQL, Prisma, Casdoor.

---
