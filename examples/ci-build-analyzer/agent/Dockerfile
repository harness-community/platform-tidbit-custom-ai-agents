FROM python:3.11-slim

WORKDIR /agent

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the instructions into the image so the agent is self-contained
COPY ../../agent-instructions/ci-build-analyzer.md instructions.md
COPY main.py .

ENTRYPOINT ["python", "main.py"]
