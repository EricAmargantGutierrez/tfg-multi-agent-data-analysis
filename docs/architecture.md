# System Architecture

## Overview

The Multi-Agent Conversational Data Analysis System is designed as a modular architecture in which each component has a single well-defined responsibility.

The system allows users to ask natural language questions about structured datasets. User requests are routed by an orchestrator to specialized agents that retrieve information, perform statistical analysis, generate visualizations, and produce reports.

The architecture combines Large Language Models (LLMs), LangGraph, the Model Context Protocol (MCP), and SQLite to provide a flexible and extensible conversational interface for data analysis.


---

# System Architecture

<p align="center">
  <img src="architecture-diagram.svg" width="900">
</p>

---


## High-Level Architecture

The system consists of the following main components:

- Interactive REPL
- LangGraph Orchestrator
- LLM-based Router
- LLM Narrator
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
- generating the final natural-language response using an LLM narrator;
- storing conversation history;
- returning the final response to the user.

The orchestrator does not perform any data analysis itself. Instead, it delegates each task to the appropriate specialized component.

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
- automatically retrying when SQL generation or execution errors occur.

Both the SQL Agent and the Analysis Agent access the SQLite database independently. The SQL Agent executes analytical SQL queries requested by the user, whereas the Analysis Agent retrieves the data required for statistical computations before performing the analysis locally using Python.

---

### Analysis Agent

The Analysis Agent performs statistical analyses and machine learning computations over the dataset.

Instead of generating SQL directly from the user's request, the agent first asks an LLM to determine:

- which statistical analysis should be performed;
- which database columns are required.

The agent then retrieves the required data from SQLite, loads it into a pandas DataFrame, executes the requested computation using specialized Python libraries, and returns the structured result to the orchestrator.

Currently supported analyses include:

- descriptive statistics;
- correlation and covariance;
- t-tests;
- linear regression;
- Principal Component Analysis (PCA);
- K-Means clustering.

---

### Visualization Agent

The Visualization Agent generates figures directly from natural language requests.

The agent:

- generates the SQL query required to retrieve the requested data;
- executes the query;
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

### LLM Narrator

The narrator converts the structured outputs returned by the different agents into concise natural-language responses.

Unlike the specialized agents, the narrator does not perform computations or access the database. Its only responsibility is to communicate the results in a readable form while preserving the information returned by the agents.

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
5. The structured result is returned to the orchestrator.
6. The orchestrator invokes the LLM narrator to generate the final natural-language response.
7. The interaction is stored in the conversation history.
8. The final answer is presented to the user.
9. When the session ends, the Report Agent generates a Markdown report.

---

## Design Decisions

Several design decisions guided the implementation:

- Each agent exposes exactly one MCP tool.
- Every agent has a single clearly defined responsibility.
- The SQL Agent is the only component allowed to execute database queries.
- Statistical analyses are performed using Python libraries whenever SQL is not the most appropriate solution.
- SQL validation prevents non-read-only statements from being executed.
- Natural-language narration is centralized in the orchestrator instead of individual agents.
- Conversation history is maintained by the orchestrator instead of individual agents.
- LLM providers are abstracted behind a common interface, allowing different models to be used without modifying the architecture.

These decisions improve modularity, maintainability, and extensibility.

---

## Current Limitations

The current implementation has several limitations:

- The system currently supports a single SQLite database.
- Visualization capabilities are limited to the implemented chart types.
- The router selects a single agent for each request.
- Long conversation histories are passed entirely to the Report Agent without prior summarization.

These limitations provide opportunities for future improvements.

---

## Future Extensions

Possible future extensions include:

- support for additional databases;
- additional analytical agents (e.g., forecasting or anomaly detection);
- richer visualization capabilities;
- retrieval-augmented generation (RAG);
- multi-agent collaboration within a single query;
- distributed deployment of MCP agents.

---

## Current Status

Phase 1 of the project has been completed.

The current implementation includes the complete multi-agent architecture, MCP-based communication, LangGraph orchestration, conversational interaction, statistical analysis, visualization generation, automatic report generation, and support for multiple LLM providers.

The next phase of the project focuses on defining and implementing a rigorous evaluation methodology to assess the correctness, robustness, efficiency, and usability of the proposed conversational system.