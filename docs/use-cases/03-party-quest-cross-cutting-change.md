# 横断変更を分業する

複数領域にまたがる変更を、担当範囲と Trial focus を分けて進めるパターンです。
設計、実装、検証、レビューを同じ担当に寄せすぎないために使います。

## 使う場面

- backend、frontend、docs、tests など複数領域にまたがる
- 既存契約を壊さないか独立確認したい
- 仕様は決まっているが、実装箇所が複数ある
- regression、security、validation など別 focus の Trial が有効

## 依頼文例

```text
この変更は party_quest として扱ってください。
target_repo_root は /path/to/guild-root/repositories/example-app です。

目的:
- ユーザー設定の通知チャネルを email / slack / none から選べるようにする

成功条件:
- 設定画面で通知チャネルを保存できる
- backend validation と frontend 表示が一致する
- 既存ユーザーの初期値が明確
- 関連 docs とテストが更新される

party_tactics:
- 実装担当は既存設計を読んで最小差分で進める
- assignment ごとに assignment_id、owned scope、編集禁止 path、validation expectation を持たせる
- party_leader が、adventurer を integration owner とする専用 assignment と integration barrier を設計する
- Trial は validation、UI 回帰、既存データ影響を focus にする
- 必要なら read-only advisor を 1 focus だけ使う

snapshot:
- revision_id: <Root が確認した HEAD commit SHA>
- kind: revision_only
- scope_paths: 全 assignment の owned scope の和集合
- dirty_state: 既存のユーザー変更を assignment scope から除外し、区別できない場合は停止

停止条件:
- migration が必要
- 外部サービス送信の実動作確認が必要
- 認可や課金に影響する
```

## 期待される流れ

1. Root が Quest Charter と共通の `base_snapshot` を作ります。clean な開始点は `revision_only` とし、全 worker が同じ `revision_id` を参照します。
2. `party_leader` が担当範囲、assignment identity、並列化可否、sequencing、Trial focus、integration barrier を設計します。同じファイルだけでなく、生成物、lockfile、schema、共有契約、共通 test fixture の owner も一つに固定します。
3. `party_leader` は cross-scope の調整だけを行う `integration_owner` の adventurer assignment を明示します。`party_leader` 自身は実装を引き取りません。
4. 各 `adventurer` が共通 base revision と自分の owned scope を確認し、scope 内で実装します。report には assignment ID、変更、`intent_alignment`、`quest_awareness`、`control_decision`、validation evidence、残リスク、base snapshot、owned scope だけの `result_snapshot` を含めます。別 worker の scope 変更はこの result を stale にしません。
5. 全実装 report が揃うまで integration barrier を閉じません。base revision 不一致、owned scope 重複、同じ owned scope の後発変更、失敗、未完了 assignment が一つでもあれば Trial へ進みません。
6. Root と `party_leader` が handoff を確認した後、並列編集を停止し、`integration_owner` だけが cross-scope glue、共有契約、統合検証を担当します。新しい実装が不要なら、その理由を残します。
7. integration owner の report 後に全 owned scope と glue を含む `working_tree_content` の integrated snapshot を固定し、以後 Trial 完了まで実装担当は編集しません。変更が生じた場合は barrier を開き直し、新しい integrated snapshot を作ります。
8. `inquisitor` が stable snapshot に対して risk-based に `focused_trial` または `multi_focus_trial` を行います。
9. advisor と `focus_reviewer` は `autonomy_budget.subassignments` を共有します。Trial lead の `inquisitor` が reviewer 数と単一 focus の assignment を最終決定し、独立した `focus_reviewer` reports を根拠確認して採用、却下、未解決の disposition を統合します。
10. Findings は重大度と disposition を付けて統合され、accept 後に `courier` が snapshot、検証、残リスクを Ledger に記録します。

## 完了条件

- 担当ごとの owned scope が明確
- 同じファイルを複数担当が同時に編集していない
- 共有 artifact と cross-scope glue の owner が一つに決まり、integration barrier 後に stable snapshot が固定されている
- Trial focus と検証結果が成功条件に対応している
- Critical / Major の不足が残っていない
- assignment report は共通 base snapshot と各 owned-scope result snapshot、integration report / Trial / Ledger は同じ最終 integrated snapshot を参照している

## 注意点

`party_quest` は人数を増やすこと自体が目的ではありません。
risk、coupling、blast radius、validation result、confidence、cost を見て、必要な分だけ担当と reviewer を置きます。
並列数を増やしても integration barrier と stable snapshot を省略せず、Trial 中に source state を動かしません。
