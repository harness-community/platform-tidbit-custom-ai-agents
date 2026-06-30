import json
import os
import sys

import anthropic

INSTRUCTIONS_PATH = os.path.join(os.path.dirname(__file__), "instructions.md")

# Terraform plans can be very large; cap what we send to the model
MAX_PLAN_CHARS = 12_000


def load_plan(path: str) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path) as f:
            content = f.read().strip()
        if len(content) > MAX_PLAN_CHARS:
            half = MAX_PLAN_CHARS // 2
            content = (
                content[:half]
                + f"\n\n[... {len(content) - MAX_PLAN_CHARS} characters truncated ...]\n\n"
                + content[-half:]
            )
        return f"### TERRAFORM PLAN\n{content}\n"
    except OSError:
        return ""


def build_context() -> str:
    parts: list[str] = []

    plan = load_plan(os.environ.get("PLAN_PATH", ""))
    if plan:
        parts.append(plan)

    workspace = os.environ.get("WORKSPACE", "").strip()
    if workspace:
        parts.append(f"### WORKSPACE\n{workspace}\n")

    changed = os.environ.get("CHANGED_MODULES", "").strip()
    if changed:
        parts.append(f"### CHANGED MODULES\n{changed}\n")

    policy_notes = os.environ.get("POLICY_NOTES", "").strip()
    if policy_notes:
        parts.append(f"### POLICY NOTES\n{policy_notes}\n")

    return "\n".join(parts) or "No Terraform plan provided."


def write_output(result: dict) -> None:
    output_path = "/harness/output.env"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    def safe(value) -> str:
        return str(value).replace("\n", " ").replace('"', "'")

    with open(output_path, "a") as f:
        f.write(f'AGENT_RISK_LEVEL={safe(result.get("risk_level", "unknown"))}\n')
        f.write(f'AGENT_APPLY_RECOMMENDED={safe(result.get("apply_recommended", False)).lower()}\n')
        f.write(f'AGENT_SUMMARY={safe(result.get("summary", ""))}\n')

        counts = result.get("resources_changed", {})
        f.write(f'AGENT_RESOURCES_ADD={safe(counts.get("add", 0))}\n')
        f.write(f'AGENT_RESOURCES_CHANGE={safe(counts.get("change", 0))}\n')
        f.write(f'AGENT_RESOURCES_DESTROY={safe(counts.get("destroy", 0))}\n')


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
            "apply_recommended": False,
            "summary": "Agent returned unstructured output — manual review required.",
            "resources_changed": {},
        }

    print(json.dumps(result, indent=2))
    write_output(result)

    criticals = [f for f in result.get("findings", []) if f.get("severity") == "critical"]
    if criticals:
        print("\nCritical findings:")
        for f in criticals:
            print(f"  {f.get('resource', 'unknown')}: {f.get('description', '')}")

    if not result.get("apply_recommended", True):
        sys.exit(1)


if __name__ == "__main__":
    main()
