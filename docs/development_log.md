# Development Log

**Project:** Multi-Agent Conversational Data Analysis System

**Author:** Eric Amargant Gutiérrez

**Supervisor:** Piotr Przybyła

---

# Project Objective

Develop a conversational system capable of answering natural language questions over structured datasets using a modular multi-agent architecture based on the Model Context Protocol (MCP).

The project combines Large Language Models, LangGraph orchestration, SQLite databases, and specialized agents for SQL querying, statistical analysis, visualization, and report generation.

---

# Milestone 1 — Project Initialization

Completed tasks:

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

Implemented the complete multi-agent architecture composed of four independent MCP agents.

- SQL Agent
- Analysis Agent
- Visualization Agent
- Report Agent

Each agent exposes a single MCP tool and has a clearly defined responsibility.

---

# Milestone 5 — LangGraph Orchestrator

Implemented the orchestration layer.

Completed tasks:

- LLM-based routing.
- MCP agent invocation.
- Conversation state management.
- Conversation history management.
- Centralized natural-language narration of agent outputs.

---

# Milestone 6 — SQL Agent

Implemented:

- Natural language to SQL generation.
- SQLite schema awareness.
- Read-only SQL validation.
- Automatic retry after SQL generation or execution errors.

---

# Milestone 7 — Analysis Agent

Implemented a dedicated statistical analysis agent.

Completed features:

- Descriptive statistics.
- Correlation analysis.
- Covariance computation.
- Independent t-tests.
- Linear regression.
- Principal Component Analysis (PCA).
- K-Means clustering.

The agent retrieves the required data from SQLite, performs the requested computation using Python scientific libraries, and returns structured results to the orchestrator.

---

# Milestone 8 — Visualization Agent

Implemented automatic chart generation from natural language requests.

Completed tasks:

- Automatic SQL generation.
- Data retrieval.
- Matplotlib chart generation.
- Figure storage in the `results/` directory.

---

# Milestone 9 — Report Agent

Implemented automatic generation of Markdown reports summarizing each interaction session.

---

# Milestone 10 — Interactive Interface

Implemented a command-line conversational interface (REPL) allowing users to interact with the complete system.

The REPL supports conversational sessions and automatically generates a session report when the interaction finishes.

---

# Phase 1 Completed

Phase 1 of the project has been successfully completed.

The implemented system includes:

- complete multi-agent architecture;
- MCP-based communication;
- LangGraph orchestration;
- conversational interaction;
- LLM-based routing;
- SQL generation and execution;
- statistical analysis and machine learning;
- automatic visualization generation;
- centralized natural-language response generation;
- automatic session report generation;
- support for multiple LLM providers.

The complete architecture has been implemented and validated through functional testing of all supported agent capabilities.

---

# Next Phase

Phase 2 focuses on the evaluation of the proposed architecture.

The evaluation will include:

- definition of a benchmark composed of representative analytical questions;
- establishment of suitable baseline approaches;
- quantitative evaluation of answer correctness;
- evaluation of routing accuracy;
- robustness analysis;
- latency and performance measurements;
- qualitative analysis of generated visualizations;
- systematic error analysis.