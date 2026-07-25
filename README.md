# Multi-Agent Conversational Data Analysis System

Bachelor's Thesis (TFG)

**Author:** Eric Amargant Gutiérrez  


**Degree:** Bachelor's Degree in Mathematical Engineering in Data Science  


**University:** Universitat Pompeu Fabra (UPF)  


**Supervisor:** Piotr Przybyła

---

## Overview

This project implements a conversational system that answers natural language questions over structured datasets using a modular multi-agent architecture.

The system combines Large Language Models (LLMs), LangGraph for orchestration, and the Model Context Protocol (MCP) to coordinate specialized agents responsible for SQL generation, data analysis, visualization, and report generation.

The objective is to investigate how agent-based architectures can improve natural language interaction with structured data while maintaining a clear separation of responsibilities between system components.

---

## Features

- Multi-agent architecture based on FastMCP
- LangGraph orchestration
- LLM-based routing
- Natural language to SQL generation
- Automatic SQL validation and self-correction
- Natural language explanations
- Automatic chart generation
- Session report generation
- Conversation history management
- Support for multiple LLM providers

---

## Architecture

The system consists of four specialized MCP agents coordinated by a LangGraph orchestrator.

- **SQL Agent** – Generates and executes read-only SQL queries.
- **Analysis Agent** – Explains SQL query results in natural language.
- **Visualization Agent** – Generates charts from natural language requests.
- **Report Agent** – Produces a Markdown report summarizing the interaction.

The orchestrator is responsible for routing user requests, invoking the appropriate agent, maintaining the conversation history, and returning the final response.

A detailed description of the architecture is available in `docs/architecture.md`.

---

## Technologies

- Python 3.12
- LangGraph
- FastMCP
- LangChain
- SQLite
- Matplotlib
- Groq (default)
- Ollama
- OpenAI
- Anthropic

---

## Repository Structure

```text
src/
├── agents/
├── config/
├── core/
├── database/
├── eval/
├── llm/
├── orchestrator/
└── repl.py

docs/
results/
data/
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/EricAmargantGutierrez/tfg-multi-agent-data-analysis.git
cd tfg-multi-agent-data-analysis
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Configure the required environment variables in the `.env` file.

---

## Running the System

Launch the interactive assistant:

```bash
python -m src.repl
```

Example questions:

- How many orders are there?
- Which region has the highest sales?
- Show a line chart of monthly sales.
- Create a bar chart of sales by region.

---

## Documentation

Additional documentation is available in the `docs/` directory.

- `architecture.md` — System architecture and execution flow.
- `development_log.md` — Project implementation log.

---

## Current Status

**Version:** v1.0

Phase 1 of the project has been completed. The current implementation includes the complete multi-agent architecture, MCP-based communication, LangGraph orchestration, conversational interaction, visualization generation, and automatic report generation.

The next stage of the project focuses on designing and implementing the evaluation methodology for the proposed architecture.

---

## License

This project was developed as part of a Bachelor's Thesis at Universitat Pompeu Fabra.