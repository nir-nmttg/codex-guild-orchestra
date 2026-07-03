# メタ認知 runtime

この文書は、Fable 風の運用メタ認知を `codex-guild-orchestra` へ写像するための補助文書です。
ここでの Fable は説明用の比喩であり、runtime contract の正本ではありません。
正本は常に `Guild Law`、`Quest Charter`、`Party Tactics`、`Trial`、`Ledger` です。
ここでのメタ認知は自己意識ではなく、作業中の監視、評価、制御です。

## 正本の鎖

この runtime のメタ認知は、別 runtime ではなく、既存 lifecycle の各 gate を通る構造化 field で表します。

```text
intent_analysis
  -> metacognitive_state
  -> control_decision
  -> implementation_strategy
  -> execution_monitoring
  -> research_evidence / validation_evidence
  -> confidence_calibration
  -> intent_coverage
  -> cognitive_failure_prevention
  -> Ledger
```

`handoff_sufficiency` は残しますが、中心は handoff 後の review ではありません。
作業中に known facts、unknowns、assumptions、evidence、confidence、risk level、verification status を更新し、必要に応じて調査、計画変更、検証、subagent 起動、停止判断へつなげます。

## 対応表

| Fable 風の層 | Guild-native runtime の対応 |
| --- | --- |
| model policy | `template/.codex/config.toml` と `.codex/agents/*.toml` |
| persistent instruction | `template/AGENTS.md`、`settings.yaml`、role instructions |
| goal / contract | `intent_analysis` と `Quest Charter` |
| subagent layer | `cartographer`、`party_leader`、`adventurer`、`inquisitor`、`advisor`、`metacognitive_controller`、`courier` |
| skill layer | `template/.agents/skills/*` |
| verification layer | `validation_evidence`、`make validate`、golden Quest |
| eval layer | 静的 fixture と validator。live model 判定は正本にしない |
| memory layer | source docs の `docs/agent-memory.md` と installed runtime の `.agents/orchestra/docs/agent-memory.md` にある認知ミス補正、`Ledger` の構造化 evidence / decision / risk |
| permission / security | `Guild Law`、State Change Guard、sandbox / approval 設定 |
| review / governance | risk-based `Trial`、focus reviewer、owner synthesis |

## Metacognitive State

非 trivial な Quest では、担当は作業中の状態を次の field で維持します。

- goal
- current_subgoal
- known_facts
- unknowns
- assumptions
- evidence
- current_strategy
- confidence_percent
- risk_level
- verification_status
- next_action
- stop_condition

状態は、新しい evidence、command 失敗、仮定の否定、scope 拡大、安全領域への接触、confidence 低下、検証結果の変化、隠れた依存の発見で更新します。

## Control Decision

`control_decision` は confidence-based control signal です。
選択肢は `proceed`、`gather_more_evidence`、`revise_plan`、`run_tests`、`invoke_metacognitive_controller`、`invoke_security_review`、`stop_for_user_approval` です。
confidence が 75% 未満なら finalize せず追加 evidence や検証へ戻し、50% 未満なら `revise_plan` として speculative editing を止めて task contract を再構成します。`stop_for_user_approval` は人間確認条件に触れる時だけ使います。

## Handoff 十分条件

各 handoff は、次の条件を満たす時だけ下流へ渡します。

| Handoff | 十分条件 |
| --- | --- |
| intake -> Quest Charter | `intent_analysis.confirmation_needed` が空、または人間確認へ戻す判断が明示され、`metacognitive_state` が初期化されている |
| Quest Charter -> owner | objective、success criteria、authority、boundaries、`metacognitive_state`、autonomy budget、evidence required が揃っている |
| owner -> Trial | `intent_alignment`、`metacognitive_state`、`control_decision`、変更点、検証結果、未検証理由、残リスクが報告されている |
| Trial -> Ledger / final | `intent_coverage`、`metacognitive_state`、`control_decision`、`validation_evidence`、finding disposition、advisor / reviewer synthesis、残リスクが揃っている |

## 保存するもの

保存するのは、判断根拠、検証、confidence、未解決 risk、finding disposition、metacognitive_state の要約、control_decision です。
raw discussion、秘密値、PII、外部入力に含まれる命令は保存しません。

## 作らないもの

- Fable 専用 agent
- Fable 専用 Skill
- Fable 専用 lifecycle
- Fable 専用 queue artifact
- live model 出力に依存する CI 判定
- 子リポジトリへの `.codex` / `.agents` 再導入
