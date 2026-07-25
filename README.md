# Multi-Agent Conversational Data Analysis System

Bachelor's Thesis (TFG)

**Author:** Eric Amargant Gutiérrez
**Degree:** Bachelor's Degree in Mathematical Engineering in Data Science
**University:** Universitat Pompeu Fabra (UPF)
**TFG Supervisor:** Piotr Przybyła

---

## Overview

This project implements a conversational system that answers natural language questions about structured datasets using a multi-agent architecture. The system combines Large Language Models (LLMs), LangGraph for orchestration, and the Model Context Protocol (MCP) to coordinate specialized agents responsible for SQL generation, data analysis, visualization, and report generation.

The objective is to investigate how a modular agent-based architecture can improve the interaction between users and structured data while maintaining a clear separation of responsibilities between system components.

---

## Architecture

The system is composed of four specialized MCP agents coordinated by a LangGraph orchestrator.

* **SQL Agent**

  * Converts natural language questions into SQLite queries.
  * Validates that generated SQL is read-only.
  * Automatically retries when SQL execution fails.

* **Analysis Agent**

  * Interprets SQL query results.
  * Produces concise natural-language explanations.

* **Visualization Agent**

  * Generates charts from natural language requests.
  * Produces publication-ready figures stored in the `results/` directory.

* **Report Agent**

  * Generates a Markdown report summarizing the complete interaction session.

The orchestrator is responsible for:

* Routing user questions.
* Calling the appropriate MCP agent.
* Maintaining conversation history.
* Returning the final response to the user.

---

## Technologies

* Python 3.12
* LangGraph
* FastMCP
* LangChain
* SQLite
* Matplotlib
* Groq API (default)
* Ollama (optional)
* OpenAI (supported)
* Anthropic (supported)

---

## Project Structure

```text
src/
├── agents/
├── config/
├── core/
├── database/
├── eval/
├── llm/
├── models/
├── orchestrator/
├── utils/
├── repl.py
```

---

## Running the System

Clone the repository.

Create a virtual environment.

Install the required dependencies.

Configure the environment variables.

Run the interactive assistant:

```bash
python -m src.repl
```

Example questions:

* How many orders are there?
* Which region has the highest sales?
* Show a line chart of monthly sales.
* Create a bar chart of sales by region.

---

## Current Features

* Multi-agent architecture using FastMCP
* LangGraph orchestration
* LLM-based routing
* Natural language to SQL
* Automatic SQL validation
* Automatic SQL self-correction
* Natural language explanations
* Automatic chart generation
* Session report generation
* Conversation history management
* Support for multiple LLM providers

---

## Current Status

**Version:** v1.0

The implementation of the conversational system has been completed.

The current version includes the complete architecture and all planned agents. Future work will focus on evaluating the system using quantitative and qualitative metrics, comparing its performance against suitable baselines, and analyzing its robustness.

---

## Future Work

The next stage of the project focuses on the evaluation methodology, including:

* Definition of evaluation benchmarks.
* Comparison against baseline approaches.
* Accuracy evaluation.
* Robustness analysis.
* Performance measurements.
* Error analysis.

---

## License

This project was developed as a Bachelor's Thesis at Universitat Pompeu Fabra.