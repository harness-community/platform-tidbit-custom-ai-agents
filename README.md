# Harness Custom AI Agents

This repository demonstrates how to build and use custom AI worker agents in Harness pipelines. Each agent is a Docker container that accepts pipeline context, reasons over it with an LLM, and writes structured output back into the pipeline.

## What is a Harness Custom AI Agent?

A custom AI agent is a reusable, versioned AI worker that runs as a native step in any Harness pipeline stage. It has two parts:

1. **Instructions** — a Markdown file that serves as the agent's system prompt. It defines the agent's role, what inputs it expects, and how it should format its response.
2. **Agent definition** — registered in Harness with a name, version, and an LLM connector. Once registered, the agent is available to any pipeline in your account.

Agents are invoked using the **Agent** step type. The step references the agent by name and version, specifies the LLM connector to use, and passes pipeline context as inputs. Downstream steps can reference the agent's output variables using standard Harness expressions.

```yaml
- step:
    name: My AI Agent
    identifier: My_AI_Agent
    type: Agent
    spec:
      agentId: my-custom-agent
      agentVersion: 1.0.0
      connectorRef: my_llm_connector
      inputs:
        MY_CONTEXT: <+execution.steps.Previous_Step.output.outputVariables.LOGS>
```

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

- A Harness account with AI Agents enabled
- An LLM connector configured in Harness (Anthropic, OpenAI, or another supported provider)
- At least one Harness Cloud or Kubernetes build infrastructure for the pipeline stages that surround the agent step

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

### 2. Register the agent in Harness

In the Harness UI, navigate to **Account Settings → AI Agents → New Agent**. Provide:

- **Name** and **ID** — used to reference the agent in pipelines
- **Version** — semantic version (e.g., `1.0.0`)
- **Instructions** — paste the contents of your Markdown file, or point to the file in your repo
- **LLM Connector** — select the Harness connector for your LLM provider (Anthropic, OpenAI, etc.)

You can also define agents via the Harness API or YAML:

```yaml
agent:
  name: My Custom Agent
  identifier: my_custom_agent
  version: 1.0.0
  llmConnectorRef: my_llm_connector
  instructions: |
    # My Custom Agent
    ...
```

### 3. Use the agent in a Harness pipeline

Reference the registered agent with the **Agent** step type. Pass pipeline context as inputs and reference the agent's output in downstream steps:

```yaml
- step:
    name: My AI Agent
    identifier: My_AI_Agent
    type: Agent
    spec:
      agentId: my_custom_agent
      agentVersion: 1.0.0
      connectorRef: my_llm_connector
      inputs:
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
