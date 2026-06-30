import json
import os
import sys

import anthropic

INSTRUCTIONS_PATH = os.path.join(os.path.dirname(__file__), "instructions.md")
MAX_FINDINGS_TO_SEND = 50


def load_scan_results(path: str) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path) as f:
            raw = f.read().strip()
        if not raw or raw == "[]":
            return ""
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                # Truncate to avoid blowing the context window on large scans
                if len(data) > MAX_FINDINGS_TO_SEND:
                    data = sorted(
                        data,
                        key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(
                            x.get("severity", "low"), 4
                        ),
                    )[:MAX_FINDINGS_TO_SEND]
            return f"### SCAN RESULTS\n{json.dumps(data, indent=2)}\n"
        except json.JSONDecodeError:
            return f"### SCAN RESULTS\n{raw[:10000]}\n"
    except OSError:
        return ""


def load_baseline(path: str) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path) as f:
            content = f.read().strip()
        return f"### BASELINE\n{content[:4000]}\n" if content else ""
    except OSError:
        return ""


def build_context() -> str:
    parts: list[str] = []

    scan = load_scan_results(os.environ.get("SCAN_RESULTS_PATH", ""))
    if scan:
        parts.append(scan)

    image = os.environ.get("IMAGE", "").strip()
    if image:
        parts.append(f"### IMAGE\n{image}\n")

    service = os.environ.get("SERVICE", "").strip()
    if service:
        parts.append(f"### SERVICE\n{service}\n")

    baseline = load_baseline(os.environ.get("BASELINE_PATH", ""))
    if baseline:
        parts.append(baseline)

    return "\n".join(parts) or "No scan results provided."


def write_output(result: dict) -> None:
    output_path = "/harness/output.env"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    def safe(value) -> str:
        return str(value).replace("\n", " ").replace('"', "'")

    counts = result.get("severity_counts", {})

    with open(output_path, "a") as f:
        f.write(f'AGENT_GATE={safe(result.get("gate", "fail"))}\n')
        f.write(f'AGENT_SUMMARY={safe(result.get("summary", ""))}\n')
        f.write(f'AGENT_TOTAL_FINDINGS={safe(result.get("total_findings", 0))}\n')
        f.write(f'AGENT_CRITICAL={safe(counts.get("critical", 0))}\n')
        f.write(f'AGENT_HIGH={safe(counts.get("high", 0))}\n')
        f.write(f'AGENT_ESCALATIONS={safe(len(result.get("immediate_escalations", [])))}\n')


def main() -> None:
    with open(INSTRUCTIONS_PATH) as f:
        system_prompt = f.read()

    context = build_context()
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=3000,
        system=system_prompt,
        messages=[{"role": "user", "content": context}],
    )

    raw = response.content[0].text.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        print(f"WARNING: agent returned non-JSON output:\n{raw}", file=sys.stderr)
        result = {
            "gate": "fail",
            "total_findings": 0,
            "severity_counts": {},
            "prioritized_findings": [],
            "immediate_escalations": [],
            "summary": "Agent returned unstructured output — manual security review required.",
        }

    print(json.dumps(result, indent=2))
    write_output(result)

    escalations = result.get("immediate_escalations", [])
    if escalations:
        print(f"\n{'='*60}")
        print("IMMEDIATE ESCALATIONS REQUIRED:")
        for item in escalations:
            print(f"  {item}")
        print(f"{'='*60}")

    if result.get("gate") == "fail":
        sys.exit(1)


if __name__ == "__main__":
    main()
