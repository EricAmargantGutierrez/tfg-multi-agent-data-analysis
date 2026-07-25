# Development Log

**Project:** Multi-Agent Conversational Data Analysis System


**Author:** Eric Amargant Gutiérrez


**Supervisor:** Piotr Przybyła

---

# Project Objective

Develop a conversational system capable of answering natural language questions over structured datasets using a modular multi-agent architecture based on the Model Context Protocol (MCP).

The project combines Large Language Models, LangGraph orchestration, SQLite databases, and specialized agents for data retrieval, analysis, visualization, and report generation.

---

# Milestone 1 — Project Initialization

- Defined the project objectives.
- Selected the Superstore dataset as the experimental dataset.
- Designed the initial project structure.
- Selected the main technologies:
  - Python
  - LangGraph
  - FastMCP
  - SQLite
  - LangChain

---

# Milestone 2 — Database

Implemented the data layer.

Completed tasks:

- Dataset validation.
- Automatic ingestion pipeline.
- Database normalization.
- SQLite database creation.

---

# Milestone 3 — LLM Integration

Implemented a provider-independent LLM interface.

Currently supported providers:

- Groq
- Ollama
- OpenAI
- Anthropic

The active provider can be selected through the project configuration.

---

# Milestone 4 — Multi-Agent Architecture

Implemented four independent MCP agents.

- SQL Agent
- Analysis Agent
- Visualization Agent
- Report Agent

Each agent exposes a single MCP tool and has a clearly defined responsibility.

---

# Milestone 5 — LangGraph Orchestrator

Implemented the orchestration layer.

Responsibilities include:

- LLM-based routing.
- Agent invocation.
- Conversation state management.
- Conversation history management.

---

# Milestone 6 — SQL Agent

Implemented:

- Natural language to SQL generation.
- SQLite schema awareness.
- Read-only SQL validation.
- Automatic retry after execution errors.

---

# Milestone 7 — Analysis Agent

Implemented the analysis agent responsible for transforming SQL query results into concise natural-language explanations.

---

# Milestone 8 — Visualization Agent

Implemented automatic chart generation from natural language requests.

Generated figures are stored in the `results/` directory.

---

# Milestone 9 — Report Agent

Implemented automatic generation of Markdown reports summarizing each interaction session.

---

# Milestone 10 — Interactive Interface

Implemented a command-line conversational interface (REPL) allowing users to interact with the complete system.

---

# Phase 1 Completed

The first phase of the project has been successfully completed.

The current implementation includes:

- complete multi-agent architecture;
- MCP communication between components;
- LangGraph orchestration;
- conversational interaction;
- SQL generation and execution;
- natural-language explanations;
- automatic chart generation;
- automatic report generation.

---

# Next Phase

The next stage of the project focuses on designing and implementing the evaluation methodology.

The evaluation will define suitable benchmarks, establish baseline approaches, measure the quality of the generated answers, evaluate the robustness of the architecture, and analyze the performance of the proposed system.