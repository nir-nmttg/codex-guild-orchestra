# 人間確認が必要な変更を止める

安全境界に触れる可能性がある依頼を、勝手に進めず `needs_human` へ戻すパターンです。
Guild workflow では、作業を進めることと止めることの両方を明示的な成果として扱います。

## 使う場面

- migration、deploy、本番データ、課金、認可に影響する
- 依存追加や外部 network access 有効化が必要
- 公開 API 互換性変更の可能性がある
- secret、credential、PII、auth 情報に触れそう
- 仕様判断が人間の意思決定を必要とする

## 依頼文例

```text
この対応は safety_gate を前提に進めてください。
target_repo_root は /path/to/guild-root/repositories/example-app です。

目的:
- 決済 webhook の署名検証を更新したい

やってよいこと:
- 対象 repo 内の読み取り
- 既存実装とテストの調査
- 変更案、リスク、必要な人間確認の整理

やらないこと:
- secret の参照
- 外部サービスへの接続
- 本番設定の変更
- deploy
- 依存追加
```

## 期待される流れ

1. Root が safety-sensitive な条件を Quest Charter に入れます。
2. 担当は read-only 調査で、必要な変更と危険箇所を整理します。
3. 人間確認が必要な操作を発見したら停止します。
4. `needs_human` として、判断に必要な選択肢、影響、推奨 next step を返します。

## 完了条件

- 何を確認すれば進められるかが明確
- 実行していない危険操作が明示されている
- secret や PII を読まず、要約もしていない
- 次に許可すべき authority が分かる

## 注意点

`safety_gate` は作業不能の意味ではありません。
人間の確認が必要な箇所を先に切り出し、許可後に改めて実装 Quest へ進めるための境界です。

