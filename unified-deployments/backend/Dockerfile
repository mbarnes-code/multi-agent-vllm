#
#
FROM python:3.12

RUN apt-get update && \
    apt-get install -y curl && \
    curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

RUN . $HOME/.local/bin/env 
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml uv.lock ./
COPY . .

RUN uv sync

CMD ["uv", "run", "--", "uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]