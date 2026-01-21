# DGX Spark Multi-Agent System

A VLLM-based multi-agent framework for distributed inference on DGX Spark clusters.

## Overview

This package provides a multi-agent orchestration system that:

- Uses **VLLM** as the LLM backend for high-performance inference
- Implements **Swarm-style** agent handoffs for specialized task routing
- Includes pre-configured agents for common tasks:
  - **Supervisor Agent**: Routes requests to specialized agents
  - **RAG Agent**: Knowledge retrieval and document search
  - **Coding Agent**: Code generation, debugging, and development
  - **Image Understanding Agent**: Visual analysis and multimodal tasks

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -e .

# Set VLLM endpoint
export VLLM_ENDPOINT="http://localhost:8000/v1"

# Run the server
python -m multi_agent.server
```

### Docker

```bash
# Build image
docker build -t dgx-spark-multi-agent .

# Run container
docker run -p 8000:8000 \
  -e VLLM_ENDPOINT="http://vllm-host:8000/v1" \
  dgx-spark-multi-agent
```

### Kubernetes

See the parent `unified-deployments/` directory for Kubernetes manifests.

## API Usage

### Chat Endpoint

```bash
# Basic chat (routes through supervisor)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Write a Python function to calculate fibonacci numbers",
    "session_id": "user123"
  }'

# Direct to coding agent
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Debug this code: def foo(): return bar",
    "agent_type": "coding",
    "session_id": "user123"
  }'
```

### Streaming

```bash
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain quantum computing",
    "stream": true
  }'
```

### List Agents

```bash
curl http://localhost:8000/agents
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `VLLM_ENDPOINT` | `http://vllm-service.vllm-system.svc.cluster.local:8000/v1` | VLLM API endpoint |
| `SUPERVISOR_MODEL` | `gpt-oss-120b` | Model for supervisor agent |
| `RAG_MODEL` | `gpt-oss-20b` | Model for RAG agent |
| `CODING_MODEL` | `meta-llama/Llama-3.1-8B-Instruct` | Model for coding agent |
| `IMAGE_MODEL` | `microsoft/Phi-4` | Model for image agent |
| `MILVUS_HOST` | `milvus` | Milvus vector DB host |
| `MILVUS_PORT` | `19530` | Milvus port |
| `WORKSPACE_DIR` | `/tmp/coding_workspace` | Coding agent workspace |
| `ENABLE_CODE_EXECUTION` | `true` | Allow code execution |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Request                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Supervisor Agent                          │
│  • Analyzes request intent                                  │
│  • Routes to specialized agent                              │
│  • Coordinates multi-agent tasks                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  RAG Agent  │   │Coding Agent │   │ Image Agent │
│             │   │             │   │             │
│ • Search    │   │ • Generate  │   │ • Analyze   │
│ • Retrieve  │   │ • Debug     │   │ • OCR       │
│ • Summarize │   │ • Test      │   │ • Describe  │
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       │                 │                 │
       ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    VLLM Backend                             │
│  • Distributed inference across DGX Sparks                  │
│  • Ray cluster for tensor parallelism                       │
│  • OpenAI-compatible API                                    │
└─────────────────────────────────────────────────────────────┘
```

## Agents

### Supervisor Agent

The supervisor analyzes incoming requests and routes them to the appropriate specialized agent. It can also handle general queries directly.

**Capabilities:**
- Request classification
- Agent routing
- Multi-agent coordination
- General assistance

### RAG Agent

Retrieval-Augmented Generation agent for knowledge-intensive tasks.

**Capabilities:**
- Knowledge base search
- Document retrieval
- Summarization
- Question answering with citations

**Tools:**
- `search_knowledge_base(query, top_k)`
- `get_document(document_id)`
- `summarize_documents(document_ids)`

### Coding Agent

Autonomous coding agent for software development tasks.

**Capabilities:**
- Code generation in multiple languages
- Debugging and error analysis
- Code review and refactoring
- Test generation
- Code explanation

**Tools:**
- `execute_code(code, language)` - Run code in sandbox
- `analyze_code(code, language)` - Static analysis
- `search_code_patterns(query, language)` - Find patterns
- `generate_tests(code, language)` - Create unit tests
- `explain_code(code, language)` - Detailed explanation
- `write_file(filename, content)` - Write to workspace
- `read_file(filename)` - Read from workspace
- `list_files(directory)` - List workspace files

**Supported Languages:**
- Python, JavaScript, TypeScript
- Go, Rust, Java
- C, C++, Bash

### Image Understanding Agent

Visual analysis agent for multimodal tasks.

**Capabilities:**
- Image analysis and description
- Text extraction (OCR)
- Visual question answering
- Image comparison

**Tools:**
- `analyze_image(image_path)`
- `extract_text(image_path)`
- `describe_image(image_path, detail_level)`
- `compare_images(image_paths)`
- `get_image_metadata(image_path)`

## Development

### Project Structure

```
multi_agent/
├── __init__.py          # Package exports
├── core.py              # Swarm implementation
├── server.py            # FastAPI server
├── main.py              # Entry point
├── agents/
│   ├── __init__.py
│   ├── supervisor.py    # Supervisor agent
│   ├── rag.py           # RAG agent
│   ├── coding.py        # Coding agent
│   └── image_understanding.py
└── tools/
    ├── __init__.py
    └── common.py        # Shared tools
```

### Adding New Agents

1. Create agent file in `agents/`:

```python
from ..core import Agent, Result

MY_AGENT_INSTRUCTIONS = """..."""

class MyAgent:
    def __init__(self, model: str = "gpt-oss-120b"):
        self.model = model
    
    def _create_functions(self) -> list:
        def my_tool(arg: str) -> str:
            """Tool description."""
            return "result"
        return [my_tool]
    
    def create(self) -> Agent:
        return Agent(
            name="My Agent",
            model=self.model,
            instructions=MY_AGENT_INSTRUCTIONS,
            functions=self._create_functions(),
        )
```

2. Register in `agents/__init__.py`
3. Add to supervisor's routing in `supervisor.py`
4. Update server initialization in `server.py`

### Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Type checking
mypy multi_agent/

# Linting
ruff check multi_agent/
```

## License

Apache 2.0
