# Phase 2 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the new replacement stack from a skeleton into a usable backend/data foundation: richer Prisma schema, modular FastAPI app structure, and a verified Phase 2 base for later auth and feature migration.

**Architecture:** Keep Streamlit untouched. Work only in the new `apps/` and `packages/` monorepo structure. Prisma remains the schema source of truth, while FastAPI exposes modular routers and SQLAlchemy runtime models that map to those tables.

**Tech Stack:** Next.js 15, TypeScript, FastAPI, SQLAlchemy, Prisma, PostgreSQL, Celery, Redis.

---
