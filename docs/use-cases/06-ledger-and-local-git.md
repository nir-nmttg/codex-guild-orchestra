# Ledger と Git 操作を明示する

作業記録、commit、PR 説明準備などを、実装担当から分けて扱うパターンです。
Guild workflow では、Ledger 反映と明示された local Git 操作は `courier` の担当です。

## 使う場面

- 実装後に判断根拠、検証、残リスクを Ledger に残したい
- 未コミット差分を意味のある単位に分けたい
- PR 説明文を branch 差分から作りたい
- 溜まっている commit を秘密情報検査後に GitHub へ push したい
- 実装担当と記録担当を分けたい

## 依頼文例

```text
実装が完了したら、Ledger に残す evidence を整理し、次の local Git 操作だけを courier に割り当ててください。
target_repo_root は /path/to/guild-root/repositories/example-app です。

snapshot:
- revision_id: <Trial が accept した HEAD commit SHA>
- kind: working_tree_content
- scope_paths: src/import/csv_parser.py と tests/test_csv_import.py だけ。untracked file は含めない
- diff_hash: <`working_tree_content` として Trial が accept した上記 path 内容の `cgo-snapshot-v1` SHA-256。stage 状態は含めない>
- dirty_state: 上記以外の既存変更は保持し、stage しない

許可する操作:
- Ledger に判断根拠、権限、検証、残リスクを短く残す
- `src/import/csv_parser.py` と `tests/test_csv_import.py` だけを stage する
- staged diff が上記 diff_hash と一致した場合だけ `fix: ignore blank CSV rows` で commit する
- PR 説明文の draft を作る

禁止すること:
- 無関係な差分を stage する
- git reset --hard などの破壊的操作
- secret、raw log、PII を Ledger に残す
- remote push や PR 作成を勝手に行う
```

## 期待される流れ

1. 実装担当が変更点、検証、残リスク、`revision_id` / `diff_hash` を report にまとめます。
2. `inquisitor` が同じ snapshot に対して Trial を行い、完了判断に必要な evidence と finding disposition を補います。
3. Root が Trial -> Ledger / final handoff を確認し、Ledger 記録と local Git 操作を別々の courier action として具体化します。
4. `courier` が snapshot を再確認し、Ledger 用の短い記録を作ります。raw diff、raw log、秘密値、PII は記録しません。
5. 最新の人間指示に具体的な操作名、対象 path / branch / range、commit message がある場合だけ、`courier` が対象差分を確認して stage / commit します。path や hunk を文脈から補いません。
6. stage 後に、staged path が許可 scope と一致することを別に確認し、同じ path の `working_tree_content` digest を再計算します。digest は stage 状態を含めないため、内容が変わらない stage 前後では同じ値です。不一致や無関係な staged path があれば commit せず停止します。
7. commit 後は commit SHA を新しい `revision_id` として固定し、残る change set の `diff_hash`、`git status`、staged / unstaged / untracked 変更、実行しなかった操作、Ledger event disposition を返します。
8. Ledger、stage、commit の途中で一部だけ成功した場合は、自動 rollback や別経路の再試行をせず、成功済み action と失敗理由を記録します。Root が新しい snapshot と狭い再 assignment を作ります。
9. remote push、PR 作成、破壊的操作は別途人間確認を挟みます。
10. GitHub へ push する場合は、`github-safe-push-from-branch` の Push Safety Gate で秘密情報、PII、内部情報、公開禁止情報を弾き、push target、branch / range、公開内容、残リスクを提示して実行直前に人間確認を得ます。

## 完了条件

- Ledger に残す内容が raw log ではなく判断根拠になっている
- commit 単位が作業意図ごとに分かれている
- 無関係なユーザー変更を巻き込んでいない
- GitHub push では Push Safety Gate の結果と残リスクが明示されている
- remote や外部状態を勝手に変更していない
- commit SHA、最終 `git status`、残差分、Ledger / Git action ごとの disposition がある
- Trial が accept した snapshot と stage / commit 対象が一致している
- commit 後の新しい `revision_id` / `diff_hash` が final report に渡されている

## 注意点

Git 操作は便利ですが、Guild workflow では authority を広げる操作です。
「commit して」「PR 説明を作って」などの明示がない限り、実装完了だけで local git や remote 操作へ進みません。
`必要なら`、`PR ready`、`仕上げて` は具体的な local Git 指示ではなく、対象 path / range のない stage / commit は実行しません。
