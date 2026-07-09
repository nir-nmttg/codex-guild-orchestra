# Quest Sentinel で制御判断を補助する

Quest 実行中に confidence が低下した、重要な unknown が残った、scope drift や検証失敗が起きた時に、read-only の `quest_sentinel` から次アクションの推薦だけを得るパターンです。
`quest_sentinel` は decision owner ではなく、実装、採否、Ledger、Git 操作を行わない terminal worker です。

## 使う場面

- confidence が 75% 未満で finalize できない
- confidence が 50% 未満で speculative editing を止める必要がある
- failed check の first failure と focused next action を整理したい
- scope drift、contradictory evidence、security-sensitive trigger がある

## 依頼文例

```text
この assignment の control signal を quest_sentinel に確認させてください。
target_repo_root は /path/to/guild-root/repositories/example-app です。

trigger:
- 関連テスト失敗後に別の修正案が複数出ている

渡すもの:
- Quest Charter と assignment ID
- current plan、既知の evidence、最初の failure、実行済み検証、risk
- 現在の quest_awareness と control_decision
- `subject_snapshot`（既存 owner snapshot を参照し、同じ dialogue では再利用）

やらないこと:
- 実装、ファイル編集、採否、Ledger / Git 操作、外部送信
- 追加 subagent 起動
```

## 期待される流れ

1. owner が作業を止め、現在の `subject_snapshot`、task、plan、evidence、diff、test result、risk を固定します。既存 snapshot を参照し、global change set を dialogue ごとに再 hash しません。
2. Root または owner が authority と boundaries 内の read-only assignment として `quest_sentinel` を起動します。
3. `quest_sentinel` は開始時に snapshot を確認し、known facts、unknowns、assumptions、evidence、current strategy、confidence、risk、verification status を `quest_awareness` に整理します。
4. 出力は `quest_awareness` と `control_decision` だけに限定し、`decision`、`rationale`、`required_next_action`、`triggers`、`confidence_threshold_applied`、`escalation_required` を返します。
5. failed check では first failure、likely root cause、一つの focused next action、同じ check の再実行を推薦します。複数の speculative fix を積みません。
6. owner が推薦の evidence を自分で確認し、`adopted / rejected / unresolved / stale_evidence` の disposition と owner confidence を synthesis に残します。sentinel の confidence や推薦を採否として転記しません。
7. `invoke_security_review` が推薦された場合は、Root が既存 authority 内で `inquisitor` の `safety_gate` へ接続します。`stop_for_user_approval` は人間確認条件に触れる場合だけ使います。
8. 同じ focus の follow-up は、新しい evidence または blocking unknown の減少が見込める時だけ行います。snapshot 変更、新しい根拠なし、scope 拡大、人間確認が必要な場合は停止します。
9. owner は採用した control decision に従って plan、assignment、検証を更新します。Ledger には raw discussion ではなく owner synthesis と最終 snapshot だけを渡します。

## 完了条件

- 推薦が固定 snapshot と検証 evidence に結び付いている
- sentinel と owner の decision authority が分離されている
- confidence threshold、first failure、scope drift、安全 trigger の適用根拠がある
- owner が推薦を根拠確認し disposition を残している
- source state が変わった場合に古い control decision を流用していない

## 注意点

`quest_sentinel` は confidence の数値を付けるためではなく、次アクションを evidence に基づいて絞るために使います。
推薦が誤っている可能性を前提に、owner が採否と実行責任を保持します。
