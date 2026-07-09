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

review scope:
- quest_charter_ref: <元 Quest Charter の ID>
- owner_report_ref: <実装担当 report の ID>
- base_ref: origin/main
- head_ref: <review 対象の commit SHA または branch head SHA>
- kind: commit_range
- revision_id: <Root が確認した HEAD commit SHA>
- dirty_state: staged / unstaged / untracked を review に含めない。存在する場合は停止
- scope_paths: <review対象 path。全差分なら repository root 相当の明示 scope>
- diff_hash: <`commit_range` の `cgo-snapshot-v1` SHA-256>

focus:
- `intent_analysis` の本質的な成果を満たし、`intent_alignment` が根拠付きか
- `evidence_state`のblocker、failed check、scope driftがhandoffに足りているか
- 責務分割が既存設計に合っているか
- テスト不足や回帰リスクがないか
- 過度な共通化や重複がないか
- `confirmation_needed` が未解消のまま実装されていないか
- 複数focus reviewerを使う場合はfocus分割とfinding dispositionを残すこと

やってよいこと:
- read-only review
- 必要な検証コマンドの提案

やらないこと:
- ファイル編集
- commit
- PR 作成
```

## 期待される流れ

1. Root が元 Quest Charter と owner report を取得し、read-only の Trial authority、`base_ref`、`head_ref`、dirty state policy、共通 snapshot 契約を固定します。元の intent や report がない場合は、推測で補わず evidence-limited とします。
2. Root と `inquisitor` が `base_ref` / `head_ref` の存在、`revision_id`、`diff_hash`、staged / unstaged / untracked の状態を確認します。許可されていない dirty state や hash mismatch があれば `stale_evidence` として停止します。
3. `inquisitor` が固定済みの差分、関連コード、owner report、テスト観点を確認します。
4. `intent_coverage` として推定意図、本質的な成果、non-goals、過剰実装回避を確認します。
5. `evidence_state`と`validation_evidence`がownerからTrialへ足りるか確認します。
6. 必要に応じて`inquisitor`が単一focusをRootへ提案し、Rootが`focus_reviewer`を直接起動します。`inquisitor`はreportsを根拠確認して統合し、使わない場合の定型説明は不要です。
7. findings を Critical / Major / Minor などの重要度で整理します。
8. 追加 Quest が必要か、完了扱いでよいかを判断します。Trial 中に source state が変わった場合は判断を破棄し、新しい snapshot で Trial をやり直します。

## 完了条件

- 重大な破綻や未検証リスクが明示されている
- `intent_coverage` が `intent_analysis`、`non_goals`、過剰実装回避まで見ている
- `evidence_state`と`validation_evidence`の不足が分類されている
- 複数focus reviewerを使った場合はfocus分割とfinding dispositionがある
- 指摘ごとに根拠ファイルや判断理由がある
- 修正が必要な場合は、次の最小 Quest に分けられる
- 問題がなければ、残る risk と test gap が説明されている
- findings と decision が固定された `base_ref` / `head_ref`、`revision_id` / `diff_hash` に結び付いている

## 注意点

Trial は採点ではなく、完了判断のための evidence を増やす工程です。
read-only review の依頼では、勝手に修正や git 操作へ進みません。
「現在の差分」を推測せず、branch diff、index、worktree、untracked file のどれを対象にするかを明示します。
