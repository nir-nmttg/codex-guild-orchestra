"""queue artifact template の検証。"""

from __future__ import annotations

from .core import load_yaml, mapping, read, require, sequence
from .rules import (
    IMPLEMENTATION_STRATEGY_KEYS,
    INTENT_ALIGNMENT_KEYS,
    INTENT_ANALYSIS_KEYS,
    INTENT_COVERAGE_REPORT_KEYS,
    TRIAL_CONDITIONAL_CHECKS,
    TRIAL_DEPTH_GUARDRAILS,
    TRIAL_REQUIRED_CHECKS,
    VOCABULARY_DRIFT_TERMS,
)
from .schema_helpers import (
    validate_authority,
    validate_autonomy_budget,
    validate_boundaries,
    validate_compat_context,
    validate_dialogue_policy,
    validate_percent,
    validate_template_metadata,
)

def validate_queue_templates() -> None:
    paths = [
        "template/.agents/orchestra/queue/templates/advisor_assignment.yaml",
        "template/.agents/orchestra/queue/templates/advisor_report.yaml",
        "template/.agents/orchestra/queue/templates/adventurer_assignment.yaml",
        "template/.agents/orchestra/queue/templates/cartographer_assignment.yaml",
        "template/.agents/orchestra/queue/templates/cartographer_report.yaml",
        "template/.agents/orchestra/queue/templates/inquisitor_trial.yaml",
        "template/.agents/orchestra/queue/templates/adventurer_report.yaml",
        "template/.agents/orchestra/queue/templates/inquisitor_report.yaml",
        "template/.agents/orchestra/queue/templates/request.yaml",
        "template/.agents/orchestra/queue/templates/command.yaml",
        "template/.agents/orchestra/queue/templates/adventurer_inbox.yaml",
        "template/.agents/orchestra/queue/templates/role_inbox.yaml",
    ]
    for rel in paths:
        doc = mapping(load_yaml(rel), rel)
        validate_template_metadata(doc, rel)
        text = read(rel)
        for token in ("scale:", "risk_dimensions:", "quality_profile:", "spark_request:", "scout_plan:", "scout_usage:", "scout_calls:"):
            require(token not in text, f"{rel} に旧固定 contract `{token}` が残っています。")
        for token in ("enabled: true", "enabled: false", "advisors: [advisor]", "used: false"):
            require(token not in text, f"{rel} に旧 advisor field `{token}` が残っています。")
        for token in VOCABULARY_DRIFT_TERMS:
            require(token not in text, f"{rel} に表記揺れ `{token}` が残っています。")

    assignment = mapping(mapping(load_yaml("template/.agents/orchestra/queue/templates/adventurer_assignment.yaml"), "adventurer_assignment").get("assignment"), "adventurer_assignment.assignment")
    for key in ("id", "quest_id", "rank", "objective", "intent_analysis", "success_criteria", "implementation_strategy", "authority", "boundaries", "autonomy_budget", "research_plan", "validation_expectations", "trial_expectations", "escalation_triggers", "evidence_required", "status"):
        require(key in assignment, f"adventurer_assignment.assignment.{key} が必要です。")
    assignment_intent = mapping(assignment.get("intent_analysis"), "adventurer_assignment.assignment.intent_analysis")
    require(set(assignment_intent) == INTENT_ANALYSIS_KEYS, "adventurer_assignment.assignment.intent_analysis が期待値と一致しません。")
    assignment_strategy = mapping(assignment.get("implementation_strategy"), "adventurer_assignment.assignment.implementation_strategy")
    require(set(assignment_strategy) == IMPLEMENTATION_STRATEGY_KEYS, "adventurer_assignment.assignment.implementation_strategy が期待値と一致しません。")
    validate_authority(assignment["authority"], "adventurer_assignment.assignment.authority")
    validate_boundaries(assignment["boundaries"], "adventurer_assignment.assignment.boundaries")
    validate_autonomy_budget(assignment["autonomy_budget"], "adventurer_assignment.assignment.autonomy_budget")
    assignment_known_context = mapping(assignment.get("known_context"), "adventurer_assignment.assignment.known_context")
    validate_compat_context(assignment_known_context.get("compat_context"), "adventurer_assignment.assignment.known_context.compat_context")

    cartographer_assignment = mapping(mapping(load_yaml("template/.agents/orchestra/queue/templates/cartographer_assignment.yaml"), "cartographer_assignment").get("assignment"), "cartographer_assignment.assignment")
    for key in ("id", "quest_id", "worker_id", "role", "kind", "rank", "objective", "intent_analysis", "success_criteria", "non_goals", "focus", "authority", "boundaries", "known_context", "autonomy_budget", "research_plan", "advisor_consultation", "output_requirements", "escalation_triggers", "evidence_required", "status"):
        require(key in cartographer_assignment, f"cartographer_assignment.assignment.{key} が必要です。")
    cartographer_intent = mapping(cartographer_assignment.get("intent_analysis"), "cartographer_assignment.assignment.intent_analysis")
    require(set(cartographer_intent) == INTENT_ANALYSIS_KEYS, "cartographer_assignment.assignment.intent_analysis が期待値と一致しません。")
    require(cartographer_assignment["worker_id"] == "cartographer", "cartographer_assignment.assignment.worker_id は cartographer にしてください。")
    require(cartographer_assignment["kind"] == "mapmaking", "cartographer_assignment.assignment.kind は mapmaking にしてください。")
    require(cartographer_assignment["rank"] == "mapmaking", "cartographer_assignment.assignment.rank は mapmaking にしてください。")
    validate_authority(cartographer_assignment["authority"], "cartographer_assignment.assignment.authority")
    cartographer_authority = mapping(cartographer_assignment["authority"], "cartographer_assignment.assignment.authority")
    require(
        cartographer_authority.get("read") is True
        and cartographer_authority.get("edit") is False
        and cartographer_authority.get("validate") is False
        and cartographer_authority.get("local_git") is False
        and cartographer_authority.get("external_actions") is False,
        "cartographer assignment は read-only にしてください。",
    )
    validate_boundaries(cartographer_assignment["boundaries"], "cartographer_assignment.assignment.boundaries")
    validate_autonomy_budget(cartographer_assignment["autonomy_budget"], "cartographer_assignment.assignment.autonomy_budget")
    cartographer_known_context = mapping(cartographer_assignment.get("known_context"), "cartographer_assignment.assignment.known_context")
    validate_compat_context(cartographer_known_context.get("compat_context"), "cartographer_assignment.assignment.known_context.compat_context")
    cartographer_advisor = mapping(cartographer_assignment.get("advisor_consultation"), "cartographer_assignment.assignment.advisor_consultation")
    require(set(cartographer_advisor) == {"consideration_required", "assignments", "owner_synthesis_required", "terminal_worker_required", "skip_reason_required_when_not_used", "skip_reason"}, "cartographer advisor_consultation は検討必須と skip reason 契約だけにしてください。")
    require(cartographer_advisor.get("consideration_required") is True, "cartographer は advisor を既定で検討対象にしてください。")
    require(cartographer_advisor.get("owner_synthesis_required") is True, "cartographer advisor は owner synthesis を必須にしてください。")
    require(cartographer_advisor.get("terminal_worker_required") is True, "cartographer advisor は terminal worker を必須にしてください。")
    require(cartographer_advisor.get("skip_reason_required_when_not_used") is True, "cartographer advisor を使わない時は理由を必須にしてください。")

    advisor_assignment = mapping(mapping(load_yaml("template/.agents/orchestra/queue/templates/advisor_assignment.yaml"), "advisor_assignment").get("assignment"), "advisor_assignment.assignment")
    for key in ("id", "quest_id", "parent_id", "worker_id", "role", "kind", "owner_worker_id", "owner_assignment_id", "objective", "focus", "dialogue_policy", "decision_authority", "terminal_worker", "owner_synthesis_required", "authority", "boundaries", "autonomy_budget", "research_plan", "escalation_triggers", "evidence_required", "status"):
        require(key in advisor_assignment, f"advisor_assignment.assignment.{key} が必要です。")
    require(advisor_assignment["worker_id"] == "advisor", "advisor_assignment.assignment.worker_id は advisor にしてください。")
    require(advisor_assignment["decision_authority"] is False, "advisor_assignment.assignment.decision_authority は false にしてください。")
    require(advisor_assignment["terminal_worker"] is True, "advisor_assignment.assignment.terminal_worker は true にしてください。")
    require(advisor_assignment["owner_synthesis_required"] is True, "advisor_assignment.assignment.owner_synthesis_required は true にしてください。")
    dialogue_policy = mapping(advisor_assignment["dialogue_policy"], "advisor_assignment.assignment.dialogue_policy")
    validate_dialogue_policy(dialogue_policy, "advisor_assignment.assignment.dialogue_policy")
    for key in ("confidence_target_percent", "confidence_delta_min_percent"):
        validate_percent(dialogue_policy.get(key), f"advisor_assignment.assignment.dialogue_policy.{key}")
    validate_authority(advisor_assignment["authority"], "advisor_assignment.assignment.authority")
    advisor_authority = mapping(advisor_assignment["authority"], "advisor_assignment.assignment.authority")
    require(advisor_authority.get("read") is True and advisor_authority.get("edit") is False and advisor_authority.get("local_git") is False and advisor_authority.get("external_actions") is False, "advisor は read-only にしてください。")
    validate_boundaries(advisor_assignment["boundaries"], "advisor_assignment.assignment.boundaries")
    validate_autonomy_budget(advisor_assignment["autonomy_budget"], "advisor_assignment.assignment.autonomy_budget")
    advisor_known_context = mapping(advisor_assignment.get("known_context"), "advisor_assignment.assignment.known_context")
    validate_compat_context(advisor_known_context.get("compat_context"), "advisor_assignment.assignment.known_context.compat_context")

    trial = mapping(mapping(load_yaml("template/.agents/orchestra/queue/templates/inquisitor_trial.yaml"), "inquisitor_trial").get("trial"), "inquisitor_trial.trial")
    for key in ("id", "quest_id", "depth", "focus", "objective", "intent_analysis", "success_criteria", "authority", "boundaries", "trial_checks", "depth_guardrails", "autonomy_budget", "research_plan", "decision_options", "evidence_required", "status"):
        require(key in trial, f"inquisitor_trial.trial.{key} が必要です。")
    trial_intent = mapping(trial.get("intent_analysis"), "inquisitor_trial.trial.intent_analysis")
    require(set(trial_intent) == INTENT_ANALYSIS_KEYS, "inquisitor_trial.trial.intent_analysis が期待値と一致しません。")
    validate_authority(trial["authority"], "inquisitor_trial.trial.authority")
    validate_boundaries(trial["boundaries"], "inquisitor_trial.trial.boundaries")
    validate_autonomy_budget(trial["autonomy_budget"], "inquisitor_trial.trial.autonomy_budget")
    trial_checks = set(sequence(trial["trial_checks"], "inquisitor_trial.trial.trial_checks"))
    expected_trial_checks = TRIAL_REQUIRED_CHECKS | TRIAL_CONDITIONAL_CHECKS
    require(trial_checks == expected_trial_checks, "inquisitor_trial.trial.trial_checks が期待値と一致しません。")
    depth_guardrails = mapping(trial["depth_guardrails"], "inquisitor_trial.trial.depth_guardrails")
    require(set(depth_guardrails) == TRIAL_DEPTH_GUARDRAILS, "inquisitor_trial.trial.depth_guardrails が期待値と一致しません。")
    multi_focus_guardrail = mapping(depth_guardrails["multi_focus_trial"], "inquisitor_trial.trial.depth_guardrails.multi_focus_trial")
    require(multi_focus_guardrail.get("requires_focus_split") is True, "multi_focus_trial は focus 分割を必須にしてください。")
    require(multi_focus_guardrail.get("allows_focus_advisors") is True, "multi_focus_trial は focus advisor を許可してください。")
    require(multi_focus_guardrail.get("allows_focus_reviewers") is True, "multi_focus_trial は focus reviewer を許可してください。")
    require(multi_focus_guardrail.get("requires_owner_synthesis") is True, "multi_focus_trial は owner synthesis を必須にしてください。")
    require(multi_focus_guardrail.get("if_focus_is_insufficient") == "request_changes", "multi_focus_trial の focus 不足時は request_changes にしてください。")
    focus_advisors = mapping(trial.get("focus_advisors"), "inquisitor_trial.trial.focus_advisors")
    require(set(focus_advisors) == {"consideration_required", "assignments", "consumes_autonomy_budget", "shared_budget_rule", "owner_synthesis_required", "terminal_worker_required", "skip_reason_required_when_not_used", "skip_reason"}, "focus_advisors は検討必須と shared budget / skip reason 契約だけにしてください。")
    require(focus_advisors.get("consideration_required") is True, "inquisitor_trial は focus advisor を既定で検討対象にしてください。")
    require(focus_advisors.get("consumes_autonomy_budget") == "subassignments", "focus advisor は autonomy_budget.subassignments を消費してください。")
    require(focus_advisors.get("shared_budget_rule") == "focus_advisors.assignments + focus_reviewers.assignments <= autonomy_budget.subassignments", "focus advisor shared budget rule が必要です。")
    require(focus_advisors.get("owner_synthesis_required") is True, "focus advisor は owner synthesis を必須にしてください。")
    require(focus_advisors.get("terminal_worker_required") is True, "focus advisor は terminal worker を必須にしてください。")
    require(focus_advisors.get("skip_reason_required_when_not_used") is True, "focus advisor を使わない時は理由を必須にしてください。")
    require("skip_reason" in focus_advisors, "focus advisor を使わない理由欄が必要です。")
    focus_reviewers = mapping(trial.get("focus_reviewers"), "inquisitor_trial.trial.focus_reviewers")
    require(set(focus_reviewers) == {"count_decision_required", "reviewer_count", "max_reviewers_bound_by", "selection_inputs", "light_change_reviewer_range", "multi_reviewer_allowed_for", "assignments", "consumes_autonomy_budget", "shared_budget_rule", "focus_split_required_when_multiple", "read_only_required", "owner_synthesis_required", "finding_disposition_required", "skip_reason_required_when_not_used", "cost_reason_required", "cost_reason_required_always", "skip_reason", "cost_reason"}, "focus_reviewers は reviewer 数判断と shared budget / evidence 契約にしてください。")
    require(focus_reviewers.get("count_decision_required") is True, "focus reviewer 数の判断を必須にしてください。")
    require(focus_reviewers.get("reviewer_count") is None, "focus_reviewers.reviewer_count は draft で null にしてください。")
    require({"workers.inquisitor.max_parallel", "autonomy_budget.subassignments"} == set(sequence(focus_reviewers.get("max_reviewers_bound_by"), "inquisitor_trial.trial.focus_reviewers.max_reviewers_bound_by")), "focus reviewer 上限が不足しています。")
    require({"risk", "focus", "blast_radius", "coupling", "validation_result", "confidence", "cost"} <= set(sequence(focus_reviewers.get("selection_inputs"), "inquisitor_trial.trial.focus_reviewers.selection_inputs")), "focus reviewer selection_inputs が不足しています。")
    require(focus_reviewers.get("light_change_reviewer_range") == "additional reviewer 0..1", "軽微な変更は追加 reviewer 0..1 にしてください。")
    settings_focus_policy = mapping(mapping(load_yaml("template/.agents/orchestra/config/settings.yaml"), "settings.yaml").get("trial"), "settings.trial").get("focus_reviewer_policy")
    settings_focus_policy = mapping(settings_focus_policy, "settings.trial.focus_reviewer_policy")
    settings_triggers = set(sequence(settings_focus_policy.get("multi_reviewer_triggers"), "settings.trial.focus_reviewer_policy.multi_reviewer_triggers"))
    template_allowed = set(sequence(focus_reviewers.get("multi_reviewer_allowed_for"), "inquisitor_trial.trial.focus_reviewers.multi_reviewer_allowed_for"))
    template_triggers = template_allowed - {"multi_focus_trial", "safety_gate"}
    require(template_triggers == settings_triggers, "settings multi_reviewer_triggers と template multi_reviewer_allowed_for の trigger 部分を一致させてください。")
    require({"multi_focus_trial", "safety_gate"} <= template_allowed, "複数 focus reviewer depth 条件が不足しています。")
    require(focus_reviewers.get("consumes_autonomy_budget") == "subassignments", "focus reviewer は autonomy_budget.subassignments を消費してください。")
    require(focus_reviewers.get("shared_budget_rule") == "focus_advisors.assignments + focus_reviewers.assignments <= autonomy_budget.subassignments", "focus reviewer shared budget rule が必要です。")
    for key in ("focus_split_required_when_multiple", "read_only_required", "owner_synthesis_required", "finding_disposition_required", "skip_reason_required_when_not_used", "cost_reason_required", "cost_reason_required_always"):
        require(focus_reviewers.get(key) is True, f"inquisitor_trial.trial.focus_reviewers.{key} は true にしてください。")
    require("skip_reason" in focus_reviewers and "cost_reason" in focus_reviewers, "focus reviewer の skip/cost reason 欄が必要です。")
    trial_research_plan = mapping(trial.get("research_plan"), "inquisitor_trial.trial.research_plan")
    validate_compat_context(trial_research_plan.get("compat_context"), "inquisitor_trial.trial.research_plan.compat_context")
    trial_budget = mapping(trial["autonomy_budget"], "inquisitor_trial.trial.autonomy_budget")
    require(isinstance(trial_budget.get("subassignments"), int) and trial_budget.get("subassignments") >= 1, "inquisitor_trial は advisor 検討用の subassignments を 1 以上にしてください。")
    focus_advisor_assignments = sequence(focus_advisors.get("assignments"), "inquisitor_trial.trial.focus_advisors.assignments")
    focus_reviewer_assignments = sequence(focus_reviewers.get("assignments"), "inquisitor_trial.trial.focus_reviewers.assignments")
    require(len(focus_advisor_assignments) + len(focus_reviewer_assignments) <= trial_budget["subassignments"], "focus_advisors.assignments + focus_reviewers.assignments は autonomy_budget.subassignments 以下にしてください。")
    safety_gate_guardrail = mapping(depth_guardrails["safety_gate"], "inquisitor_trial.trial.depth_guardrails.safety_gate")
    require(safety_gate_guardrail.get("requires_human_or_safety_evidence") is True, "safety_gate は人間確認または安全確認 evidence を必須にしてください。")
    require(safety_gate_guardrail.get("if_evidence_is_missing") == "needs_human", "safety_gate の evidence 不足時は needs_human にしてください。")

    cartographer_report = mapping(mapping(load_yaml("template/.agents/orchestra/queue/templates/cartographer_report.yaml"), "cartographer_report").get("report"), "cartographer_report.report")
    for key in ("id", "quest_id", "assignment_id", "worker_id", "target_repo_root", "status", "summary", "objective", "intent_analysis", "success_criteria", "terrain_map", "recommended_implementation_strategy", "risk_zones", "recommended_quest_rank", "recommended_party_tactics", "recommended_trial", "advisor_usage", "advisor_synthesis", "unknowns", "research_evidence", "confidence", "risks", "evidence_refs"):
        require(key in cartographer_report, f"cartographer_report.report.{key} が必要です。")
    cartographer_report_intent = mapping(cartographer_report.get("intent_analysis"), "cartographer_report.report.intent_analysis")
    require(set(cartographer_report_intent) == INTENT_ANALYSIS_KEYS, "cartographer_report.report.intent_analysis が期待値と一致しません。")
    cartographer_strategy = mapping(cartographer_report.get("recommended_implementation_strategy"), "cartographer_report.report.recommended_implementation_strategy")
    require(set(cartographer_strategy) == IMPLEMENTATION_STRATEGY_KEYS, "cartographer_report.report.recommended_implementation_strategy が期待値と一致しません。")
    require(cartographer_report["worker_id"] == "cartographer", "cartographer_report.report.worker_id は cartographer にしてください。")
    terrain_map = mapping(cartographer_report["terrain_map"], "cartographer_report.report.terrain_map")
    require(set(terrain_map) == {"existing_structure", "relevant_paths", "dependencies", "candidate_routes"}, "cartographer_report.report.terrain_map が期待値と一致しません。")
    recommended_rank = mapping(cartographer_report["recommended_quest_rank"], "cartographer_report.report.recommended_quest_rank")
    require(recommended_rank.get("rank") == "mapmaking", "cartographer_report.report.recommended_quest_rank.rank は mapmaking にしてください。")
    cartographer_report_advisor = mapping(cartographer_report["advisor_usage"], "cartographer_report.report.advisor_usage")
    require(set(cartographer_report_advisor) == {"considered", "used", "skip_reason_required_when_not_used", "skip_reason"}, "cartographer_report.report.advisor_usage は検討結果と skip reason 契約だけにしてください。")
    require(cartographer_report_advisor.get("considered") is True, "cartographer_report.report.advisor_usage.considered は true にしてください。")
    require(cartographer_report_advisor.get("used") is None, "cartographer_report.report.advisor_usage.used は draft で採否を先取りしないでください。")
    require(cartographer_report_advisor.get("skip_reason_required_when_not_used") is True, "cartographer_report.report.advisor_usage.skip_reason_required_when_not_used は true にしてください。")
    cartographer_synthesis = mapping(cartographer_report["advisor_synthesis"], "cartographer_report.report.advisor_synthesis")
    require(cartographer_synthesis.get("raw_discussion_recorded") is False, "cartographer_report.report.advisor_synthesis.raw_discussion_recorded は false にしてください。")
    cartographer_research = mapping(cartographer_report.get("research_evidence"), "cartographer_report.report.research_evidence")
    validate_compat_context(cartographer_research.get("compat_context"), "cartographer_report.report.research_evidence.compat_context")

    for rel in ("template/.agents/orchestra/queue/templates/adventurer_report.yaml", "template/.agents/orchestra/queue/templates/inquisitor_report.yaml"):
        report = mapping(mapping(load_yaml(rel), rel).get("report"), f"{rel}.report")
        for key in ("id", "quest_id", "worker_id", "status", "summary", "validation_evidence", "research_evidence", "confidence", "risks", "evidence_refs"):
            require(key in report, f"{rel}.report.{key} が必要です。")
        if rel.endswith("adventurer_report.yaml"):
            intent_alignment = mapping(report.get("intent_alignment"), f"{rel}.report.intent_alignment")
            require(set(intent_alignment) == INTENT_ALIGNMENT_KEYS, f"{rel}.report.intent_alignment が期待値と一致しません。")
        report_research = mapping(report.get("research_evidence"), f"{rel}.report.research_evidence")
        validate_compat_context(report_research.get("compat_context"), f"{rel}.report.research_evidence.compat_context")
        if rel.endswith("inquisitor_report.yaml"):
            intent_coverage = mapping(report.get("intent_coverage"), f"{rel}.report.intent_coverage")
            require(set(intent_coverage) == INTENT_COVERAGE_REPORT_KEYS, f"{rel}.report.intent_coverage が期待値と一致しません。")
            advisor_usage = mapping(report.get("advisor_usage"), f"{rel}.report.advisor_usage")
            require(set(advisor_usage) == {"considered", "used", "skip_reason_required_when_not_used", "skip_reason"}, f"{rel}.report.advisor_usage は検討結果と skip reason 契約だけにしてください。")
            for key in ("considered", "used", "skip_reason_required_when_not_used", "skip_reason"):
                require(key in advisor_usage, f"{rel}.report.advisor_usage.{key} が必要です。")
            require(advisor_usage.get("considered") is True, f"{rel}.report.advisor_usage.considered は true にしてください。")
            require(advisor_usage.get("used") is None, f"{rel}.report.advisor_usage.used は draft で採否を先取りしないでください。")
            require(advisor_usage.get("skip_reason_required_when_not_used") is True, f"{rel}.report.advisor_usage.skip_reason_required_when_not_used は true にしてください。")
            reviewer_usage = mapping(report.get("reviewer_usage"), f"{rel}.report.reviewer_usage")
            require(set(reviewer_usage) == {"count_decision_required", "reviewer_count", "max_reviewers_bound_by", "selection_inputs", "light_change_reviewer_range", "multi_reviewer_used", "consumes_autonomy_budget", "shared_budget_rule", "focus_split", "read_only_confirmed", "owner_synthesis_required", "finding_disposition_required", "skip_reason_required_when_not_used", "cost_reason_required", "cost_reason_required_always", "skip_reason", "cost_reason"}, f"{rel}.report.reviewer_usage は reviewer 数判断と shared budget / evidence 契約にしてください。")
            require(reviewer_usage.get("count_decision_required") is True, f"{rel}.report.reviewer_usage.count_decision_required は true にしてください。")
            require(reviewer_usage.get("reviewer_count") is None, f"{rel}.report.reviewer_usage.reviewer_count は draft で null にしてください。")
            require({"workers.inquisitor.max_parallel", "autonomy_budget.subassignments"} == set(sequence(reviewer_usage.get("max_reviewers_bound_by"), f"{rel}.report.reviewer_usage.max_reviewers_bound_by")), f"{rel}.report.reviewer_usage.max_reviewers_bound_by が不足しています。")
            reviewer_inputs = mapping(reviewer_usage.get("selection_inputs"), f"{rel}.report.reviewer_usage.selection_inputs")
            require({"risk", "focus", "blast_radius", "coupling", "validation_result", "confidence", "cost"} <= set(reviewer_inputs), f"{rel}.report.reviewer_usage.selection_inputs が不足しています。")
            require(reviewer_usage.get("light_change_reviewer_range") == "additional reviewer 0..1", f"{rel}.report.reviewer_usage.light_change_reviewer_range は additional reviewer 0..1 にしてください。")
            require(reviewer_usage.get("consumes_autonomy_budget") == "subassignments", f"{rel}.report.reviewer_usage.consumes_autonomy_budget は subassignments にしてください。")
            require(reviewer_usage.get("shared_budget_rule") == "focus_advisors.assignments + focus_reviewers.assignments <= autonomy_budget.subassignments", f"{rel}.report.reviewer_usage.shared_budget_rule が必要です。")
            for key in ("read_only_confirmed", "owner_synthesis_required", "finding_disposition_required", "skip_reason_required_when_not_used", "cost_reason_required", "cost_reason_required_always"):
                require(reviewer_usage.get(key) is True, f"{rel}.report.reviewer_usage.{key} は true にしてください。")
            require("skip_reason" in reviewer_usage and "cost_reason" in reviewer_usage, f"{rel}.report.reviewer_usage に skip/cost reason 欄が必要です。")
            require("reviewer_reports" in report, f"{rel}.report.reviewer_reports が必要です。")
            finding_dispositions = mapping(report.get("finding_dispositions"), f"{rel}.report.finding_dispositions")
            require(set(finding_dispositions) == {"adopted", "rejected", "unresolved"}, f"{rel}.report.finding_dispositions は adopted/rejected/unresolved にしてください。")
            reviewer_synthesis = mapping(report.get("reviewer_synthesis"), f"{rel}.report.reviewer_synthesis")
            require(set(reviewer_synthesis) == {"owner_worker_id", "summary", "adopted_findings", "rejected_findings", "unresolved_findings", "decision_basis", "raw_discussion_recorded"}, f"{rel}.report.reviewer_synthesis が期待値と一致しません。")
            require(reviewer_synthesis.get("owner_worker_id") == "inquisitor", f"{rel}.report.reviewer_synthesis.owner_worker_id は inquisitor にしてください。")
            require(reviewer_synthesis.get("raw_discussion_recorded") is False, f"{rel}.report.reviewer_synthesis.raw_discussion_recorded は false にしてください。")
            dialogue_synthesis = mapping(report.get("advisor_dialogue_synthesis"), f"{rel}.report.advisor_dialogue_synthesis")
            require(dialogue_synthesis.get("raw_discussion_recorded") is False, f"{rel}.report.advisor_dialogue_synthesis.raw_discussion_recorded は false にしてください。")
            for key in ("confidence_target_percent", "owner_confidence_percent", "previous_confidence_percent", "confidence_delta_percent", "new_evidence_refs", "blocking_unknowns_resolved", "blocking_unknowns_remaining", "continue_or_stop", "stop_reason"):
                require(key in dialogue_synthesis, f"{rel}.report.advisor_dialogue_synthesis.{key} が必要です。")
    advisor_report = mapping(mapping(load_yaml("template/.agents/orchestra/queue/templates/advisor_report.yaml"), "advisor_report").get("report"), "advisor_report.report")
    for key in ("id", "quest_id", "assignment_id", "worker_id", "owner_worker_id", "status", "decision_authority", "terminal_worker", "owner_synthesis_required", "summary", "focus", "findings", "risks", "unknowns", "confidence_percent", "confidence_basis", "confidence_delta_percent", "new_evidence_refs", "blocking_unknowns_resolved", "blocking_unknowns_remaining", "recommended_next_focus", "research_evidence", "confidence", "evidence_refs"):
        require(key in advisor_report, f"advisor_report.report.{key} が必要です。")
    require(advisor_report["worker_id"] == "advisor", "advisor_report.report.worker_id は advisor にしてください。")
    require(advisor_report["decision_authority"] is False, "advisor_report.report.decision_authority は false にしてください。")
    require(advisor_report["terminal_worker"] is True, "advisor_report.report.terminal_worker は true にしてください。")
    require(advisor_report["owner_synthesis_required"] is True, "advisor_report.report.owner_synthesis_required は true にしてください。")
    confidence_basis = mapping(advisor_report["confidence_basis"], "advisor_report.report.confidence_basis")
    require(set(confidence_basis) == {"verified_findings", "validation_evidence", "unresolved_risks", "blocking_unknowns"}, "advisor_report.report.confidence_basis が期待値と一致しません。")
    advisor_research = mapping(advisor_report.get("research_evidence"), "advisor_report.report.research_evidence")
    validate_compat_context(advisor_research.get("compat_context"), "advisor_report.report.research_evidence.compat_context")
