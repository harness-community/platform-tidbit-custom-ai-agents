# Harness Custom AI Agents

This repository demonstrates how to build and use custom AI worker agents in Harness pipelines. Each agent is a Docker container that accepts pipeline context, reasons over it with an LLM, and writes structured output back into the pipeline.

## What is a Harness Custom AI Agent?

A custom AI agent is a pipeline step with two parts:

1. **Instructions** — a Markdown file that serves as the agent's system prompt. It defines the agent's role, what inputs it expects, and how it should format its response.
2. **Runner** — a Python script packaged in a Docker image. It reads pipeline context from environment variables, calls an LLM (Claude) using the instructions, and emits results as Harness output variables.

Agents are invoked as **Plugin** steps in any Harness stage type (CI, CD, IaC, STO, Custom). The pipeline passes context through step settings; the agent writes its findings to `/harness/output.env` so downstream steps can act on them.

## Repository Structure

```
.
├── README.md                        # This file
├── agent-instructions/              # Standalone instruction Markdown files (agent system prompts)
│   ├── ci-build-analyzer.md
│   ├── cd-deployment-advisor.md
│   ├── iac-reviewer.md
│   └── sto-security-triage.md
└── examples/                        # Complete, runnable examples per Harness module
    ├── ci-build-analyzer/           # CI: analyzes build/test failures
    │   ├── pipeline.yaml
    │   └── agent/
    │       ├── main.py
    │       ├── requirements.txt
    │       └── Dockerfile
    ├── cd-deployment-advisor/       # CD: reviews deployment config before rollout
    │   ├── pipeline.yaml
    │   └── agent/
    │       ├── main.py
    │       ├── requirements.txt
    │       └── Dockerfile
    ├── iac-reviewer/                # IaC: reviews Terraform plan for risk and drift
    │   ├── pipeline.yaml
    │   └── agent/
    │       ├── main.py
    │       ├── requirements.txt
    │       └── Dockerfile
    └── sto-security-triage/         # STO: triages vulnerability scan results
        ├── pipeline.yaml
        └── agent/
            ├── main.py
            ├── requirements.txt
            └── Dockerfile
```

## Prerequisites

- A Harness account with at least one Harness Cloud or Kubernetes build infrastructure
- An Anthropic API key stored as a Harness secret named `anthropic_api_key`
- Docker (to build and push agent images)
- Python 3.11+ (to run agents locally during development)

## Creating Your Own Agent

### 1. Write the agent instructions

Create a Markdown file that describes what the agent does, what inputs it receives, and what output format it should produce. This file becomes the LLM system prompt, so be specific.

```markdown
# My Custom Agent

## Role
You are a <describe role>.

## Inputs
You will receive the following context from the Harness pipeline:
- `CONTEXT_VAR`: description of what it contains

## Output Format
Respond only with a JSON object:
\`\`\`json
{
  "summary": "one-line finding",
  "severity": "low | medium | high | critical",
  "recommendations": ["..."]
}
\`\`\`
```

See [`agent-instructions/`](agent-instructions/) for real examples.

### 2. Implement the agent runner

```python
# agent/main.py
import os, json, anthropic

def main():
    with open("/agent/instructions.md") as f:
        system_prompt = f.read()

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    context = os.environ.get("MY_CONTEXT", "")

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": context}],
    )

    result = json.loads(response.content[0].text)
    print(json.dumps(result, indent=2))

    with open("/harness/output.env", "a") as f:
        f.write(f"AGENT_SUMMARY={result['summary']}\n")
        f.write(f"AGENT_SEVERITY={result['severity']}\n")

if __name__ == "__main__":
    main()
```

### 3. Build and push the Docker image

```dockerfile
FROM python:3.11-slim
WORKDIR /agent
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY instructions.md .
COPY main.py .
ENTRYPOINT ["python", "main.py"]
```

```bash
docker build -t myregistry/my-agent:latest ./agent
docker push myregistry/my-agent:latest
```

### 4. Use the agent in a Harness pipeline

```yaml
- step:
    name: My AI Agent
    identifier: My_AI_Agent
    type: Plugin
    spec:
      connectorRef: my_docker_registry
      image: myregistry/my-agent:latest
      settings:
        ANTHROPIC_API_KEY: <+secrets.getValue("anthropic_api_key")>
        MY_CONTEXT: <+execution.steps.Previous_Step.output.outputVariables.LOGS>
```

Downstream steps can reference agent output with:
```
<+execution.steps.My_AI_Agent.output.outputVariables.AGENT_SUMMARY>
<+execution.steps.My_AI_Agent.output.outputVariables.AGENT_SEVERITY>
```

## Examples

| Example | Module | What it does |
|---------|--------|--------------|
| [ci-build-analyzer](examples/ci-build-analyzer/) | CI | Reads build logs and test results, identifies root causes, suggests fixes |
| [cd-deployment-advisor](examples/cd-deployment-advisor/) | CD | Evaluates a deployment manifest and change context before rollout |
| [iac-reviewer](examples/iac-reviewer/) | IaC Management | Reviews a Terraform plan, flags risky changes and policy violations |
| [sto-security-triage](examples/sto-security-triage/) | STO | Triages vulnerability scan output, prioritizes CVEs, drafts remediation notes |
