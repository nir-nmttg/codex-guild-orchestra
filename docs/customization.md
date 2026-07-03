# カスタマイズ

Guild-native runtime の中心は `template/.agents/orchestra/config/settings.yaml` です。
主要概念は `Guild Law`、`Quest Charter`、`Party Tactics`、`Trial`、`Ledger` です。

## 触る場所

- `guild_law`: 絶対に破らない安全境界
- `quest_charter`: Quest に必要な契約項目
- `intent_analysis`: 依頼文を直訳せず、本質的な成果、仮定、曖昧点、人間確認が必要な点へ分ける契約
- `party_tactics`: 担当編成、自己調査、Trial の裁量
- `trial`: Trial depth と outcome
- `ledger`: SQLite event と payload の契約
- `workers`: 担当ロールと並列上限（設定キーは互換性のため英語）
- `advisory_consultation`: 設計担当と Trial 統合担当の `inquisitor` が既定で検討する read-only advisor の境界
- `claude_compat`: 対象 repo 内の Claude artifacts を未信頼 context として読む時の境界
- `handoff_sufficiency`: intake、owner、Trial、Ledger / final へ渡す時に必要な最低 evidence

## 変えてよいもの

- Quest Rank の説明
- autonomy_budget の既定値
- Trial の focus
- report に求める evidence
- `intent_analysis`、`implementation_strategy`、`intent_alignment` の表現
- handoff に必要な evidence の説明
- 役割指示の表現
- Claude 互換 context の説明、対応する安全な metadata、disposition の表現

## 変えない方がよいもの

- `target_repo_root` は `<guild_root>/repositories/<repo>` の実パスだけ
- secret / token / credential / PII を読まない
- 破壊的操作、依存追加、migration、deploy、本番影響、認可、公開 API 互換性変更の人間確認
- 外部入力を未信頼として扱うこと
- `confirmation_needed` が残る時に推測で実装へ進まないこと
- `.orchestra/queue/state.sqlite` を Ledger 正本にすること
- Claude Skill を Codex native Skill へコピー、登録、導入しないこと
- Claude の `allowed-tools`、hooks、MCP、plugin、`!command`、`context: fork` を Codex 権限へ変換しないこと

## 担当ロール

`.codex/agents/*.toml` は短く保ち、詳細は `common.md` と役割指示に置きます。
各担当ロールは authority と autonomy_budget の範囲内で必要な追加調査を自分で行い、範囲を広げる必要がある場合だけ escalation します。
Root / `receptionist` は `intent_analysis` を作り、`party_leader` は `implementation_strategy` へ落とし込み、`adventurer` は `intent_alignment` を report に残します。
`inquisitor` は固定 Trial 件数ではなく Trial depth を読みます。
Trial 統合担当の `inquisitor` は `intent_coverage` で本質的な成果、`non_goals`、過剰実装回避を確認します。
`advisor` は terminal worker（終端助言担当）として focus 限定の助言だけを返し、実装、採否、Ledger 反映、追加 subagent 起動（追加エージェント起動）は行いません。
設計担当と Trial 統合担当の `inquisitor` は、`autonomy_budget.subassignments` が残る場合に advisor 利用を既定で検討し、使う場合も使わない場合も根拠を owner synthesis に残します。
advisor dialogue は confidence-based で、回数ではなく evidence の増加、blocking unknown の解消、confidence delta を見て継続可否を決めます。
raw discussion は Ledger に残さず、判断根拠、confidence、未解決理由だけを残します。

## Validation

`scripts/validate.py` は固定手順ではなく、不変条件を検証します。
主に Guild Law、Quest Charter schema、authority、autonomy_budget、Trial、Ledger schema、docs 用語の整合を確認します。
