# Guild Quest Lifecycle

この文書は Guild-native runtime の早見表です。
現在の runtime は、`Guild Law`、`Quest Charter`、`Party Tactics`、`Trial`、`Ledger` を中心に動きます。

## Lifecycle

```text
Human Request
  -> intent_analysis
  -> quest_awareness
  -> control_decision
  -> Quest Charter
  -> Party Tactics
  -> Execution
  -> Trial
  -> Ledger
  -> Final Report
```

## Rank

| Quest Rank | 使う場面 | 主担当 |
| --- | --- | --- |
| `mapmaking` | 計画、設計、調査、方針整理 | `cartographer` |
| `errand` | 明白な軽作業 | `adventurer` または軽量な割り当て（assignment）。Ledger / local Git の明示操作のみ `courier` |
| `solo_quest` | 単独自律遂行 | `adventurer` |
| `party_quest` | 分担や独立 Trial が有効 | `party_leader` |
| `guild_quest` | 戦略、広い影響、安全判断 | `guildmaster` |

## Roles

- `receptionist`: Quest Charter を作る
- `cartographer`: 地図、危険地帯、`implementation_strategy` 候補、推奨 rank を返す
- `guildmaster`: `guild_quest` 戦略と Party 境界を決める
- `party_leader`: `intent_analysis` から `implementation_strategy`、Party Tactics、Trial depth を設計する
- `adventurer`: authority 内で自律的に調査、実装、検証し、`intent_alignment` を残す
- `inquisitor`: risk-based Trial の lead / integrator として、`intent_coverage`、reviewer evidence、重大度、finding disposition、最終 decision を統合する
- `focus_reviewer`: `inquisitor` から割り当てられた単一 focus だけを確認し、bounded read-only evidence を返す terminal worker（終端担当）
- `advisor`: focus 限定の read-only 助言を返す terminal worker（終端助言担当）
- `quest_sentinel`: 作業中の confidence、unknowns、assumptions、verification status を監視し、次アクションを推薦する read-only 制御監視担当
- `courier`: Ledger 反映と明示された local Git 操作を扱う

## Quest Awareness

非 trivial な Quest では、担当は `quest_awareness` と `control_decision` を更新します。
confidence は evidence に基づく control signal であり、75% 未満では finalize せず、50% 未満では speculative editing を止めます。
unknown が correctness を塞ぐ時は調査へ戻り、failed check は first failure を説明して同じ check を再実行します。
scope drift、安全領域、矛盾 evidence は plan revision または needs_human の trigger です。

## Trial

Trial は固定人数ではなく、risk と confidence で決めます。
全 handoff は `cgo-snapshot-v1` の `subject_snapshot` に結び付けます。並列実装は共通base、各owned-scope result、integration barrier後のintegrated snapshotを分け、別scopeの変更だけで先行reportをstaleにしません。read-only dialogueは同じsnapshotを再利用し、mutation / HEAD / scope / dirty-state signalの変更時だけ再計算します。
すべての Trial では、`intent_analysis.confirmation_needed` が未解消のまま実装されていないかを確認し、残る場合は `needs_human` または `request_changes` にします。

- `none`
- `self_check`
- `peer_review`
- `focused_trial`
- `multi_focus_trial`
- `safety_gate`

`self_check` は owner validation attestation であり、Root のaccept判断ではありません。errand / low-risk soloの厳格なeligibility gateをすべて満たす場合だけindependent Trialを省略し、それ以外は`inquisitor`の`peer_review`以上へ上げます。

`mapmaking`、`party_quest`、`guild_quest`、`focused_trial` / `multi_focus_trial`、architecture / safety / security / regression / validation などの high-value focus では、`autonomy_budget.subassignments` が残り focus が境界内に収まる場合、owner は read-only `advisor` の利用を既定で検討します。
advisor report は採否ではなく材料であり、最終 decision と重大度分類は Trial 統合担当の `inquisitor` が行います。使わない場合も owner は理由を synthesis に残します。
advisor は実装分業者ではなく、考慮漏れや未確認リスクを見つけて成果物の confidence を高めるために使います。
confidence-based dialogue は、新しい evidence、blocking unknown の解消、confidence delta がある間だけ続け、進捗が止まった時は target confidence 未満でも停止して未解決理由を残します。

Party Tactics は必要な Trial focus を提案でき、Trial lead / integrator の `inquisitor` が risk、focus、blast radius、coupling、validation result、confidence、cost から追加 read-only `focus_reviewer` 数と assignment を最終決定します。
軽微な変更は追加 read-only focus reviewer 0..1 を標準にし、`multi_focus_trial`、`safety_gate`、高 risk、高 coupling、検証失敗、evidence 不足では複数 reviewer を選べます。
上限は `workers.focus_reviewer.max_parallel` と `autonomy_budget.subassignments` の小さい方です。
focus reviewer は `autonomy_budget.subassignments` を消費し、`focus_advisors.assignments + focus_reviewers.assignments <= autonomy_budget.subassignments` を守ります。
複数 reviewer を使う時は focus 分割、read-only、owner synthesis、finding disposition を残します。skip reason は reviewer を使わない時に必須、cost reason は reviewer 数判断で常に必須です。
`focus_reviewer` は Trial 内の単一 focus だけを確認する独立した terminal worker で、`advisor` とは別契約です。採否、重大度分類、requested changes、最終 owner synthesis、追加 subagent 起動を行わず、Trial lead の `inquisitor` が reports を根拠確認して統合します。

## Safety

どの Rank でも `target_repo_root` 境界、秘密情報、PII、人間確認条件は Guild Law として固定です。
