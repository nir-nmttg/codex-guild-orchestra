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
- Trial は validation、UI 回帰、既存データ影響を focus にする
- 必要なら read-only advisor を 1 focus だけ使う

停止条件:
- migration が必要
- 外部サービス送信の実動作確認が必要
- 認可や課金に影響する
```

## 期待される流れ

1. Root が Quest Charter を作ります。
2. `party_leader` が担当範囲、並列化可否、Trial focus を設計します。
3. `adventurer` が owned scope 内で実装します。
4. `inquisitor` が risk-based に `focused_trial` または `multi_focus_trial` を行います。
5. Findings は重大度と disposition を付けて統合されます。

## 完了条件

- 担当ごとの owned scope が明確
- 同じファイルを複数担当が同時に編集していない
- Trial focus と検証結果が成功条件に対応している
- Critical / Major の不足が残っていない

## 注意点

`party_quest` は人数を増やすこと自体が目的ではありません。
risk、coupling、blast radius、validation result、confidence、cost を見て、必要な分だけ担当と reviewer を置きます。

