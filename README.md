# News Analyst Agent

A news analysis agent built with LangGraph + LangChain. Input any topic and it will automatically fetch relevant news, perform multi-perspective analysis, identify conflicting information, and generate a comprehensive report — delivered daily via email.

## Project Structure

```
news-analyst-agent/
├── src/                        # Application source code
│   ├── main.py                 # CLI entry point
│   ├── daily.py                # Daily pipeline orchestrator
│   ├── lambda_function.py      # AWS Lambda handler
│   ├── graph.py                # LangGraph workflow definition
│   ├── nodes.py                # LLM node functions (fetch, analyze, conflicts, report)
│   ├── tools.py                # Tavily news search tool
│   ├── state.py                # AgentState TypedDict
│   ├── db.py                   # SQLite persistence layer
│   ├── logger.py               # Centralized logging config
│   ├── notifier.py             # Gmail SMTP email sender
│   ├── template.py             # HTML email template
│   └── system_prompt.md        # LLM system prompt (bilingual formatting)
├── tests/                      # pytest test suite (25 tests)
│   ├── conftest.py             # Shared fixtures & mocks
│   ├── test_db.py              # Database layer tests
│   ├── test_nodes.py           # LLM node tests
│   ├── test_tools.py           # Search tool tests
│   ├── test_notifier.py        # Email sender tests
│   ├── test_graph.py           # Workflow structure tests
│   └── test_daily.py           # Integration tests
├── .github/workflows/
│   └── deploy.yml              # CI/CD: test → build → deploy to Lambda
├── Dockerfile                  # Lambda container image (arm64)
├── deploy.sh                   # Manual deploy script
├── requirements.txt            # Pinned dependencies
├── config.json                 # Topics & email config (gitignored)
├── .env.example                # Environment variables template
└── .gitignore
```

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your API keys
```

### Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key (free tier) |
| `TAVILY_API_KEY` | Tavily search API key |
| `GMAIL_ADDRESS` | Sender Gmail address |
| `GMAIL_APP_PASSWORD` | Gmail App Password |

### Config

Create `config.json` at the project root:

```json
{
  "topics": ["Financial Market", "AI Latest News"],
  "email": {
    "to": ["your@email.com"]
  }
}
```

## Usage

### Single topic (interactive)

```bash
python src/main.py
```

### Single topic (CLI argument)

```bash
python src/main.py "AI Latest News"
```

### Daily report (all topics → email)

```bash
python src/daily.py
```

## Testing

```bash
pytest tests/ -v
```

All external APIs (Groq, Tavily, Gmail) are mocked — no real calls are made during testing.

## Deployment

Deployed as a Docker container on AWS Lambda (arm64), triggered daily by EventBridge Scheduler.

### Manual deploy

```bash
bash deploy.sh news-analyst-agent
```

### CI/CD (GitHub Actions)

- Every push/PR → runs tests
- Push to `master` + tests pass → builds Docker image → pushes to ECR → updates Lambda

Required GitHub Secrets: `AWS_ROLE_ARN`

## Tech Stack

- **LLM**: Groq (llama-3.3-70b-versatile)
- **Orchestration**: LangGraph + LangChain
- **Search**: Tavily API
- **Database**: SQLite
- **Email**: Gmail SMTP
- **Deployment**: AWS Lambda + ECR + EventBridge
- **CI/CD**: GitHub Actions (OIDC auth)
