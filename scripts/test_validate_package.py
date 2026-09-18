#!/usr/bin/env python3
"""Isolated mutation tests for the standard-library package validator."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import validate_package as validator


PARAMS = {
    "intensity": "中度", "genre": "正文", "output_mode": "终稿",
    "mode": "pasted", "decoration": False,
}
FIXTURE = (
    "外围正文。\n"
    "<!-- protected:table -->\n| 名称 | 数值 |\n| --- | --- |\n| 甲 | 10 |\n| 乙 | 20 |\n<!-- /protected:table -->\n"
    "<!-- protected:literal -->\n按钮在右上角。\n<!-- /protected:literal -->\n"
    "<!-- protected:code -->\n```sh\necho 'A-B'\n```\n<!-- /protected:code -->\n"
)


def skill_text() -> str:
    text = "---\nname: rezinamuh\ndescription: >-\n  独立校验测试技能。\nmetadata:\n  version: '1.0.0'\nlicense: MIT\n---\n"
    for number in range(1, 26):
        if (number - 1) % 5 == 0:
            text += f"\n## {'ABCDE'[(number - 1) // 5]}. 规则组\n"
        text += f"\n### {number}. 测试规则\n\n"
        text += "\n".join(f"{field}独立测试数据。" for field in validator.RULE_FIELDS) + "\n"
        if number in validator.HIGH_RISK_RULES:
            text += "**禁止：**不得增加事实。\n"
    return text


def case(case_id: str, **extra: object) -> dict:
    value = {
        "id": case_id, "input": "我明天不去。", "params": copy.deepcopy(PARAMS),
        "rules": [], "skip_rules": [], "invariants": ["保留原意"],
        "forbidden": ["增加原因"],
    }
    value.update(extra)
    return value


class ValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="rezinamuh-validator-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for directory in ("tests/fixtures", "tests/runs"):
            (self.root / directory).mkdir(parents=True)
        self.write("SKILL.md", skill_text())
        self.write("README.md", "# Rezinamuh\n技能标识：`rezinamuh`。当前版本：`1.0.0`，25 条规则。\n")
        self.write("LICENSE", "MIT License\n\n" + validator.UPSTREAM_COPYRIGHT + "\n\n" + "\n\n".join(validator.MIT_PARAGRAPHS) + "\n")
        self.write("ATTRIBUTION.md", "upstream commit: " + "a" * 40 + "\n" + validator.UPSTREAM_COPYRIGHT + "\n")
        self.write("tests/fixtures/protected-input.md", FIXTURE)
        self.write("tests/cases.md", "测试场景说明。\n")
        self.write("tests/execution.log", "Tests use synthetic fixture data only.\n")
        self.write("tests/acceptance.md", "Mechanical checks only, no semantic claim.\n")
        file_cases = []
        for case_id, mode in (("C07-copy", "file-copy"), ("C07-inplace", "file-inplace")):
            item = case(case_id, fixture="fixtures/protected-input.md", protected_regions=["table", "literal", "code"])
            del item["input"]
            item["params"]["mode"] = mode
            file_cases.append(item)
        first = case("T01", rules=list(range(1, 26)), protected_literals=["明天"])
        scenarios = [case(case_id) for case_id in validator.REQUIRED_CASES if case_id not in {"T01", "T12b", "C07-copy", "C07-inplace"}]
        next(item for item in scenarios if item["id"] == "T12a")["no_growth"] = True
        repeated = case("T12b", input_from="T12a", no_growth=True)
        del repeated["input"]
        self.data = {
            "schema_version": 1, "length_metric": "unicode_codepoints",
            "cases": [first, *file_cases, *scenarios, repeated],
            "rule_coverage": {str(number): {"case_id": "T01", "mode": "apply"} for number in range(1, 26)},
            "control_groups": {f"C{number:02}": ["C07-copy", "C07-inplace"] for number in range(1, 9)},
        }
        self.save_cases()
        self.records = []
        for item in self.data["cases"]:
            input_text = FIXTURE if "fixture" in item else "我明天不去。"
            self.records.append(self.record(item, input_text))
        self.save_records()
        self.write("tests/runs/C07-copy.md", FIXTURE)
        self.write("tests/runs/C07-inplace.md", FIXTURE)

    def write(self, relative: str, text: str) -> None:
        with (self.root / relative).open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def record(self, item: dict, input_text: str) -> dict:
        return {
            "run_id": f"run-{item['id']}", "case_id": item["id"],
            "input": input_text, "params": copy.deepcopy(item["params"]),
            "skill_sha256": hashlib.sha256((self.root / "SKILL.md").read_bytes()).hexdigest(),
            "generation_method": "synthetic unit-test fixture, not model behavior evidence",
            "model": "unit-test-fixture", "observed_at": "2026-09-18T00:00:00+00:00",
            "raw_response": input_text, "final_text": input_text, "status": "observed",
        }

    def save_cases(self) -> None:
        self.write("tests/cases.json", json.dumps(self.data, ensure_ascii=False, indent=2) + "\n")

    def save_records(self) -> None:
        self.write("tests/model_outputs.jsonl", "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in self.records))

    def set_final(self, index: int, final_text: str, *, sync_file: bool = True) -> None:
        self.records[index]["final_text"] = final_text
        self.records[index]["raw_response"] = final_text
        self.save_records()
        if sync_file and self.records[index]["case_id"].startswith("C07-"):
            self.write(f"tests/runs/{self.records[index]['case_id']}.md", final_text)

    def assertError(self, needle: str, *, structure_only: bool = False) -> None:
        errors = validator.validate_package(self.root, structure_only=structure_only)
        self.assertTrue(any(needle in error for error in errors), f"expected {needle!r}; got {errors!r}")

    def test_valid_full_package(self) -> None:
        self.assertEqual([], validator.validate_package(self.root))

    def test_structure_only_does_not_require_execution_artifacts(self) -> None:
        for relative in validator.EXECUTION_FILES:
            (self.root / relative).unlink()
        self.assertEqual([], validator.validate_package(self.root, structure_only=True))
        self.assertError("cannot read required")

    def test_missing_rule_number(self) -> None:
        self.write("SKILL.md", skill_text().replace("### 12. 测试规则", "### 删除规则"))
        self.assertError("exactly 1..25", structure_only=True)

    def test_duplicate_rule_number(self) -> None:
        self.write("SKILL.md", skill_text().replace("### 12. 测试规则", "### 11. 测试规则"))
        self.assertError("exactly 1..25", structure_only=True)

    def test_missing_rule_field(self) -> None:
        self.write("SKILL.md", skill_text().replace("**动作：**", "动作：", 1))
        self.assertError("rule 1: missing field **动作：**", structure_only=True)

    def test_missing_high_risk_prohibition(self) -> None:
        self.write("SKILL.md", skill_text().replace("**禁止：**", "禁止：", 1))
        self.assertError("rule 1: missing field **禁止：**", structure_only=True)

    def test_wrong_slug(self) -> None:
        self.write("SKILL.md", skill_text().replace("name: rezinamuh", "name: humanizer"))
        self.assertError("name must occur once", structure_only=True)

    def test_wrong_version(self) -> None:
        self.write("SKILL.md", skill_text().replace("version: '1.0.0'", "version: '3.0.0'"))
        self.assertError("metadata.version", structure_only=True)

    def test_readme_current_version_must_match(self) -> None:
        self.write("README.md", "# Rezinamuh\n技能标识：`rezinamuh`。当前版本：`3.0.0`，25 条规则。\n")
        self.assertError("README.md: current version", structure_only=True)

    def test_readme_slug_must_match(self) -> None:
        self.write("README.md", "# Rezinamuh\n技能标识：`humanizer`。当前版本：`1.0.0`，25 条规则。\n")
        self.assertError("README.md: skill identifier", structure_only=True)

    def test_duplicate_version(self) -> None:
        self.write("SKILL.md", skill_text().replace("version: '1.0.0'", "version: '1.0.0'\n  version: '2.0.0'"))
        self.assertError("metadata.version", structure_only=True)

    def test_top_level_version(self) -> None:
        self.write("SKILL.md", skill_text().replace("license: MIT", "version: 1.0.0\nlicense: MIT"))
        self.assertError("top-level version", structure_only=True)

    def test_missing_group(self) -> None:
        self.write("SKILL.md", skill_text().replace("## D. 规则组", "## 格式规则"))
        self.assertError("five rule groups", structure_only=True)

    def test_missing_upstream_copyright(self) -> None:
        self.write("LICENSE", (self.root / "LICENSE").read_text().replace(validator.UPSTREAM_COPYRIGHT, "Copyright (c) 2026 Someone Else"))
        self.assertError("exact upstream copyright", structure_only=True)

    def test_missing_mit_warranty(self) -> None:
        self.write("LICENSE", (self.root / "LICENSE").read_text().replace(validator.MIT_PARAGRAPHS[-1], ""))
        self.assertError("MIT paragraph 3", structure_only=True)

    def test_file_hash_cannot_replace_commit_field(self) -> None:
        self.write("ATTRIBUTION.md", "upstream file SHA-256: " + "a" * 64 + "\n" + validator.UPSTREAM_COPYRIGHT)
        self.assertError("upstream commit field", structure_only=True)

    def test_bad_case_dependency(self) -> None:
        self.data["cases"][-1]["input_from"] = "absent"
        self.save_cases()
        self.assertError("unknown input_from reference", structure_only=True)

    def test_case_dependency_cycle(self) -> None:
        self.data["cases"][-1]["input_from"] = "T12b"
        self.save_cases()
        self.assertError("dependency cycle", structure_only=True)

    def test_required_scenario_cannot_be_removed(self) -> None:
        self.data["cases"] = [item for item in self.data["cases"] if item["id"] != "T10a"]
        self.save_cases()
        self.assertError("missing required case T10a", structure_only=True)

    def test_repeat_cannot_be_replaced_with_fixed_input(self) -> None:
        del self.data["cases"][-1]["input_from"]
        self.data["cases"][-1]["input"] = "我明天不去。"
        self.save_cases()
        self.assertError("second rewrite must use input_from", structure_only=True)

    def test_bad_coverage_reference(self) -> None:
        self.data["rule_coverage"]["1"]["case_id"] = "absent"
        self.save_cases()
        self.assertError("rule_coverage.1: unknown case", structure_only=True)

    def test_coverage_apply_and_skip_must_match(self) -> None:
        self.data["rule_coverage"]["1"]["mode"] = "skip"
        self.save_cases()
        self.assertError("skip_rules does not include", structure_only=True)

    def test_bad_control_reference(self) -> None:
        self.data["control_groups"]["C01"] = ["T01", "absent"]
        self.save_cases()
        self.assertError("control_groups.C01: unknown case", structure_only=True)

    def test_bad_result_case_reference(self) -> None:
        self.records[0]["case_id"] = "absent"
        self.save_records()
        self.assertError("unknown case reference")

    def test_bad_supersedes_reference(self) -> None:
        self.records[0]["supersedes"] = "absent"
        self.save_records()
        self.assertError("supersedes must reference")

    def test_missing_current_skill_output(self) -> None:
        self.records[0]["skill_sha256"] = "b" * 64
        self.save_records()
        self.assertError("missing observed output for current")

    def test_latest_matching_hash_record_wins_and_old_failure_remains(self) -> None:
        correct = copy.deepcopy(self.records[1])
        self.records[1]["final_text"] = "wrong old output"
        self.records[1]["raw_response"] = "wrong old output"
        correct["run_id"] = "rerun-C07-copy"
        correct["supersedes"] = "run-C07-copy"
        self.records.append(correct)
        # A later record for another skill version must not replace this one.
        old_version = copy.deepcopy(correct)
        old_version.update(run_id="other-version", skill_sha256="f" * 64, final_text="different", raw_response="different")
        self.records.append(old_version)
        self.save_records()
        self.assertEqual([], validator.validate_package(self.root))

    def test_changed_protected_region(self) -> None:
        self.set_final(1, FIXTURE.replace("按钮在右上角。", "按钮在左上角。"))
        self.assertError("protected region 'literal' changed")

    def test_reordered_table_rows(self) -> None:
        self.set_final(1, FIXTURE.replace("| 甲 | 10 |\n| 乙 | 20 |", "| 乙 | 20 |\n| 甲 | 10 |"))
        self.assertError("protected region 'table' changed")

    def test_identical_literal_elsewhere_does_not_hide_change(self) -> None:
        altered = FIXTURE.replace("按钮在右上角。", "按钮在左上角。") + "\n按钮在右上角。\n"
        self.set_final(1, altered)
        self.assertError("protected region 'literal' changed")

    def test_reordered_protected_regions(self) -> None:
        region_map, _ = validator.Validator(self.root).regions(FIXTURE, "fixture")
        reordered = "外围正文。\n" + region_map["code"] + "\n" + region_map["literal"] + "\n" + region_map["table"] + "\n"
        self.set_final(1, reordered)
        self.assertError("protected region order changed")

    def test_duplicate_protected_region(self) -> None:
        region_map, _ = validator.Validator(self.root).regions(FIXTURE, "fixture")
        self.set_final(1, FIXTURE + region_map["literal"])
        self.assertError("duplicate protected region literal")

    def test_missing_marker_even_if_inner_text_preserved(self) -> None:
        self.set_final(1, FIXTURE.replace("<!-- protected:literal -->", ""))
        self.assertError("unmatched closing protected region literal")

    def test_protected_literal_count(self) -> None:
        self.set_final(0, "我明天不去。明天。")
        self.assertError("protected literal count changed")

    def test_unicode_length_counts_codepoints_including_whitespace(self) -> None:
        self.data["cases"][0]["params"]["max_chars"] = 4
        self.records[0]["params"]["max_chars"] = 4
        self.save_cases()
        self.set_final(0, "明天😀\n ")
        self.assertError("5 Unicode codepoints, exceeds max_chars 4")

    def test_declared_budget_conflict_can_exceed_limit(self) -> None:
        item, record = self.data["cases"][1], self.records[1]
        item["expect_budget_conflict"] = True
        item["params"]["max_chars"] = 20
        record["params"]["max_chars"] = 20
        record["budget_conflict"] = True
        record["audit"] = "保护内容超过20码点，无法满足长度要求，按原文保留。"
        record["raw_response"] = record["audit"] + "\n\n" + FIXTURE
        self.save_cases()
        self.save_records()
        self.assertEqual([], validator.validate_package(self.root))

    def test_conflict_requires_public_audit(self) -> None:
        self.data["cases"][1]["expect_budget_conflict"] = True
        self.data["cases"][1]["params"]["max_chars"] = 20
        self.records[1]["params"]["max_chars"] = 20
        self.records[1]["budget_conflict"] = True
        self.save_cases()
        self.save_records()
        self.assertError("openly reported in nonempty audit")

    def test_unrequested_conflict_does_not_bypass_length(self) -> None:
        self.data["cases"][1]["params"]["max_chars"] = 20
        self.records[1]["params"]["max_chars"] = 20
        self.records[1].update(budget_conflict=True, audit="冲突")
        self.records[1]["raw_response"] = "冲突\n" + FIXTURE
        self.save_cases()
        self.save_records()
        self.assertError("exceeds max_chars 20")

    def test_audit_is_not_counted_in_final_length(self) -> None:
        item, record = self.data["cases"][0], self.records[0]
        item["params"].update(max_chars=6, output_mode="审计结果与终稿")
        record["params"] = copy.deepcopy(item["params"])
        record["audit"] = "这是一段超过终稿长度的独立审计说明。"
        record["raw_response"] = record["audit"] + "\n" + record["final_text"]
        self.save_cases()
        self.save_records()
        self.assertEqual([], validator.validate_package(self.root))

    def test_audit_must_have_been_in_raw_response(self) -> None:
        self.records[0]["audit"] = "这段记录没有出现在实际响应中。"
        self.save_records()
        self.assertError("raw_response does not contain the recorded audit")

    def test_final_must_have_been_in_raw_response(self) -> None:
        self.records[0]["raw_response"] = "另一个响应"
        self.save_records()
        self.assertError("raw_response does not contain the exact final_text")

    def test_plain_final_response_cannot_hide_prefix(self) -> None:
        self.records[0]["raw_response"] = "以下是改写结果：\n我明天不去。"
        self.save_records()
        self.assertError("raw_response must equal final_text")

    def test_plain_final_response_cannot_hide_suffix(self) -> None:
        self.records[0]["raw_response"] = "我明天不去。\n希望对你有帮助。"
        self.save_records()
        self.assertError("raw_response must equal final_text")

    def test_embedded_final_response_cannot_hide_audit(self) -> None:
        self.data["cases"][0]["params"]["mode"] = "embedded"
        self.records[0]["params"]["mode"] = "embedded"
        self.records[0]["raw_response"] = "审计：保留了时间与否定。\n我明天不去。"
        self.save_cases()
        self.save_records()
        self.assertError("raw_response must equal final_text")

    def test_embedded_final_response_cannot_hide_comment(self) -> None:
        self.data["cases"][0]["params"]["mode"] = "embedded"
        self.records[0]["params"]["mode"] = "embedded"
        self.records[0]["raw_response"] = "我明天不去。<!-- 已完成改写 -->"
        self.save_cases()
        self.save_records()
        self.assertError("raw_response must equal final_text")

    def test_compliant_final_substring_cannot_hide_overlong_actual_response(self) -> None:
        # The selected body is exactly six codepoints; the actual response is longer.
        self.data["cases"][0]["params"]["max_chars"] = 6
        self.records[0]["params"]["max_chars"] = 6
        self.records[0]["raw_response"] = "改写结果：我明天不去。"
        self.save_cases()
        self.save_records()
        self.assertError("raw_response must equal final_text")

    def test_plain_final_response_rejects_nonempty_audit_field(self) -> None:
        # Audit is already a substring, so the existing provenance check passes.
        self.records[0]["audit"] = "明天"
        self.save_records()
        self.assertError("final-only response must not include a nonempty audit")

    def test_undeclared_conflict_cannot_bypass_final_only_response(self) -> None:
        self.records[0]["budget_conflict"] = True
        self.records[0]["audit"] = "我自称存在长度冲突。"
        self.records[0]["raw_response"] = "我自称存在长度冲突。\n我明天不去。"
        self.save_records()
        self.assertError("raw_response must equal final_text")

    def test_pasted_final_response_allows_declared_public_budget_conflict(self) -> None:
        item, record = self.data["cases"][0], self.records[0]
        item["expect_budget_conflict"] = True
        item["params"]["max_chars"] = 3
        record["params"]["max_chars"] = 3
        record["budget_conflict"] = True
        record["audit"] = "无法在3码点内保留完整信息，因此保留原句并报告冲突。"
        record["raw_response"] = record["audit"] + "\n我明天不去。"
        self.save_cases()
        self.save_records()
        self.assertEqual([], validator.validate_package(self.root))

    def test_file_copy_response_allows_operation_summary(self) -> None:
        self.records[1]["raw_response"] = "已创建文件副本。\n" + FIXTURE
        self.save_records()
        self.assertEqual([], validator.validate_package(self.root))

    def test_file_inplace_response_allows_operation_summary(self) -> None:
        self.records[2]["raw_response"] = "已完成文件就地更新。\n" + FIXTURE
        self.save_records()
        self.assertEqual([], validator.validate_package(self.root))

    def test_repeat_must_use_actual_previous_output(self) -> None:
        self.records[-1]["input"] = "不是前次实际输出。"
        self.save_records()
        self.assertError("dependency's actual final_text")

    def test_repeat_cannot_grow(self) -> None:
        self.set_final(-1, "我明天不去。总体而言，我明天不去。")
        self.assertError("no_growth violated")

    def test_missing_required_output_file(self) -> None:
        (self.root / "tests/runs/C07-copy.md").unlink()
        self.assertError("tests/runs/C07-copy.md: cannot read required")

    def test_saved_output_must_match_record_including_final_newline(self) -> None:
        self.write("tests/runs/C07-copy.md", FIXTURE.rstrip("\n"))
        self.assertError("saved file differs")

    def test_fixture_may_not_escape_tests(self) -> None:
        self.data["cases"][1]["fixture"] = "../README.md"
        self.save_cases()
        self.assertError("fixture must remain inside tests", structure_only=True)

    def test_multiple_input_sources_invalid(self) -> None:
        self.data["cases"][0]["input_from"] = "C07-copy"
        self.save_cases()
        self.assertError("exactly one nonempty", structure_only=True)

    def test_file_case_requires_file_mode(self) -> None:
        self.data["cases"][1]["params"]["mode"] = "pasted"
        self.save_cases()
        self.assertError("file-mode test requires mode: file-copy", structure_only=True)

    def test_optional_array_cannot_be_null(self) -> None:
        self.data["cases"][0]["protected_literals"] = None
        self.save_cases()
        self.assertError("protected_literals: must be an array", structure_only=True)

    def test_record_params_must_match_declared_params(self) -> None:
        self.records[0]["params"]["intensity"] = "重度"
        self.save_records()
        self.assertError("recorded params differ from case params")

    def test_list_numbers_outside_regions_do_not_fail_global_number_check(self) -> None:
        # New list markers are not changes to the protected table's data.
        self.set_final(1, FIXTURE.replace("外围正文。", "1. 外围正文。\n2. 外围正文。"))
        self.assertEqual([], validator.validate_package(self.root))

    def test_bad_json_is_diagnostic(self) -> None:
        self.write("tests/cases.json", "{")
        self.assertError("invalid JSON", structure_only=True)

    def test_malformed_params_is_diagnostic_not_exception(self) -> None:
        self.data["cases"][0]["params"] = None
        self.data["cases"][0]["expect_budget_conflict"] = True
        self.save_cases()
        self.assertError("params must be an object", structure_only=True)

    def test_missing_required_output_record(self) -> None:
        self.records.pop()
        self.save_records()
        self.assertError("case T12b output: missing observed output")

    def test_cli_exit_codes(self) -> None:
        command = [sys.executable, str(Path(validator.__file__).resolve()), "--root", str(self.root)]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("PASS", completed.stdout)
        self.assertIn("Not checked: semantic equivalence", completed.stdout)
        (self.root / "tests/model_outputs.jsonl").unlink()
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(1, completed.returncode)
        self.assertIn("ERROR", completed.stderr)


if __name__ == "__main__":
    unittest.main()
