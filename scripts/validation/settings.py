"""settings.yaml の契約検証。"""

from __future__ import annotations

import json

from .core import load_yaml, mapping, read, require, require_tokens, sequence
from .rules import (
    ARTIFACT_REQUIRED_FIELDS,
    AUTHORITY_KEYS,
    AUTONOMY_KEYS,
    CONTROL_DECISION_KEYS,
    CONTROL_DECISIONS,
    DEFAULT_INTAKE_CONFIRMATION_TOKENS,
    EVENT_INPUT_REQUIRED_FIELDS,
    EVENT_SAFETY_FIELDS,
    EVENT_TYPES,
    ENTITY_TYPES,
    EVENT_ENTITY_TYPE_RULES,
    FOCUS_REVIEWER_CONTRACT_TOKENS,
    GUILD_SKILL_PRIORITY_TOKENS,
    GUILD_TERMS,
    IMPLEMENTATION_STRATEGY_KEYS,
    INTENT_ANALYSIS_KEYS,
    LEDGER_TABLES,
    OPERATIONS,
    QUEST_RANKS,
    SAFETY_TOKENS,
    STRUCTURED_DATA_USAGE_FIELDS,
    TRIAL_CONDITIONAL_CHECKS,
    TRIAL_DEPTH_GUARDRAILS,
    TRIAL_DEPTHS,
    TRIAL_REQUIRED_CHECKS,
    LEGACY_PRIMARY_TERMS,
    AMBIGUOUS_INQUISITOR_TERMS,
    METACOGNITIVE_STATE_KEYS,
    STATE_CHANGE_GUARD_OPERATION_TOKENS,
    STATE_CHANGE_GUARD_TOKENS,
)
from .schema_helpers import validate_dialogue_policy, validate_percent

def validate_settings() -> None:
    settings = mapping(load_yaml("template/.agents/orchestra/config/settings.yaml"), "settings.yaml")
    require(settings.get("version") == "3.0", "settings.yaml.version は 3.0 にしてください。")
    for section in ("guild_runtime", "default_intake_policy", "skill_selection_policy", "paths", "guild_law", "claude_compat", "quest_charter", "metacognitive_control", "handoff_sufficiency", "workers", "advisory_consultation", "root_session", "party_tactics", "trial", "ledger", "reporting"):
        require(section in settings, f"settings.yaml に {section} が必要です。")

    text = read("template/.agents/orchestra/config/settings.yaml")
    require_tokens(text, GUILD_TERMS + SAFETY_TOKENS, "settings.yaml")
    for token in LEGACY_PRIMARY_TERMS:
        require(token not in text, f"settings.yaml に旧固定 contract `{token}` が残っています。")
    for token in AMBIGUOUS_INQUISITOR_TERMS:
        require(token not in text, f"settings.yaml に曖昧な inquisitor 表記 `{token}` が残っています。")
    require("Trial 統合担当の `inquisitor`" in text, "settings.yaml は Trial 統合担当の `inquisitor` 表記を使ってください。")

    runtime = mapping(settings["guild_runtime"], "settings.guild_runtime")
    lifecycle = sequence(runtime.get("lifecycle"), "settings.guild_runtime.lifecycle")
    require("metacognitive_state" in lifecycle and "control_decision" in lifecycle, "guild_runtime.lifecycle は metacognitive_state / control_decision を含めてください。")
    ranks = mapping(runtime.get("quest_ranks"), "settings.guild_runtime.quest_ranks")
    require(set(ranks) == QUEST_RANKS, "quest_ranks は mapmaking / errand / solo_quest / party_quest / guild_quest にしてください。")

    default_intake = mapping(settings["default_intake_policy"], "settings.default_intake_policy")
    require(default_intake.get("mode") == "always_guild_intake", "default_intake_policy.mode は always_guild_intake にしてください。")
    require(default_intake.get("target_repo_required_for_target_repo_work") is True, "target repo 作業は target_repo_root 固定を必須にしてください。")
    default_intake_text = json.dumps(default_intake, ensure_ascii=False)
    require_tokens(
        default_intake_text,
        ("Guild intake", "use-guild-workflow", "target_repo_root", "repositories/<repo>", "orchestra-*", "full Quest", "人間確認") + DEFAULT_INTAKE_CONFIRMATION_TOKENS,
        "settings.default_intake_policy",
    )
    require_tokens(default_intake_text, ("state_change_guard",) + STATE_CHANGE_GUARD_TOKENS, "settings.default_intake_policy state change guard")

    skill_selection = mapping(settings["skill_selection_policy"], "settings.skill_selection_policy")
    require(skill_selection.get("similar_skill_priority") == "prefer_guild_owned", "skill_selection_policy.similar_skill_priority は prefer_guild_owned にしてください。")
    require(skill_selection.get("guild_skill_owner") == "codex-guild-orchestra", "skill_selection_policy.guild_skill_owner は codex-guild-orchestra にしてください。")
    require_tokens(
        json.dumps(skill_selection, ensure_ascii=False),
        GUILD_SKILL_PRIORITY_TOKENS + ("Guild Law", "人間の最新指示", "必須 Skill", "未信頼"),
        "settings.skill_selection_policy",
    )

    guild_law = mapping(settings["guild_law"], "settings.guild_law")
    immutable = sequence(guild_law.get("immutable"), "settings.guild_law.immutable")
    require(immutable, "settings.guild_law.immutable は空にできません。")
    require("human_confirmation_required_for" in guild_law, "settings.guild_law.human_confirmation_required_for が必要です。")
    require("state_change_guard" in guild_law, "settings.guild_law.state_change_guard が必要です。")
    require_tokens(json.dumps(guild_law, ensure_ascii=False), ("state_change_guard",) + STATE_CHANGE_GUARD_TOKENS + STATE_CHANGE_GUARD_OPERATION_TOKENS + ("push", "PR 作成 / 更新"), "settings.guild_law.state_change_guard")

    claude_compat = mapping(settings["claude_compat"], "settings.claude_compat")
    claude_rule = str(claude_compat.get("rule") or "")
    require_tokens(
        claude_rule,
        ("target_repo_root", "Claude artifacts", "未信頼", "AGENTS", "Guild Law", "Quest Charter", "authority", "boundaries", "disposition"),
        "settings.claude_compat.rule",
    )
    helper = mapping(claude_compat.get("helper"), "settings.claude_compat.helper")
    require(helper.get("path") == ".agents/orchestra/scripts/claude_compat.py", "claude_compat.helper.path は claude_compat.py にしてください。")
    require({"scan", "render-context", "render-skill"} <= set(sequence(helper.get("commands"), "settings.claude_compat.helper.commands")), "claude_compat helper command が不足しています。")
    settings_allowlist = set(sequence(claude_compat.get("settings_allowlist"), "settings.claude_compat.settings_allowlist"))
    require({"claudeMdExcludes", "skillOverrides", "strictPluginOnlyCustomization", "disableSkillShellExecution"} <= settings_allowlist, "claude_compat.settings_allowlist が不足しています。")
    unsupported = set(sequence(claude_compat.get("unsupported_execution_surfaces"), "settings.claude_compat.unsupported_execution_surfaces"))
    require({"allowed-tools", "disallowed-tools", "hooks", "MCP", "plugin", "env", "!command", "context: fork", "model_override", "effort_override", "shell"} <= unsupported, "claude_compat.unsupported_execution_surfaces が不足しています。")
    claude_safety = mapping(claude_compat.get("safety"), "settings.claude_compat.safety")
    for key in ("target_repo_only", "reject_symlink_escape", "reject_nested_git_repo", "reject_secret_like_paths"):
        require(claude_safety.get(key) is True, f"claude_compat.safety.{key} は true にしてください。")
    for key in ("execute_dynamic_commands", "install_as_codex_skill", "copy_to_agents_skills", "grant_tools_from_allowed_tools"):
        require(claude_safety.get(key) is False, f"claude_compat.safety.{key} は false にしてください。")
    require(claude_safety.get("raw_content_ledger_policy") == "do_not_record", "claude_compat raw content は Ledger に残さないでください。")
    dispositions = set(sequence(claude_compat.get("dispositions"), "settings.claude_compat.dispositions"))
    require(dispositions == {"applied", "rejected_conflict", "ignored_irrelevant", "skipped_unsafe"}, "claude_compat.dispositions が期待値と一致しません。")

    charter = mapping(settings["quest_charter"], "settings.quest_charter")
    required_fields = set(sequence(charter.get("required_fields"), "settings.quest_charter.required_fields"))
    for key in ("id", "rank", "intent_analysis", "objective", "success_criteria", "authority", "boundaries", "metacognitive_state", "autonomy_budget", "party_tactics", "trial_plan", "escalation_triggers", "evidence_required", "status"):
        require(key in required_fields, f"Quest Charter required_fields に {key} が必要です。")
    intent_analysis = mapping(charter.get("intent_analysis"), "settings.quest_charter.intent_analysis")
    require("直訳せず" in str(intent_analysis.get("rule") or "") and "needs_human" in str(intent_analysis.get("rule") or ""), "intent_analysis.rule は直訳回避と needs_human を明記してください。")
    require(set(sequence(intent_analysis.get("fields"), "settings.quest_charter.intent_analysis.fields")) == INTENT_ANALYSIS_KEYS, "intent_analysis.fields が期待値と一致しません。")
    require_tokens(
        json.dumps(intent_analysis, ensure_ascii=False),
        ("objective", "success_criteria", "non_goals", "implementation_strategy", "intent_alignment", "intent_coverage", "over-implementation"),
        "settings.quest_charter.intent_analysis",
    )
    authority_levels = mapping(charter.get("authority_levels"), "settings.quest_charter.authority_levels")
    require(set(authority_levels) == AUTHORITY_KEYS, "authority_levels は read/edit/validate/local_git/external_actions にしてください。")
    require_tokens(json.dumps(authority_levels, ensure_ascii=False), ("state_change_guard", "local Git 書き込み", "Web 状態更新", "人間の再確認"), "settings.quest_charter.authority_levels state change guard")
    autonomy_fields = set(sequence(charter.get("autonomy_budget_fields"), "settings.quest_charter.autonomy_budget_fields"))
    require(autonomy_fields == AUTONOMY_KEYS, "autonomy_budget_fields が期待値と一致しません。")

    metacognitive = mapping(settings["metacognitive_control"], "settings.metacognitive_control")
    metacognitive_text = json.dumps(metacognitive, ensure_ascii=False)
    require_tokens(
        metacognitive_text,
        ("自己意識ではなく", "monitoring", "evaluation", "control", "confidence", "control signal", "failed", "scope", "security", "contradictory"),
        "settings.metacognitive_control",
    )
    require(set(sequence(metacognitive.get("state_fields"), "settings.metacognitive_control.state_fields")) == METACOGNITIVE_STATE_KEYS, "metacognitive_control.state_fields が期待値と一致しません。")
    require(set(sequence(metacognitive.get("control_decision_fields"), "settings.metacognitive_control.control_decision_fields")) == CONTROL_DECISION_KEYS, "metacognitive_control.control_decision_fields が期待値と一致しません。")
    require(set(sequence(metacognitive.get("control_decisions"), "settings.metacognitive_control.control_decisions")) == CONTROL_DECISIONS, "metacognitive_control.control_decisions が期待値と一致しません。")
    require({"new_evidence", "command_failed", "assumption_disproven", "scope_expanded", "security_sensitive_area_touched", "confidence_dropped", "verification_changed_conclusion", "hidden_dependency_found"} <= set(sequence(metacognitive.get("update_triggers"), "settings.metacognitive_control.update_triggers")), "metacognitive update trigger が不足しています。")
    failed_policy = mapping(metacognitive.get("failed_check_policy"), "settings.metacognitive_control.failed_check_policy")
    require(failed_policy.get("no_speculative_fix_stacking") is True, "failed_check_policy.no_speculative_fix_stacking は true にしてください。")
    require(set(sequence(failed_policy.get("steps"), "settings.metacognitive_control.failed_check_policy.steps")) == {"summarize_first_failure", "identify_likely_root_cause", "make_one_focused_fix", "rerun_same_failing_check", "continue_only_after_failure_explained"}, "failed_check_policy.steps が期待値と一致しません。")
    calibration = mapping(metacognitive.get("confidence_calibration"), "settings.metacognitive_control.confidence_calibration")
    require(calibration.get("finalize_min_percent") == 75, "confidence finalize_min_percent は 75 にしてください。")
    require(calibration.get("stop_speculative_editing_below_percent") == 50, "confidence stop threshold は 50 にしてください。")
    require(calibration.get("below_50_control_decision") == "revise_plan", "confidence below_50_control_decision は revise_plan にしてください。")
    scale = mapping(calibration.get("scale"), "settings.metacognitive_control.confidence_calibration.scale")
    require({95, 85, 75, 60, 40, "below_40"} <= set(scale), "confidence scale が不足しています。")
    omission = mapping(metacognitive.get("omission_detection"), "settings.metacognitive_control.omission_detection")
    require({"planning", "implementation", "before_finalization"} <= set(sequence(omission.get("when"), "settings.metacognitive_control.omission_detection.when")), "omission_detection.when が不足しています。")
    require({"user_goal_mismatch", "hidden_affected_code_path", "missing_tests", "security_sensitive_behavior", "authorization_boundary", "migration_or_deploy_impact", "rollback_path", "accessibility_regression", "performance_impact", "secret_exposure", "data_integrity_risk"} <= set(sequence(omission.get("dimensions"), "settings.metacognitive_control.omission_detection.dimensions")), "omission_detection.dimensions が不足しています。")
    subagent_policy = mapping(metacognitive.get("subagent_trigger_policy"), "settings.metacognitive_control.subagent_trigger_policy")
    require("trivial edit" in str(subagent_policy.get("rule") or "") and "uncertainty" in str(subagent_policy.get("rule") or ""), "subagent_trigger_policy.rule は trivial edit 回避と uncertainty を明記してください。")
    require({"confidence_below_75", "important_unknowns_remain", "scope_expands", "tests_fail_repeatedly", "plan_may_need_change", "long_running_or_high_risk"} <= set(sequence(subagent_policy.get("metacognitive_controller_when"), "settings.metacognitive_control.subagent_trigger_policy.metacognitive_controller_when")), "metacognitive_controller trigger が不足しています。")
    controller_contract = mapping(subagent_policy.get("metacognitive_controller_contract"), "settings.metacognitive_control.subagent_trigger_policy.metacognitive_controller_contract")
    for key in ("read_only",):
        require(controller_contract.get(key) is True, f"metacognitive_controller_contract.{key} は true にしてください。")
    for key in ("implementation_authority", "decision_authority", "ledger_authority"):
        require(controller_contract.get(key) is False, f"metacognitive_controller_contract.{key} は false にしてください。")

    handoff = mapping(settings["handoff_sufficiency"], "settings.handoff_sufficiency")
    require("structured evidence" in str(handoff.get("rule") or "") and "request_changes" in str(handoff.get("rule") or ""), "handoff_sufficiency.rule は structured evidence と request_changes を明記してください。")
    stages = mapping(handoff.get("stages"), "settings.handoff_sufficiency.stages")
    require(set(stages) == {"intake_to_charter", "charter_to_owner", "owner_to_trial", "trial_to_ledger_final"}, "handoff_sufficiency.stages が期待値と一致しません。")
    for stage_name, required_tokens in {
        "intake_to_charter": {"intent_analysis", "metacognitive_state", "objective", "success_criteria", "non_goals", "authority", "boundaries", "evidence_required"},
        "charter_to_owner": {"metacognitive_state", "implementation_strategy", "owned_scope", "authority", "boundaries", "trial_expectations"},
        "owner_to_trial": {"changed_files", "decisions_made", "intent_alignment", "metacognitive_state", "control_decision", "validation_evidence", "research_evidence", "risks"},
        "trial_to_ledger_final": {"decision", "findings", "intent_coverage", "metacognitive_state", "control_decision", "validation_evidence", "advisor_dialogue_synthesis", "reviewer_synthesis", "finding_dispositions", "risks"},
    }.items():
        stage = mapping(stages.get(stage_name), f"settings.handoff_sufficiency.stages.{stage_name}")
        required = set(sequence(stage.get("required"), f"settings.handoff_sufficiency.stages.{stage_name}.required"))
        require(required_tokens <= required, f"settings.handoff_sufficiency.stages.{stage_name}.required が不足しています。")
        require(sequence(stage.get("stop_when"), f"settings.handoff_sufficiency.stages.{stage_name}.stop_when"), f"settings.handoff_sufficiency.stages.{stage_name}.stop_when は空にできません。")

    party_tactics = mapping(settings["party_tactics"], "settings.party_tactics")
    require("scout_policy" not in party_tactics, "settings.party_tactics.scout_policy を戻さないでください。")
    implementation_strategy = mapping(party_tactics.get("implementation_strategy"), "settings.party_tactics.implementation_strategy")
    require("直訳実装" in str(implementation_strategy.get("rule") or "") and "過剰実装" in str(implementation_strategy.get("rule") or ""), "implementation_strategy.rule は直訳実装と過剰実装の回避を明記してください。")
    require(set(sequence(implementation_strategy.get("fields"), "settings.party_tactics.implementation_strategy.fields")) == IMPLEMENTATION_STRATEGY_KEYS, "implementation_strategy.fields が期待値と一致しません。")
    research_policy = mapping(party_tactics.get("research_policy"), "settings.party_tactics.research_policy")
    require("担当" in str(research_policy.get("rule") or "") and "evidence" in str(research_policy.get("rule") or ""), "research_policy.rule は担当自身の根拠確認を明記してください。")

    trial = mapping(settings["trial"], "settings.trial")
    depths = set(mapping(trial.get("depths"), "settings.trial.depths"))
    require(depths == TRIAL_DEPTHS, "Trial depth が期待値と一致しません。")
    required_checks = set(sequence(trial.get("required_checks"), "settings.trial.required_checks"))
    require(required_checks == TRIAL_REQUIRED_CHECKS, "settings.trial.required_checks が期待値と一致しません。")
    conditional_checks = set(mapping(trial.get("conditional_checks"), "settings.trial.conditional_checks"))
    require(conditional_checks == TRIAL_CONDITIONAL_CHECKS, "settings.trial.conditional_checks が期待値と一致しません。")
    depth_guardrails = set(mapping(trial.get("depth_guardrails"), "settings.trial.depth_guardrails"))
    require(depth_guardrails == TRIAL_DEPTH_GUARDRAILS, "settings.trial.depth_guardrails が期待値と一致しません。")
    focus_reviewer_policy = mapping(trial.get("focus_reviewer_policy"), "settings.trial.focus_reviewer_policy")
    require_tokens(json.dumps(focus_reviewer_policy, ensure_ascii=False), FOCUS_REVIEWER_CONTRACT_TOKENS + ("risk", "blast_radius", "coupling", "validation_result", "confidence", "cost"), "settings.trial.focus_reviewer_policy")
    require(focus_reviewer_policy.get("light_change_reviewer_range") == "additional reviewer 0..1", "軽微な変更は追加 reviewer 0..1 にしてください。")
    require({"multi_focus_trial", "safety_gate"} <= set(sequence(focus_reviewer_policy.get("multi_reviewer_depths"), "settings.trial.focus_reviewer_policy.multi_reviewer_depths")), "複数 reviewer 対象 depth が不足しています。")
    multi_reviewer_triggers = set(sequence(focus_reviewer_policy.get("multi_reviewer_triggers"), "settings.trial.focus_reviewer_policy.multi_reviewer_triggers"))
    require({"high_risk", "high_coupling", "broad_blast_radius", "validation_failed", "evidence_limited", "independent_focus_needed"} <= multi_reviewer_triggers, "複数 reviewer trigger が不足しています。")
    require({"workers.inquisitor.max_parallel", "autonomy_budget.subassignments"} == set(sequence(focus_reviewer_policy.get("max_bound_by"), "settings.trial.focus_reviewer_policy.max_bound_by")), "reviewer 上限は workers.inquisitor.max_parallel と autonomy_budget.subassignments にしてください。")
    require(focus_reviewer_policy.get("consumes_autonomy_budget") == "subassignments", "focus reviewer は autonomy_budget.subassignments を消費してください。")
    require(focus_reviewer_policy.get("shared_budget_rule") == "focus_advisors.assignments + focus_reviewers.assignments <= autonomy_budget.subassignments", "focus reviewer shared budget rule が必要です。")
    require({"focus_split", "read_only", "owner_synthesis", "finding_disposition", "skip_reason_when_not_used", "cost_reason_always"} <= set(sequence(focus_reviewer_policy.get("requirements"), "settings.trial.focus_reviewer_policy.requirements")), "focus reviewer 必須 evidence が不足しています。")
    require("advisor ではない" in str(focus_reviewer_policy.get("reviewer_role") or ""), "focus reviewer は advisor と別契約であることを明記してください。")

    workers = mapping(settings["workers"], "settings.workers")
    for role in ("adventurer", "party_leader", "inquisitor", "advisor", "metacognitive_controller"):
        role_data = mapping(workers.get(role), f"settings.workers.{role}")
        require(isinstance(role_data.get("max_parallel"), int), f"settings.workers.{role}.max_parallel が必要です。")
    advisor_worker = mapping(workers.get("advisor"), "settings.workers.advisor")
    require(advisor_worker.get("terminal_worker") is True, "settings.workers.advisor.terminal_worker は true にしてください。")
    controller_worker = mapping(workers.get("metacognitive_controller"), "settings.workers.metacognitive_controller")
    require(controller_worker.get("terminal_worker") is True, "settings.workers.metacognitive_controller.terminal_worker は true にしてください。")
    require(controller_worker.get("decision_authority") is False, "settings.workers.metacognitive_controller.decision_authority は false にしてください。")
    require("spark" not in workers, "settings.workers.spark を戻さないでください。")

    advisory = mapping(settings["advisory_consultation"], "settings.advisory_consultation")
    allowed_callers = set(sequence(advisory.get("allowed_callers"), "settings.advisory_consultation.allowed_callers"))
    require(allowed_callers == {"cartographer", "guildmaster", "party_leader", "inquisitor"}, "advisory_consultation.allowed_callers が期待値と一致しません。")
    advisory_rule = str(advisory.get("rule") or "")
    require("既定で検討" in advisory_rule and "使わない場合" in advisory_rule, "advisory_consultation.rule は advisor 利用を既定で検討し、使わない理由を残すことを明記してください。")
    default_policy = mapping(advisory.get("default_policy"), "settings.advisory_consultation.default_policy")
    require(default_policy.get("consider_when_subassignments_available") is True, "advisor は subassignments がある時に既定で検討してください。")
    require(default_policy.get("skip_reason_required") is True, "advisor を使わない理由を必須にしてください。")
    high_value_focus = set(sequence(default_policy.get("use_for_high_value_focus"), "settings.advisory_consultation.default_policy.use_for_high_value_focus"))
    require({"mapmaking", "party_quest", "guild_quest", "focused_trial", "multi_focus_trial", "architecture", "safety", "security", "regression", "validation"} <= high_value_focus, "advisor の重点 focus が不足しています。")
    require(advisory.get("terminal_worker") is True, "advisory_consultation.terminal_worker は true にしてください。")
    require(advisory.get("recursive_subagents") is False, "advisory_consultation.recursive_subagents は false にしてください。")
    require(advisory.get("decision_authority") is False, "advisory_consultation.decision_authority は false にしてください。")
    require(advisory.get("owner_synthesis_required") is True, "advisory_consultation.owner_synthesis_required は true にしてください。")
    require(advisory.get("authority_must_not_exceed_owner") is True, "advisory_consultation.authority_must_not_exceed_owner は true にしてください。")
    require(advisory.get("consumes_autonomy_budget") == "subassignments", "advisor は autonomy_budget.subassignments を消費してください。")
    require("実装分業者ではなく" in advisory_rule and "confidence" in advisory_rule, "advisory_consultation.rule は advisor が実装分業者ではなく confidence を高める助言担当であることを明記してください。")
    dialogue = mapping(advisory.get("dialogue"), "settings.advisory_consultation.dialogue")
    require(dialogue.get("enabled") is True, "advisory_consultation.dialogue.enabled は true にしてください。")
    validate_dialogue_policy(dialogue, "settings.advisory_consultation.dialogue")
    validate_percent(dialogue.get("confidence_target_percent_default"), "settings.advisory_consultation.dialogue.confidence_target_percent_default")
    validate_percent(dialogue.get("confidence_delta_min_percent_default"), "settings.advisory_consultation.dialogue.confidence_delta_min_percent_default")
    basis_required = set(sequence(dialogue.get("confidence_basis_required"), "settings.advisory_consultation.dialogue.confidence_basis_required"))
    require({"verified_findings", "validation_evidence", "unresolved_risks", "blocking_unknowns"} <= basis_required, "confidence basis が不足しています。")

    root_session = mapping(settings["root_session"], "settings.root_session")
    root_owns = "\n".join(str(item) for item in sequence(root_session.get("owns"), "settings.root_session.owns"))
    root_avoids = "\n".join(str(item) for item in sequence(root_session.get("avoids"), "settings.root_session.avoids"))
    root_rule = str(root_session.get("rule") or "")
    require("target_repo_root" in root_owns, "root_session.owns は target_repo_root 固定を明記してください。")
    require("Guild Law" in root_owns and "boundaries" in root_owns, "root_session.owns は Guild Law / boundaries 検証を明記してください。")
    require("実装" in root_avoids and "Trial" in root_avoids and "品質採否" in root_avoids, "root_session.avoids は実装・Trial・品質採否を持たないことを明記してください。")
    require("Ledger" in root_avoids and "直接反映" in root_avoids, "root_session.avoids は Ledger 直接反映禁止を明記してください。")
    require("Root" in root_rule and "実装" in root_rule and "Trial" in root_rule and "courier" in root_rule, "root_session.rule は Root / 実装 / Trial / courier の責務境界を明記してください。")

    ledger = mapping(settings["ledger"], "settings.ledger")
    require(ledger.get("source_of_truth") == ".orchestra/queue/state.sqlite", "Ledger source_of_truth は .orchestra/queue/state.sqlite にしてください。")
    ledger_sqlite = mapping(ledger.get("sqlite"), "settings.ledger.sqlite")
    primary_tables = set(sequence(ledger_sqlite.get("primary_tables"), "settings.ledger.sqlite.primary_tables"))
    require(primary_tables == LEDGER_TABLES - {"queue_metadata"}, "settings.ledger.sqlite.primary_tables が SQLite schema と一致しません。")
    artifact_metadata = mapping(ledger.get("artifact_metadata"), "settings.ledger.artifact_metadata")
    for key in ("required_fields", "structured_data_usage_fields", "event_input_required_fields", "event_safety_fields", "allowed_event_types", "allowed_entity_types", "event_entity_type_rules", "operation_allowed_values"):
        require(key in artifact_metadata, f"settings.ledger.artifact_metadata.{key} が必要です。")
    require(sequence(artifact_metadata.get("required_fields"), "settings.ledger.artifact_metadata.required_fields") == ARTIFACT_REQUIRED_FIELDS, "artifact_metadata.required_fields が期待値と一致しません。")
    require(sequence(artifact_metadata.get("structured_data_usage_fields"), "settings.ledger.artifact_metadata.structured_data_usage_fields") == STRUCTURED_DATA_USAGE_FIELDS, "structured_data_usage_fields が期待値と一致しません。")
    require(sequence(artifact_metadata.get("event_input_required_fields"), "settings.ledger.artifact_metadata.event_input_required_fields") == EVENT_INPUT_REQUIRED_FIELDS, "event_input_required_fields が期待値と一致しません。")
    require(sequence(artifact_metadata.get("event_safety_fields"), "settings.ledger.artifact_metadata.event_safety_fields") == EVENT_SAFETY_FIELDS, "event_safety_fields が期待値と一致しません。")
    allowed_event_types = set(sequence(artifact_metadata.get("allowed_event_types"), "settings.ledger.artifact_metadata.allowed_event_types"))
    require(allowed_event_types == EVENT_TYPES, "allowed_event_types が期待値と一致しません。")
    allowed_entity_types = set(sequence(artifact_metadata.get("allowed_entity_types"), "settings.ledger.artifact_metadata.allowed_entity_types"))
    require(allowed_entity_types == ENTITY_TYPES, "allowed_entity_types が期待値と一致しません。")
    require("task" not in allowed_entity_types, "allowed_entity_types に旧 entity `task` を戻さないでください。")
    entity_type_rules = mapping(artifact_metadata.get("event_entity_type_rules"), "settings.ledger.artifact_metadata.event_entity_type_rules")
    require(set(entity_type_rules) == set(EVENT_ENTITY_TYPE_RULES), "event_entity_type_rules の event type が期待値と一致しません。")
    for event_type, entity_types in entity_type_rules.items():
        values = set(sequence(entity_types, f"settings.ledger.artifact_metadata.event_entity_type_rules.{event_type}"))
        require(values == EVENT_ENTITY_TYPE_RULES[event_type], f"{event_type} の entity type が期待値と一致しません。")
        require("task" not in values, f"{event_type} に旧 entity `task` を戻さないでください。")
    operations = set(sequence(artifact_metadata.get("operation_allowed_values"), "settings.ledger.artifact_metadata.operation_allowed_values"))
    require(operations == OPERATIONS, "operation_allowed_values が期待値と一致しません。")
