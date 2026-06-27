# Ledger と Git 操作を明示する

作業記録、commit、PR 説明準備などを、実装担当から分けて扱うパターンです。
Guild workflow では、Ledger 反映と明示された local Git 操作は `courier` の担当です。

## 使う場面

- 実装後に判断根拠、検証、残リスクを Ledger に残したい
- 未コミット差分を意味のある単位に分けたい
- PR 説明文を branch 差分から作りたい
- 実装担当と記録担当を分けたい

## 依頼文例

```text
実装が完了したら、Ledger に残す evidence を整理し、必要なら local git 操作を courier に分けてください。
target_repo_root は /path/to/guild-root/repositories/example-app です。

許可すること:
- Ledger に判断根拠、権限、検証、残リスクを短く残す
- 明示した範囲だけ stage / commit する
- PR 説明文の draft を作る

禁止すること:
- 無関係な差分を stage する
- git reset --hard などの破壊的操作
- secret、raw log、PII を Ledger に残す
- remote push や PR 作成を勝手に行う
```

## 期待される流れ

1. 実装担当が変更点、検証、残リスクを report にまとめます。
2. Trial が完了判断に必要な evidence を補います。
3. `courier` が Ledger 用の短い記録を作ります。
4. Git 操作が明示されている場合だけ、対象差分を確認して stage / commit します。
5. remote push、PR 作成、破壊的操作は別途人間確認を挟みます。

## 完了条件

- Ledger に残す内容が raw log ではなく判断根拠になっている
- commit 単位が作業意図ごとに分かれている
- 無関係なユーザー変更を巻き込んでいない
- remote や外部状態を勝手に変更していない

## 注意点

Git 操作は便利ですが、Guild workflow では authority を広げる操作です。
「commit して」「PR 説明を作って」などの明示がない限り、実装完了だけで local git や remote 操作へ進みません。

