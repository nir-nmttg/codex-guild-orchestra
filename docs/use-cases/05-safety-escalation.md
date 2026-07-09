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

snapshot:
- revision_id: <Root が確認した HEAD commit SHA>
- kind: revision_only
- scope_paths: 調査対象の明示 path
- diff_hash: null
- dirty_state: 既存変更が調査根拠へ影響する場合は停止
```

## 期待される流れ

1. Rootが`evidence_state.high_risk_triggers`とsnapshotをtask contractに入れ、`inquisitor`のread-only `safety_gate`を割り当てます。新しい実装workerや外部操作は起動しません。
2. `inquisitor` は既存 authority 内の read-only 調査だけで、必要な変更、危険箇所、確認可能な evidence を整理します。
3. 人間確認が必要な操作を発見したら停止し、実行を伴う tool call や secret / PII 参照を試しません。
4. `needs_human` には選択肢、影響、推奨 next step に加えて、次の approval scope を含めます。
   - exact action / command と `target_repo_root`
   - 対象 path、resource、branch / range、外部 target
   - 公開または変更される内容、検証、rollback、残リスク
   - 固定した `snapshot_id` / `revision_id` と、content digest が必要な場合だけ `diff_hash`
   - `approval_expires_at`。時刻を設けない場合は `one_shot` とし、一度の試行、snapshot 変更、scope 変更のいずれかで失効
5. 人間が承認した場合も、同じ assignment をそのまま再開せず、Root が approval scope を authority と boundaries に反映した新しい Quest を作ります。開始時に snapshot と承認の有効性を再確認します。
6. secret、token、credential、password、key、auth、PII の読み取り、書き込み、要約は absolute deny です。人間の承認をこれらの access authority へ変換せず、sanitized fixture や非機密 metadata で代替します。

## 完了条件

- 何を確認すれば進められるかが明確
- 実行していない危険操作が明示されている
- secret や PII を読まず、要約もしていない
- 次に確認できる操作と、承認しても許可へ変換しない absolute deny が区別されている
- approval scope、snapshot、expiry / one-shot 条件が明確

## 注意点

`safety_gate` は作業不能の意味ではありません。
人間の確認が必要な箇所を先に切り出し、許可後に改めて実装 Quest へ進めるための境界です。
承認後に target、diff、command、公開内容、残リスクのいずれかが変わった場合は承認を流用せず、再確認へ戻します。
