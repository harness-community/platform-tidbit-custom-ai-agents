import json
import os
import sys
import xml.etree.ElementTree as ET

import anthropic

INSTRUCTIONS_PATH = os.path.join(os.path.dirname(__file__), "instructions.md")


def load_file(path: str, label: str) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path) as f:
            content = f.read().strip()
        return f"### {label}\n{content}\n" if content else ""
    except OSError:
        return ""


def summarize_junit(xml_path: str) -> str:
    if not xml_path or not os.path.exists(xml_path):
        return ""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        suites = root.findall(".//testsuite")
        lines = ["### TEST RESULTS (JUnit summary)"]
        for suite in suites:
            tests = suite.get("tests", "?")
            failures = suite.get("failures", "0")
            errors = suite.get("errors", "0")
            lines.append(f"Suite: {suite.get('name')} — {tests} tests, {failures} failures, {errors} errors")
            for case in suite.findall("testcase"):
                failure = case.find("failure")
                error = case.find("error")
                if failure is not None or error is not None:
                    node = failure if failure is not None else error
                    lines.append(f"  FAILED: {case.get('classname')}.{case.get('name')}")
                    lines.append(f"    {(node.text or '').strip()[:300]}")
        return "\n".join(lines) + "\n"
    except ET.ParseError:
        return load_file(xml_path, "TEST RESULTS")


def build_context() -> str:
    parts: list[str] = []

    build_log = load_file(os.environ.get("BUILD_LOG_PATH", ""), "BUILD LOGS")
    if build_log:
        parts.append(build_log[:8000])

    junit_summary = summarize_junit(os.environ.get("TEST_RESULTS_PATH", ""))
    test_log = load_file(os.environ.get("TEST_LOG_PATH", ""), "TEST LOGS")
    if junit_summary:
        parts.append(junit_summary)
    elif test_log:
        parts.append(test_log[:4000])

    changed = os.environ.get("CHANGED_FILES", "").strip()
    if changed:
        parts.append(f"### CHANGED FILES\n{changed}\n")

    return "\n".join(parts) or "No build context provided."


def write_output(result: dict) -> None:
    output_path = "/harness/output.env"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    def safe(value: str) -> str:
        return str(value).replace("\n", " ").replace('"', "'")

    with open(output_path, "a") as f:
        f.write(f'AGENT_VERDICT={safe(result.get("verdict", "unknown"))}\n')
        f.write(f'AGENT_CONFIDENCE={safe(result.get("confidence", "low"))}\n')
        f.write(f'AGENT_SUMMARY={safe(result.get("summary", ""))}\n')
        f.write(f'AGENT_ROOT_CAUSE={safe(result.get("root_cause", ""))}\n')


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
            "verdict": "unknown",
            "root_cause": raw[:500],
            "confidence": "low",
            "summary": "Agent returned unstructured output — see logs.",
        }

    print(json.dumps(result, indent=2))
    write_output(result)

    if result.get("verdict") not in ("pre_existing_failure", "flaky_test", "unknown"):
        sys.exit(0)


if __name__ == "__main__":
    main()
