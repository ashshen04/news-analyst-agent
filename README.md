# News Analyst Agent

A news analysis agent built with LangGraph + LangChain. Input any topic and it will automatically fetch relevant news, perform multi-perspective analysis, identify conflicting information, and generate a comprehensive report.

## Project Structure

```
news-analyst-agent/
├── main.py             # Entry point
├── graph.py            # LangGraph workflow definition
├── nodes.py            # Graph node definitions
├── tools.py            # Tool definitions
├── state.py            # AgentState definition
├── requirements.txt    # Dependencies
└── .env.example        # Environment variables template
```

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

Then edit `.env` with your keys.

## Usage

```bash
python main.py
```
