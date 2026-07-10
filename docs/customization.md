# カスタマイズ

`template/AGENTS.md`はモデル向けcompact kernel、`template/.agents/orchestra/config/settings.yaml`は機械契約です。安全規則を複数surfaceへコピーしないでください。

## 変更できるもの

- fast pathとmaterial taskの分類
- rankの説明
- subagent roleごとのmodelと固定reasoning effort
- Rootのreasoning effort（`high`、`xhigh`、`max`。既定は`high`、`max`は明示利用だけ）
- change-type別Trial check
- evidence/outputの表現
- worker並列数

## 保持するもの

- `target_repo_root`境界
- secret/PII absolute deny
- 既存ユーザー変更の保持
- local Gitと外部更新のauthorization
- snapshot/lineage mismatchのfail-closed
- high-risk実装者と最終decision ownerの分離

## Prompt hygiene

- custom agent TOMLはrole固有の短いjob、authority、outputだけにします。
- `common.md`や`settings.yaml`を全agentへ常時再読込しません。
- 数値confidence、固定read/test回数、sage/examinerの未使用理由、全変更共通の長いchecklistを追加しません。
- 新しい規則は、実際のevalで特定されたfailureを直す時だけ追加します。
- schema、snapshot、lineage、metadataはpromptではなくvalidator/helperへ置きます。

## Role topology

Rootだけがagentを起動し、custom agentはterminalです。bounded実装とcross-scope integrationを別roleにし、read-heavy作業の並列化を優先します。

role追加は、既存roleでは相反するauthority/model要件があり、代表taskの評価で品質改善が確認できる場合だけ行います。

## Validation

`scripts/validate.py`はprompt行数、禁止された旧制約、role/model固定値、terminal設定、安全契約、queue/snapshot、final outcome hard gateを検証します。
