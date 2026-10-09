# A.R.C.

**Your Code Has History. Your AI Should Remember It.**

A.R.C. is a local-first developer memory system designed to preserve project context and help developers work more efficiently with AI coding assistants.

## The Problem

AI coding assistants can lose important context between sessions. Developers often have to repeatedly explain previous decisions, encountered errors, attempted solutions, and unfinished tasks.

This wastes time, interrupts development, and can lead to repeated mistakes.

## Our Solution

A.R.C. acts as a persistent memory layer for software development. It records important project activities, organizes supporting evidence, and makes previous context accessible to developers and AI agents.

Instead of relying solely on conversation history, A.R.C. helps coding assistants access recorded information about what actually happened in a project.

## Key Features

- **Project Memory** — Records development sessions, important decisions, errors, and attempted solutions.
- **Evidence-Based Progress Tracking** — Associates tasks with code changes and test results to distinguish verified work from unverified claims.
- **Semantic Search** — Retrieves relevant development history through natural-language queries using local embeddings.
- **AI Agent Integration** — Provides recorded project context to compatible AI coding assistants through the Model Context Protocol (MCP).
- **Local-First Storage** — Keeps project evidence in a local SQLite database, giving developers control over their recorded information.

## How It Works

1. **Record** — Capture meaningful development events, decisions, code changes, and test results.
2. **Organize** — Store project history as structured, traceable evidence.
3. **Retrieve** — Find relevant information using semantic search or connected AI agents.
4. **Continue** — Use previously recorded context to guide future development sessions.

## Technology Stack

- **Python** — Core backend and CLI
- **SQLite** — Local project data storage
- **Ollama** — Local embedding model execution
- **all-minilm** — Semantic embeddings
- **Git** — Code change evidence
- **Model Context Protocol (MCP)** — AI coding assistant integration

## Current Development Status

A.R.C. supports explicit sessions, opt-in Git observation, task evidence tracking, configured tests, automatic indexing, local search, cited evidence answers, a VS Code extension, and MCP integration. Target-Mac and physical offline release checks remain pending.

Planned improvements include automated activity tracking, intelligent handoffs, incident memory, local AI chat, and a VS Code interface.

The physical disconnected-network validation is still pending.

## Our Vision

We envision a development environment where important context does not disappear when an AI session ends.

**Build continuously. Remember intelligently.**
