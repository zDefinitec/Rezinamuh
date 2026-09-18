#!/usr/bin/env python3
"""Check this package's structure and recorded, mechanically checkable outputs.

Only the narrow front matter format used by this package is supported; this is
not a YAML parser. These checks cannot establish semantic equivalence, stylistic
quality, truthful model provenance, a remote commit's existence, or legal review.
No network requests or non-standard-library dependencies are used.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


RULES = set(range(1, 26))
HIGH_RISK_RULES = {1, 5, 6, 9, 13, 14, 15, 16, 17, 23, 25}
REQUIRED_CASES = tuple(f"T{number:02}" for number in range(1, 10)) + (
    "T10a", "T10b", "T11", "T12a", "T12b", "C07-copy", "C07-inplace",
)
RULE_FIELDS = ("**适用与效果：**", "**动作：**", "**跳过与边界：**", "**例：**")
STRUCTURE_FILES = (
    "SKILL.md", "README.md", "LICENSE", "ATTRIBUTION.md", "tests/cases.json",
    "tests/cases.md", "tests/fixtures/protected-input.md",
)
EXECUTION_FILES = (
    "tests/model_outputs.jsonl", "tests/execution.log", "tests/acceptance.md",
    "tests/runs/C07-copy.md", "tests/runs/C07-inplace.md",
)
PARAM_VALUES = {
    "intensity": {"轻度", "中度", "重度"},
    "genre": {"正文", "结构化", "聊天"},
    "output_mode": {"终稿", "审计结果与终稿"},
    "mode": {"pasted", "embedded", "file-copy", "file-inplace"},
}
REGION_MARKER = re.compile(r"<!--\s*(/?)protected:([A-Za-z0-9_.-]+)\s*-->")
MIT_PARAGRAPHS = (
    "Permission is hereby granted, free of charge, to any person obtaining a copy "
    'of this software and associated documentation files (the "Software"), to deal '
    "in the Software without restriction, including without limitation the rights "
    "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell "
    "copies of the Software, and to permit persons to whom the Software is "
    "furnished to do so, subject to the following conditions:",
    "The above copyright notice and this permission notice shall be included in "
    "all copies or substantial portions of the Software.",
    'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR '
    "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, "
    "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE "
    "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER "
    "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, "
    "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN "
    "THE SOFTWARE.",
)
UPSTREAM_COPYRIGHT = "Copyright (c) 2025 Siqi Chen"


class Validator:
    def __init__(self, root: Path, structure_only: bool = False):
        self.root = root.resolve()
        self.structure_only = structure_only
        self.errors: list[str] = []
        self.cases: dict[str, dict[str, Any]] = {}
        self.inputs: dict[str, str] = {}
        self.skill_hash = ""

    def error(self, location: str, message: str) -> None:
        self.errors.append(f"{location}: {message}")

    def read(self, relative: str) -> str | None:
        path = self.root / relative
        try:
            # newline='' preserves CRLF and makes literal checks truly exact.
            with path.open("r", encoding="utf-8", newline="") as handle:
                text = handle.read()
        except (OSError, UnicodeError) as exc:
            self.error(relative, f"cannot read required UTF-8 file ({exc})")
            return None
        if not text.strip():
            self.error(relative, "required file is empty")
        return text

    def check_skill(self, skill: str) -> None:
        # Hash original file bytes, including its newline encoding.
        self.skill_hash = hashlib.sha256(skill.encode("utf-8")).hexdigest()
        match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", skill, re.S)
        if not match:
            self.error("SKILL.md", "missing narrow-format YAML front matter")
            return
        front = match.group(1).replace("\r\n", "\n")
        names = re.findall(r"^name:\s*(.*?)\s*$", front, re.M)
        if names != ["rezinamuh"]:
            self.error("SKILL.md", "name must occur once as name: rezinamuh")
        descriptions = re.findall(r"^description:\s*>-\s*\n((?:[ \t]+[^\n]*(?:\n|$))+)", front, re.M)
        if len(descriptions) != 1 or not descriptions[0].strip():
            self.error("SKILL.md", "description must be a nonempty indented >- block")
        metadata = re.findall(r"^metadata:\s*\n((?:[ \t]+[^\n]*(?:\n|$))+)", front, re.M)
        versions = re.findall(r"^  version:[^\n]*$", metadata[0], re.M) if len(metadata) == 1 else []
        if len(versions) != 1 or not re.fullmatch(r"  version:\s*(['\"])1\.0\.0\1\s*", versions[0]):
            self.error("SKILL.md", "metadata.version must occur once as quoted 1.0.0")
        if re.search(r"^version:", front, re.M):
            self.error("SKILL.md", "top-level version is forbidden; use metadata.version")
        license_fields = re.findall(r"^license:\s*(.*?)\s*$", front, re.M)
        if license_fields and license_fields != ["MIT"]:
            self.error("SKILL.md", "optional license field must be MIT")
        body = skill[match.end():]
        headings = list(re.finditer(r"^###\s+(\d+)\.\s+[^\r\n]+", body, re.M))
        numbers = [int(item.group(1)) for item in headings]
        if numbers != list(range(1, 26)):
            self.error("SKILL.md", f"rule headings must be exactly 1..25 in order, found {numbers}")
        for heading in headings:
            number = int(heading.group(1))
            next_heading = re.search(r"^#{1,3}\s+", body[heading.end():], re.M)
            end = heading.end() + next_heading.start() if next_heading else len(body)
            rule_body = body[heading.end():end]
            for field in RULE_FIELDS + (("**禁止：**",) if number in HIGH_RISK_RULES else ()):
                if field not in rule_body:
                    self.error(f"SKILL.md rule {number}", f"missing field {field}")
        groups = re.findall(r"^##\s+([A-E])\.\s+", body, re.M)
        if groups != list("ABCDE"):
            self.error("SKILL.md", "five rule groups must appear once in order as ## A. through ## E.")

    def check_license(self, license_text: str, attribution: str) -> None:
        normalized = " ".join(license_text.split())
        if "MIT License" not in license_text:
            self.error("LICENSE", "missing MIT License title")
        for index, paragraph in enumerate(MIT_PARAGRAPHS, 1):
            if paragraph not in normalized:
                self.error("LICENSE", f"missing or altered complete MIT paragraph {index}")
        # The upstream copyright identity is checked separately from prose.
        if UPSTREAM_COPYRIGHT not in license_text.splitlines():
            self.error("LICENSE", f"missing exact upstream copyright notice: {UPSTREAM_COPYRIGHT}")
        if UPSTREAM_COPYRIGHT not in attribution:
            self.error("ATTRIBUTION.md", "must reproduce the preserved upstream copyright notice")
        if not re.search(r"(?im)^.*(?:commit|提交)[^\r\n]*\b[a-f0-9]{40}\b", attribution):
            self.error("ATTRIBUTION.md", "missing readable upstream commit field with a 40-hex commit id (local format check only)")

    def check_readme(self, readme: str) -> None:
        if not re.search(r"^# Rezinamuh\s*$", readme, re.M):
            self.error("README.md", "display name must be # Rezinamuh")
        if not re.search(r"技能标识[：:]\s*`rezinamuh`", readme):
            self.error("README.md", "skill identifier must be documented as 技能标识：`rezinamuh`")
        if not re.search(r"当前版本[：:]\s*`1\.0\.0`", readme):
            self.error("README.md", "current version must be documented as 当前版本：`1.0.0`")
        if not re.search(r"25\s*条", readme):
            self.error("README.md", "must document the package's 25 rules")

    def string_list(self, value: Any, location: str) -> bool:
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            self.error(location, "must be an array of nonempty strings")
            return False
        if len(value) != len(set(value)):
            self.error(location, "contains duplicate entries")
            return False
        return True

    def rule_list(self, value: Any, location: str) -> None:
        if not isinstance(value, list) or any(type(item) is not int or item not in RULES for item in value):
            self.error(location, "must be an array of integer rule ids in 1..25")
        elif len(value) != len(set(value)):
            self.error(location, "contains duplicate rule ids")

    def check_params(self, params: Any, location: str) -> None:
        if not isinstance(params, dict):
            self.error(location, "params must be an object")
            return
        for key, allowed in PARAM_VALUES.items():
            if not isinstance(params.get(key), str) or params[key] not in allowed:
                self.error(location, f"{key} must be one of {sorted(allowed)}")
        if type(params.get("decoration")) is not bool:
            self.error(location, "decoration must be boolean")
        if "max_chars" in params and (type(params["max_chars"]) is not int or params["max_chars"] < 1):
            self.error(location, "max_chars must be a positive integer")
        if "target_sample" in params and (not isinstance(params["target_sample"], str) or not params["target_sample"].strip()):
            self.error(location, "target_sample must be a nonempty string")

    def regions(self, text: str, location: str) -> tuple[dict[str, str], list[str]]:
        found: dict[str, str] = {}
        order: list[str] = []
        opened: tuple[str, int] | None = None
        for marker in REGION_MARKER.finditer(text):
            close, region_id = marker.groups()
            if not close:
                if opened is not None:
                    self.error(location, f"nested protected region {region_id}")
                if region_id in found or (opened and opened[0] == region_id):
                    self.error(location, f"duplicate protected region {region_id}")
                opened = (region_id, marker.start())
            elif opened is None or opened[0] != region_id:
                self.error(location, f"unmatched closing protected region {region_id}")
            else:
                found[region_id] = text[opened[1]:marker.end()]
                order.append(region_id)
                opened = None
        if opened:
            self.error(location, f"unclosed protected region {opened[0]}")
        return found, order

    def check_cases(self, document: str) -> None:
        try:
            data = json.loads(document)
        except json.JSONDecodeError as exc:
            self.error("tests/cases.json", f"invalid JSON ({exc})")
            return
        if not isinstance(data, dict):
            self.error("tests/cases.json", "top level must be an object")
            return
        if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
            self.error("tests/cases.json", "schema_version must be integer 1")
        if data.get("length_metric") != "unicode_codepoints":
            self.error("tests/cases.json", "length_metric must be unicode_codepoints")
        cases = data.get("cases")
        if not isinstance(cases, list) or not cases:
            self.error("tests/cases.json", "cases must be a nonempty array")
            return
        for index, case in enumerate(cases):
            location = f"tests/cases.json case[{index}]"
            if not isinstance(case, dict):
                self.error(location, "case must be an object")
                continue
            case_id = case.get("id")
            if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", case_id):
                self.error(location, "id must be a nonempty portable identifier")
                continue
            location = f"case {case_id}"
            if case_id in self.cases:
                self.error(location, "duplicate case id")
                continue
            self.cases[case_id] = case
            sources = [key for key in ("input", "fixture", "input_from") if key in case]
            if len(sources) != 1 or not isinstance(case.get(sources[0]), str) or not case[sources[0]]:
                self.error(location, "provide exactly one nonempty input, fixture, or input_from")
            elif sources[0] == "input":
                self.inputs[case_id] = case["input"]
            elif sources[0] == "fixture":
                tests_root = (self.root / "tests").resolve()
                fixture = (tests_root / case["fixture"]).resolve()
                if Path(case["fixture"]).is_absolute() or not fixture.is_relative_to(tests_root):
                    self.error(location, "fixture must remain inside tests/ using a relative path")
                else:
                    text = self.read(str(fixture.relative_to(self.root)))
                    if text is not None:
                        self.inputs[case_id] = text
            self.check_params(case.get("params"), location)
            for field in ("rules", "skip_rules"):
                self.rule_list(case.get(field), f"{location}.{field}")
            rules, skip_rules = case.get("rules"), case.get("skip_rules")
            if isinstance(rules, list) and isinstance(skip_rules, list) and any(item in skip_rules for item in rules):
                self.error(location, "rules and skip_rules overlap")
            for field in ("invariants", "forbidden"):
                self.string_list(case.get(field), f"{location}.{field}")
            for field in ("protected_regions", "protected_literals", "forbidden_literals"):
                if field in case:
                    self.string_list(case[field], f"{location}.{field}")
            for field in ("expect_budget_conflict", "no_growth"):
                if field in case and type(case[field]) is not bool:
                    self.error(location, f"{field} must be boolean")
            if case.get("expect_budget_conflict") and (not isinstance(case.get("params"), dict) or "max_chars" not in case["params"]):
                self.error(location, "expect_budget_conflict requires max_chars")
        # Check all dependencies, including cycles, before interpreting outputs.
        for case_id, case in self.cases.items():
            visited = {case_id}
            dependency = case.get("input_from")
            while dependency is not None:
                if not isinstance(dependency, str) or dependency not in self.cases:
                    self.error(f"case {case_id}", f"unknown input_from reference {dependency!r}")
                    break
                if dependency in visited:
                    self.error(f"case {case_id}", "input_from dependency cycle")
                    break
                visited.add(dependency)
                dependency = self.cases[dependency].get("input_from")
            if case_id in self.inputs:
                text = self.inputs[case_id]
                region_map, _ = self.regions(text, f"case {case_id} input")
                for region_id in case.get("protected_regions", []) if isinstance(case.get("protected_regions", []), list) else []:
                    if isinstance(region_id, str) and region_id not in region_map:
                        self.error(f"case {case_id}", f"protected region {region_id!r} missing from input")
                for literal in case.get("protected_literals", []) if isinstance(case.get("protected_literals", []), list) else []:
                    if isinstance(literal, str) and literal not in text:
                        self.error(f"case {case_id}", f"protected literal {literal!r} missing from input")
        coverage = data.get("rule_coverage")
        if not isinstance(coverage, dict) or set(coverage) != {str(item) for item in RULES}:
            self.error("tests/cases.json", "rule_coverage must have exactly keys '1'..'25'")
        if isinstance(coverage, dict):
            for rule, entry in coverage.items():
                if not isinstance(entry, dict) or entry.get("mode") not in ("apply", "skip"):
                    self.error(f"rule_coverage.{rule}", "must contain case_id and mode apply|skip")
                    continue
                case_id = entry.get("case_id")
                if not isinstance(case_id, str) or case_id not in self.cases:
                    self.error(f"rule_coverage.{rule}", f"unknown case reference {case_id!r}")
                    continue
                field = "rules" if entry["mode"] == "apply" else "skip_rules"
                values = self.cases[case_id].get(field)
                if not rule.isdigit() or not isinstance(values, list) or int(rule) not in values:
                    self.error(f"rule_coverage.{rule}", f"{case_id}.{field} does not include this rule")
        controls = data.get("control_groups")
        if not isinstance(controls, dict) or set(controls) != {f"C{index:02}" for index in range(1, 9)}:
            self.error("tests/cases.json", "control_groups must have exactly C01..C08")
        if isinstance(controls, dict):
            for group, members in controls.items():
                location = f"control_groups.{group}"
                if self.string_list(members, location):
                    if len(members) < 2:
                        self.error(location, "control group requires at least two distinct cases")
                    for case_id in members:
                        if case_id not in self.cases:
                            self.error(location, f"unknown case reference {case_id!r}")
        for case_id in REQUIRED_CASES:
            if case_id not in self.cases:
                self.error("tests/cases.json", f"missing required case {case_id}")
        if "T12b" in self.cases and self.cases["T12b"].get("input_from") != "T12a":
            self.error("case T12b", "second rewrite must use input_from: T12a")
        for case_id in ("T12a", "T12b"):
            if case_id in self.cases and self.cases[case_id].get("no_growth") is not True:
                self.error(f"case {case_id}", "repeated style test requires no_growth: true")
        for case_id, mode in (("C07-copy", "file-copy"), ("C07-inplace", "file-inplace")):
            params = self.cases.get(case_id, {}).get("params")
            if isinstance(params, dict) and params.get("mode") != mode:
                self.error(f"case {case_id}", f"file-mode test requires mode: {mode}")

    def check_outputs(self, document: str) -> None:
        selected: dict[str, dict[str, Any]] = {}
        runs: dict[str, dict[str, Any]] = {}
        for line_number, line in enumerate(document.splitlines(), 1):
            if not line.strip():
                continue
            location = f"tests/model_outputs.jsonl:{line_number}"
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                self.error(location, f"invalid JSON ({exc})")
                continue
            if not isinstance(record, dict):
                self.error(location, "record must be an object")
                continue
            for field in ("run_id", "case_id", "input", "skill_sha256", "generation_method", "model", "observed_at", "raw_response", "final_text"):
                if not isinstance(record.get(field), str) or not record[field].strip():
                    self.error(location, f"{field} must be a nonempty string")
            case_id, run_id = record.get("case_id"), record.get("run_id")
            if not isinstance(case_id, str) or case_id not in self.cases:
                self.error(location, f"unknown case reference {case_id!r}")
                continue
            if not isinstance(run_id, str):
                continue
            if run_id in runs:
                self.error(location, f"duplicate run_id {run_id!r}")
            supersedes = record.get("supersedes")
            if supersedes is not None and (not isinstance(supersedes, str) or supersedes not in runs or runs[supersedes].get("case_id") != case_id):
                self.error(location, "supersedes must reference an earlier run for the same case")
            runs[run_id] = record
            if not isinstance(record.get("skill_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", record["skill_sha256"]):
                self.error(location, "skill_sha256 must be a lowercase SHA-256 hex digest")
            if record.get("status") != "observed":
                self.error(location, "status must be observed")
            self.check_params(record.get("params"), location)
            try:
                timestamp = datetime.fromisoformat(record.get("observed_at", "").replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    raise ValueError("timezone required")
            except (AttributeError, TypeError, ValueError):
                self.error(location, "observed_at must be an ISO 8601 timestamp with timezone")
            if "audit" in record and not isinstance(record["audit"], str):
                self.error(location, "audit must be a string when present")
            if "budget_conflict" in record and type(record["budget_conflict"]) is not bool:
                self.error(location, "budget_conflict must be boolean when present")
            if record.get("skill_sha256") == self.skill_hash:
                selected[case_id] = record
        for case_id, case in self.cases.items():
            record = selected.get(case_id)
            location = f"case {case_id} output"
            if record is None:
                self.error(location, "missing observed output for current SKILL.md SHA-256")
                continue
            input_text, final = record.get("input"), record.get("final_text")
            if not isinstance(input_text, str) or not isinstance(final, str):
                continue
            if record.get("params") != case.get("params"):
                self.error(location, "recorded params differ from case params")
            expected_input = self.inputs.get(case_id)
            dependency = case.get("input_from")
            if dependency is not None and isinstance(dependency, str):
                parent = selected.get(dependency)
                expected_input = parent.get("final_text") if parent else None
            if expected_input is None:
                self.error(location, "cannot resolve actual input")
            elif input_text != expected_input:
                self.error(location, "recorded input differs from declared input or dependency's actual final_text")
            raw = record.get("raw_response")
            if isinstance(raw, str) and final not in raw:
                self.error(location, "raw_response does not contain the exact final_text")
            audit = record.get("audit", "")
            if isinstance(audit, str) and audit and isinstance(raw, str) and audit not in raw:
                self.error(location, "raw_response does not contain the recorded audit")
            params = case.get("params") if isinstance(case.get("params"), dict) else {}
            if params.get("output_mode") == "审计结果与终稿" and (not isinstance(audit, str) or not audit.strip()):
                self.error(location, "audit output mode requires separately recorded nonempty audit")
            limit = params.get("max_chars")
            conflict_expected = case.get("expect_budget_conflict") is True
            has_conflict = record.get("budget_conflict") is True
            public_budget_conflict = (
                conflict_expected and has_conflict and isinstance(audit, str)
                and bool(audit.strip()) and isinstance(raw, str) and audit in raw
            )
            if params.get("mode") in ("pasted", "embedded") and params.get("output_mode") == "终稿" and not public_budget_conflict:
                if raw != final:
                    self.error(location, "final-only raw_response must equal final_text without omitted prefix or suffix")
                if isinstance(audit, str) and audit:
                    self.error(location, "final-only response must not include a nonempty audit")
            if conflict_expected and not has_conflict:
                self.error(location, "expected budget conflict must be recorded as budget_conflict: true")
            if (conflict_expected or has_conflict) and (not isinstance(audit, str) or not audit.strip()):
                self.error(location, "budget conflict must be openly reported in nonempty audit")
            if type(limit) is int and len(final) > limit and not public_budget_conflict:
                self.error(location, f"final_text has {len(final)} Unicode codepoints, exceeds max_chars {limit}")
            if case.get("no_growth") is True and len(final) > len(input_text):
                self.error(location, f"no_growth violated ({len(input_text)} -> {len(final)} Unicode codepoints)")
            source_regions, source_order = self.regions(input_text, f"{location} input regions")
            output_regions, output_order = self.regions(final, f"{location} final regions")
            protected = case.get("protected_regions", [])
            if isinstance(protected, list) and all(isinstance(item, str) for item in protected):
                for region_id in protected:
                    if region_id not in source_regions:
                        self.error(location, f"protected region {region_id!r} missing from actual input")
                    elif output_regions.get(region_id) != source_regions[region_id]:
                        self.error(location, f"protected region {region_id!r} changed or missing (including its markers)")
                if [item for item in output_order if item in protected] != [item for item in source_order if item in protected]:
                    self.error(location, "protected region order changed")
            literals = case.get("protected_literals", [])
            if isinstance(literals, list):
                for literal in literals:
                    if isinstance(literal, str) and (not literal or input_text.count(literal) == 0 or final.count(literal) != input_text.count(literal)):
                        self.error(location, f"protected literal count changed or absent from input: {literal!r}")
            forbidden = case.get("forbidden_literals", [])
            if isinstance(forbidden, list):
                for literal in forbidden:
                    if isinstance(literal, str) and literal and literal in final:
                        self.error(location, f"forbidden literal present: {literal!r}")
            if case_id in ("C07-copy", "C07-inplace"):
                file_path = f"tests/runs/{case_id}.md"
                saved = self.read(file_path)
                if saved is not None and saved != final:
                    self.error(file_path, "saved file differs from the recorded final_text")

    def run(self) -> list[str]:
        contents: dict[str, str] = {}
        for relative in STRUCTURE_FILES + (() if self.structure_only else EXECUTION_FILES):
            text = self.read(relative)
            if text is not None:
                contents[relative] = text
        if "SKILL.md" in contents:
            self.check_skill(contents["SKILL.md"])
        if "README.md" in contents:
            self.check_readme(contents["README.md"])
        if "LICENSE" in contents and "ATTRIBUTION.md" in contents:
            self.check_license(contents["LICENSE"], contents["ATTRIBUTION.md"])
        if "tests/cases.json" in contents:
            self.check_cases(contents["tests/cases.json"])
        if not self.structure_only and "tests/model_outputs.jsonl" in contents:
            self.check_outputs(contents["tests/model_outputs.jsonl"])
        return self.errors


def validate_package(root: Path | str, *, structure_only: bool = False) -> list[str]:
    """Return diagnostics; an empty list means only these mechanical checks pass."""
    return Validator(Path(root), structure_only=structure_only).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="package root (default: this script's package directory)")
    parser.add_argument("--structure-only", action="store_true", help="check package and cases before model outputs exist")
    args = parser.parse_args(argv)
    errors = validate_package(args.root, structure_only=args.structure_only)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"FAIL: {len(errors)} mechanical check(s) failed", file=sys.stderr)
        return 1
    scope = "structure" if args.structure_only else "structure and recorded outputs"
    print(f"PASS: {scope} mechanical checks")
    print("Not checked: semantic equivalence, style quality, independent provenance, remote commit existence, or platform compatibility.")
    print("Front matter validation supports only this package's narrow format, not general YAML.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
