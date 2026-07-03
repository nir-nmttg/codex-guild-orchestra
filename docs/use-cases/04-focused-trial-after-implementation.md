# 実装済みブランチを確認する

実装後に、意図充足、責務分割、保守性、検証、回帰リスクを確認するパターンです。
自分で作った差分の最終確認や、PR 前の品質確認に向いています。

## 使う場面

- 実装は終わったが、見落としを確認したい
- PR 前にリスクの高い箇所だけ深く見たい
- 仕様と差分がずれていないか確認したい
- reviewer に見るべき focus を明示したい

## 依頼文例

```text
現在のブランチ差分を focused_trial として確認してください。
target_repo_root は /path/to/guild-root/repositories/example-app です。

focus:
- `intent_analysis` の本質的な成果を満たし、`intent_alignment` が根拠付きか
- `quest_awareness` と `control_decision` が owner -> Trial の handoff に足りているか
- 責務分割が既存設計に合っているか
- テスト不足や回帰リスクがないか
- 過度な共通化や重複がないか
- `confirmation_needed` が未解消のまま実装されていないか
- focus reviewer を使う場合は cost reason と finding disposition を残すこと

やってよいこと:
- read-only review
- 必要な検証コマンドの提案

やらないこと:
- ファイル編集
- commit
- PR 作成
```

## 期待される流れ

1. Root が read-only の Trial として境界を固定します。
2. `inquisitor` が差分、関連コード、テスト観点を確認します。
3. `intent_coverage` として推定意図、本質的な成果、non-goals、過剰実装回避を確認します。
4. `quest_awareness`、`control_decision`、`validation_evidence` が Trial -> Ledger / final に足りるか確認します。
5. 必要に応じて focus reviewer を追加し、使う場合は focus 分割、cost reason、finding disposition を残します。
6. findings を Critical / Major / Minor などの重要度で整理します。
6. 追加 Quest が必要か、完了扱いでよいかを判断します。

## 完了条件

- 重大な破綻や未検証リスクが明示されている
- `intent_coverage` が `intent_analysis`、`non_goals`、過剰実装回避まで見ている
- `quest_awareness`、`control_decision`、`validation_evidence` の不足が分類されている
- focus reviewer を使った場合は cost reason と finding disposition がある
- 指摘ごとに根拠ファイルや判断理由がある
- 修正が必要な場合は、次の最小 Quest に分けられる
- 問題がなければ、残る risk と test gap が説明されている

## 注意点

Trial は採点ではなく、完了判断のための evidence を増やす工程です。
read-only review の依頼では、勝手に修正や git 操作へ進みません。
