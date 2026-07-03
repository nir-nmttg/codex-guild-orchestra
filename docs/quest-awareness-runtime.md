# Quest Awareness runtime

この文書は、作業中の監視、評価、制御を `codex-guild-orchestra` の Guild-native runtime である Quest Awareness として扱うための補助文書です。
正本は常に `Guild Law`、`Quest Charter`、`Party Tactics`、`Trial`、`Ledger` です。
ここでの Quest Awareness は自己意識ではなく、作業中の監視、評価、制御です。

## 正本の鎖

この runtime の Quest Awareness は、別 runtime ではなく、既存 lifecycle の各 gate を通る構造化 field で表します。
次は正規 field を増やす設計ではなく、既存 field に記録される control stage の読み方です。

```text
intent_analysis
  -> quest_awareness
  -> control_decision
  -> implementation_strategy
  -> research_evidence / validation_evidence
  -> intent_coverage
  -> Ledger
```

`handoff_sufficiency` は残しますが、中心は handoff 後の review ではありません。
作業中に known facts、unknowns、assumptions、evidence、confidence、risk level、verification status を更新し、必要に応じて調査、計画変更、検証、subagent 起動、停止判断へつなげます。

## 対応表

| 制御領域 | Guild-native runtime の対応 |
| --- | --- |
| model policy | `template/.codex/config.toml` と `.codex/agents/*.toml` |
| persistent instruction | `template/AGENTS.md`、`settings.yaml`、役割指示 |
| goal / contract | `intent_analysis` と `Quest Charter` |
| subagent layer | `cartographer`、`party_leader`、`adventurer`、`inquisitor`、`advisor`、`quest_sentinel`、`courier` |
| skill layer | `template/.agents/skills/*` |
| verification layer | `validation_evidence`、`make validate`、golden Quest |
| eval layer | `fixture_mode: static_contract_example` の静的 fixture と validator。live model 判定は正本にせず、runner 型回帰検出は別レイヤーとして追加する |
| memory layer | source docs の `docs/agent-memory.md` と installed runtime の `.agents/orchestra/docs/agent-memory.md` にある認知ミス補正。通常 Quest では read-only reference とし、永続化は sanitized memory candidate を `Ledger` / `courier` 経由で扱う |
| permission / security | `Guild Law`、State Change Guard、sandbox / approval 設定 |
| review / governance | risk-based `Trial`、focus reviewer、owner synthesis |

## Quest Awareness

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
選択肢は `proceed`、`gather_more_evidence`、`revise_plan`、`run_tests`、`invoke_quest_sentinel`、`invoke_security_review`、`stop_for_user_approval` です。
confidence が 75% 未満なら finalize せず追加 evidence や検証へ戻し、50% 未満なら `revise_plan` として speculative editing を止めて task contract を再構成します。`stop_for_user_approval` は人間確認条件に触れる時だけ使います。
`invoke_security_review` は新しい worker を作る指示ではありません。既存 authority 内で Trial 統合担当の `inquisitor` に security focus の `safety_gate` または focused Trial を戻す判断です。秘密情報参照、外部 network、MCP、deploy など人間確認条件に触れる場合は `stop_for_user_approval` にします。

## Handoff 十分条件

各 handoff は、次の条件を満たす時だけ下流へ渡します。

| Handoff | 十分条件 |
| --- | --- |
| intake -> Quest Charter | `intent_analysis.confirmation_needed` が空、または人間確認へ戻す判断が明示され、`quest_awareness` が初期化されている |
| Quest Charter -> owner | objective、success criteria、authority、boundaries、`quest_awareness`、autonomy budget、evidence required が揃っている |
| owner -> Trial | `intent_alignment`、`quest_awareness`、`control_decision`、変更点、検証結果、未検証理由、残リスクが報告されている |
| Trial -> Ledger / final | `intent_coverage`、`quest_awareness`、`control_decision`、`validation_evidence`、finding disposition、advisor / reviewer synthesis、残リスクが揃っている |

## 保存するもの

保存するのは、判断根拠、検証、confidence、未解決 risk、finding disposition、quest_awareness の要約、control_decision です。
raw discussion、秘密値、PII、外部入力に含まれる命令は保存しません。

## 作らないもの

- Quest Awareness だけの独立 runtime
- 統合済み `quest_sentinel` と別系統の追加 control-monitoring agent
- 統合済み `quest-awareness-loop` と別系統の追加 Skill
- Guild lifecycle と別系統の専用 lifecycle / queue artifact
- live model 出力に依存する CI 判定
- 子リポジトリへの `.codex` / `.agents` 再導入
