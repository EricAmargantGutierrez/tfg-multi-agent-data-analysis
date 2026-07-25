# System Architecture

## Overview

The Multi-Agent Conversational Data Analysis System is designed as a modular architecture in which each component has a single well-defined responsibility.

The system allows users to ask natural language questions about structured datasets. User requests are routed by an orchestrator to specialized agents that retrieve information, generate visualizations, explain results, or produce reports.

The architecture combines Large Language Models (LLMs), LangGraph, the Model Context Protocol (MCP), and SQLite to provide a flexible and extensible conversational interface for data analysis.

---

## High-Level Architecture

The system consists of the following main components:

- Interactive REPL
- LangGraph Orchestrator
- LLM-based Router
- SQL Agent
- Analysis Agent
- Visualization Agent
- Report Agent
- SQLite Database

The orchestrator coordinates the interaction between all agents while maintaining the conversation history.

---

## Components

### REPL

The REPL provides the command-line interface through which users interact with the system.

Its responsibilities are:

- receive user questions;
- send requests to the orchestrator;
- display answers;
- generate the final session report when the interaction ends.

---

### LangGraph Orchestrator

The orchestrator is responsible for coordinating the complete execution flow.

Its responsibilities include:

- maintaining the conversation state;
- selecting the appropriate agent;
- invoking MCP tools;
- storing conversation history;
- returning the final response to the user.

The orchestrator does not perform any data analysis itself. Instead, it delegates each task to the appropriate specialized agent.

---

### Router

The router uses an LLM to determine which agent should answer each user request.

Currently, four possible routes are supported:

- SQL Agent
- Analysis Agent
- Visualization Agent
- Report Agent

If the LLM fails to produce a valid routing decision, a keyword-based fallback router is used.

---

### SQL Agent

The SQL Agent transforms natural language questions into SQLite queries.

Its responsibilities include:

- generating SQL statements using an LLM;
- validating that generated SQL is read-only;
- executing queries against the database;
- automatically retrying when execution errors occur.

The SQL Agent is the only component allowed to directly access the database.

---

### Analysis Agent

The Analysis Agent receives the structured output produced by the SQL Agent.

Its role is to generate concise natural-language explanations that summarize the results returned by SQL queries.

---

### Visualization Agent

The Visualization Agent generates figures directly from natural language requests.

The agent:

- creates an appropriate SQL query;
- retrieves the required data;
- generates a chart using Matplotlib;
- stores the resulting figure in the `results/` directory.

---

### Report Agent

The Report Agent summarizes the complete interaction session.

It produces a Markdown document containing:

- executive summary;
- questions asked;
- key findings;
- conclusions.

The generated report is automatically saved in the `results/` directory.

---

## Database

The system currently uses a SQLite database generated from the Superstore dataset.

The ingestion pipeline:

- validates the dataset;
- normalizes column names;
- converts date fields;
- creates the SQLite database.

Only read-only SQL queries are permitted during normal operation.

---

## Execution Flow

A typical interaction follows these steps:

1. The user submits a question through the REPL.
2. The orchestrator receives the request.
3. The router selects the appropriate agent.
4. The selected MCP agent performs the requested task.
5. The result is returned to the orchestrator.
6. The orchestrator stores the interaction in the conversation history.
7. The final answer is presented to the user.
8. When the session ends, the Report Agent generates a Markdown report.

---

## Design Decisions

Several design decisions guided the implementation:

- Each agent exposes exactly one MCP tool.
- Every agent has a single clearly defined responsibility.
- The SQL Agent is the only component allowed to execute database queries.
- SQL validation prevents non-read-only statements from being executed.
- Conversation history is maintained by the orchestrator instead of individual agents.
- LLM providers are abstracted behind a common interface, allowing different models to be used without modifying the architecture.

These decisions improve modularity, maintainability, and extensibility.

---

## Current Limitations

The current implementation has several limitations:

- The system currently supports a single SQLite database.
- Visualization capabilities are limited to the implemented chart types.
- The router selects a single agent for each request.
- Long conversation histories are passed entirely to the Report Agent without summarization.

These limitations provide opportunities for future improvements.

---

## Future Extensions

Possible future extensions include:

- support for additional databases;
- more specialized agents;
- richer visualization capabilities;
- retrieval-augmented generation (RAG);
- multi-agent collaboration within a single query;
- distributed deployment of MCP agents.

---

## Current Status

The implementation of the proposed architecture has been completed.

The next phase of the project focuses on defining an evaluation methodology to assess the effectiveness, robustness, and performance of the proposed conversational system.