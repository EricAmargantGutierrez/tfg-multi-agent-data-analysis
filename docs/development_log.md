# Development Log

## Project

**Title:** Multi-Agent Conversational Data Analysis System


**Author:** Eric Amargant Gutiérrez


**Supervisor:** Piotr Przybyła

---

# Phase 1 — Core System Implementation

## Objective

Implement the complete architecture proposed for the conversational data analysis system.

The goal of this phase is to obtain a functional prototype capable of answering natural language questions over structured data using a multi-agent architecture based on MCP.

---

## Main Components Implemented

### Dataset

* Superstore dataset
* SQLite database
* Automatic ingestion pipeline
* Dataset validation

---

### LLM Integration

Implemented a provider-independent LLM interface supporting:

* Groq
* Ollama
* OpenAI
* Anthropic

The active provider is selected through the project configuration.

---

### Multi-Agent Architecture

Implemented four independent MCP agents:

* SQL Agent
* Analysis Agent
* Visualization Agent
* Report Agent

Each agent exposes a single MCP tool with a well-defined responsibility.

---

### Orchestrator

Implemented using LangGraph.

Responsibilities include:

* Question routing
* Agent invocation
* Conversation state management
* Session history management

---

### SQL Agent

Features:

* Natural language to SQL generation
* SQLite schema awareness
* Read-only SQL validation
* Automatic retry after execution errors

---

### Analysis Agent

Receives SQL query results and generates natural-language explanations using an LLM.

---

### Visualization Agent

Generates charts directly from natural language requests.

Outputs figures into the `results/` directory.

---

### Report Agent

Generates a Markdown report summarizing the interaction session.

---

### Interactive Interface

Implemented a command-line REPL supporting conversational interaction with the system.

---

## Current Status

Phase 1 has been completed successfully.

The system can:

* answer analytical questions,
* execute SQL queries,
* explain results,
* generate charts,
* generate session reports,
* maintain conversation history.

---

## Next Phase

Design and implement a rigorous evaluation methodology for the proposed architecture.

This phase will define evaluation metrics, establish suitable baselines, and experimentally assess the performance of the system.