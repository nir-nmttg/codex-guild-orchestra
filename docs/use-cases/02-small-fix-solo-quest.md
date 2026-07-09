# 小さな修正を自律実装する

目的と成功条件が明確な修正を、単独担当が調査、実装、検証まで進めるパターンです。
軽い不具合修正、docs 修正、テスト追加、限定的な UI 調整に向いています。

## 使う場面

- 再現条件や期待挙動が明確な不具合
- docs、コメント、リンク、表記ゆれの整理
- 既存方針に沿った小さなテスト追加
- 変更範囲が一つの機能や小さなファイル群に閉じる作業

## 依頼文例

```text
この不具合を solo_quest として修正してください。
target_repo_root は /path/to/guild-root/repositories/example-app です。

目的:
- CSV import で空行があると失敗する問題を修正する

成功条件:
- 空行を無視して import が完了する
- 既存の valid / invalid 行の扱いは変えない
- 関連テストが通る

intent_analysis:
- inferred_intent: CSV import の利用者が不要な空行で処理全体を失敗させず、既存の行検証ルールは維持したい
- essential_outcomes:
  - 空行だけを無害に無視する
  - valid / invalid 行の既存仕様を変えない
- confirmation_needed: []

authority:
- read: 対象 repo 内
- edit: import 処理、関連テスト、必要な docs のみ
- validate: 既存の関連テスト

snapshot:
- revision_id: <Root が確認した HEAD commit SHA>
- kind: revision_only
- scope_paths: import 処理、関連テスト、明示した untracked test file
- dirty_state: 既存のユーザー変更は除外し、区別できない場合は停止

停止条件:
- 仕様判断が必要
- 公開 API 互換性に影響する
- 依存追加や migration が必要
```

## 期待される流れ

1. Root が Quest Charter を作り、目的、成功条件、authority、boundaries と開始時の `base_snapshot` を固定します。
2. `adventurer` が snapshot の一致と既存のユーザー変更を確認してから、対象範囲を読みます。
3. `adventurer` が `implementation_strategy` に沿って、空行だけを扱う最小十分な差分を選びます。
4. 変更に見合う検証を実行し、self-check は Trial decision ではなく owner の validation evidence として残します。
5. `adventurer` が変更点、`intent_alignment`、`quest_awareness`、`control_decision`、`validation_evidence`、未検証範囲、残リスク、owned scope の `working_tree_content` result snapshot を report にまとめます。
6. Root が owner -> Trial handoff と `self_check` eligibility gate を機械的に確認します。`errand` または low-risk `solo_quest`、単一 owned scope、低 uncertainty / coupling、限定 blast radius、safety / confirmation / public API・data compatibility change / scope drift / blocking unknown なし、targeted validation 成功、成功条件の直接 evidence、snapshot 一致をすべて満たす場合だけ independent Trial を省略できます。owner は validation attestation と skip reason を残しますが、`accept`、重大度、requested changes は決めず、Root も品質判断を補いません。
7. 独立確認が必要なrisk、曖昧なintent coverage、検証不足、scope driftがある場合だけ、Rootが`inquisitor`へ`peer_review`以上を割り当てます。`inquisitor`は`intent_coverage`、成功条件、回帰リスク、decision、finding dispositionを返します。
8. self-check eligibility と owner attestation、または`inquisitor`のaccept後に、`courier`がTrial -> Ledger handoffの要約だけを記録し、Rootがfinal reportを集約します。local Git操作は人間が具体的に指示した別assignmentがない限り行いません。

## 完了条件

- 成功条件を満たす差分がある
- `intent_analysis` の本質的な成果を満たし、過剰実装を避けた根拠がある
- `quest_awareness` と `control_decision` が owner から Trial へ渡せる形で整理されている
- 変更理由が既存設計と矛盾しない
- 実行した検証と未検証範囲が明示されている
- 人間確認が必要な操作を勝手に進めていない
- owner report、Trial、Ledger が同じ base / result snapshot を参照している

## 注意点

小さな修正でも、影響範囲が広がった時は `party_quest` や `safety_gate` に切り替えます。
`solo_quest` は一人で抱え込むための指定ではなく、境界が小さい時に過剰な分業を避けるための rank です。
owner report 後に source state が変わった場合は、古い Trial を流用せず snapshot と検証を更新します。
