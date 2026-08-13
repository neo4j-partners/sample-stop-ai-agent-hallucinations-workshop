FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app

ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1 \
    AWS_REGION=us-east-1 \
    AWS_DEFAULT_REGION=us-east-1

COPY agent_requirements.txt agent_requirements.txt

# The last line of agent_requirements.txt installs the shared `workshop` package
# from a local wheel, so the wheel has to be in the image before the install
# runs. 5.1_agentcore_deploy.ipynb builds it into vendor/ from the repository's
# workshop/ directory, which is outside this build context and unreachable from
# inside the image any other way. See vendor/README.md.
COPY vendor/ vendor/
RUN uv pip install -r agent_requirements.txt

RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 8080

COPY --chown=bedrock_agentcore:bedrock_agentcore . .

CMD ["opentelemetry-instrument", "python", "-m", "booking_agent"]
