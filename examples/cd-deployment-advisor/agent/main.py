import json
import os
import sys

import anthropic

INSTRUCTIONS_PATH = os.path.join(os.path.dirname(__file__), "instructions.md")


def load_file(path: str, label: str, max_chars: int = 8000) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path) as f:
            content = f.read().strip()
        if not content:
            return ""
        if path.endswith(".json"):
            try:
                parsed = json.loads(content)
                content = json.dumps(parsed, indent=2)
            except json.JSONDecodeError:
                pass
        return f"### {label}\n{content[:max_chars]}\n"
    except OSError:
        return ""


def build_context() -> str:
    parts: list[str] = []

    manifest = load_file(os.environ.get("MANIFEST_PATH", ""), "MANIFEST")
    if manifest:
        parts.append(manifest)

    change_summary = os.environ.get("CHANGE_SUMMARY", "").strip()
    if change_summary:
        parts.append(f"### CHANGE SUMMARY\n{change_summary}\n")

    metrics = load_file(os.environ.get("METRICS_PATH", ""), "CURRENT METRICS", max_chars=2000)
    if metrics:
        parts.append(metrics)

    env = os.environ.get("ENVIRONMENT", "").strip()
    service = os.environ.get("SERVICE_NAME", "").strip()
    env_line = f"### ENVIRONMENT\nService: {service}\nTarget environment: {env}\n"
    parts.append(env_line)

    return "\n".join(parts) or "No deployment context provided."


def write_output(result: dict) -> None:
    output_path = "/harness/output.env"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    def safe(value) -> str:
        return str(value).replace("\n", " ").replace('"', "'")

    with open(output_path, "a") as f:
        f.write(f'AGENT_RISK_LEVEL={safe(result.get("risk_level", "unknown"))}\n')
        f.write(f'AGENT_PROCEED={safe(result.get("proceed", True)).lower()}\n')
        f.write(f'AGENT_STRATEGY={safe(result.get("suggested_strategy", "none"))}\n')
        f.write(f'AGENT_SUMMARY={safe(result.get("summary", ""))}\n')


def main() -> None:
    with open(INSTRUCTIONS_PATH) as f:
        system_prompt = f.read()

    context = build_context()
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": context}],
    )

    raw = response.content[0].text.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        print(f"WARNING: agent returned non-JSON output:\n{raw}", file=sys.stderr)
        result = {
            "risk_level": "unknown",
            "proceed": False,
            "suggested_strategy": "manual_gate",
            "summary": "Agent returned unstructured output — manual review required.",
        }

    print(json.dumps(result, indent=2))
    write_output(result)

    findings = result.get("findings", [])
    errors = [f for f in findings if f.get("severity") == "error"]
    if errors:
        print("\nFindings requiring attention:")
        for finding in errors:
            print(f"  [{finding['severity'].upper()}] {finding['description']}")


if __name__ == "__main__":
    main()
