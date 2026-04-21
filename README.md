# Chief of Staff

A personal AI platform that acts as a Chief of Staff for a specific role — ingesting information from connected sources, retaining it in a knowledge base, and reasoning over it to answer questions, draft communications, and surface what matters.

## What it does

- Pulls in information from email, calendar, documents, and other sources
- Stores everything in a searchable knowledge base with full provenance
- Answers questions grounded in that knowledge, with citations back to source material
- Behaves according to a role definition — who it serves, what it prioritises, how it communicates

## How it works

The platform has two parts: a **generic core** that handles ingestion, storage, retrieval, and reasoning; and a **role pack** — a configuration file that defines the specific role, its goals, stakeholders, and working style. Swapping the role pack changes who the platform serves without touching the core.

The model layer is kept behind an interface so the underlying LLM can be changed without affecting the rest of the system.

## Design principles

- Every answer traces back to source material — no generation without retrieval
- Source documents are never mixed with generated output
- Secrets and credentials never appear in logs or API responses
- Role behaviour lives in configuration, not code

## Stack

Python · PostgreSQL · pgvector · MCP (model context protocol) · Docker
