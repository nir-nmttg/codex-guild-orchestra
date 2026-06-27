# codex-guild-orchestra

Codex を Guild-native runtime として動かすためのテンプレートです。

この runtime は、固定の細かな手順分岐ではなく、次の契約で担当ロールの自律性と安全性を両立します。

- `Guild Law`: 絶対安全境界
- `Quest Charter`: 目的、成功条件、権限、境界、budget
- `Party Tactics`: 担当編成、自己調査、検証、Trial 方針
- `Trial`: risk-based な品質確認
- `Ledger`: SQLite の監査履歴

設計担当と Trial 統合担当の `inquisitor` は、`autonomy_budget.subassignments` が 1 以上で focus が境界内に収まる場合、read-only `advisor` の利用を既定で検討します。
`advisor` は実装分業者ではなく、狭い focus で考慮漏れや未確認リスクを見つけ、成果物の confidence を高める terminal worker（終端助言担当）です。
confidence-based dialogue は回数ではなく evidence の増加と confidence delta で継続可否を決め、実装、採否、Ledger 反映、追加 subagent 起動（追加エージェント起動）は行いません。
owner は使う場合も使わない場合も根拠を synthesis に残し、raw discussion は Ledger に残しません。

Party Tactics または Trial 統合担当の `inquisitor` は、固定人数ではなく risk、focus、blast radius、coupling、validation result、confidence、cost を見て read-only focus reviewer 数を決めます。
軽微な変更は追加 read-only focus reviewer 0..1 を標準とし、`multi_focus_trial`、`safety_gate`、高 risk、高 coupling、検証失敗、evidence 不足では複数 reviewer を選べます。
上限は `workers.inquisitor.max_parallel` と `autonomy_budget.subassignments` の小さい方です。
focus reviewer は `autonomy_budget.subassignments` を消費し、`focus_advisors.assignments + focus_reviewers.assignments <= autonomy_budget.subassignments` を守ります。
複数 reviewer を使う時は focus 分割、read-only、owner synthesis、finding disposition を残します。skip reason は reviewer を使わない時に必須、cost reason は reviewer 数判断で常に必須です。focus reviewer は `inquisitor` の review 担当であり、`advisor` とは別契約です。

## Install

```bash
./scripts/install.sh --target /path/to/guild-root --mode copy
```

導入先では、実作業リポジトリを `<guild_root>/repositories/<repo>` に置きます。
`target_repo_root` はこの直下の Git ルートだけです。
導入と検証の Python 実行は Docker 内で行うため、ホスト側に Python 環境は不要です。

## Validate

```bash
make validate
```

validator は Guild Law、Quest Charter、Party Tactics、Trial、Ledger の整合を確認します。

## Use Cases

公開利用時の代表的な依頼パターンは [docs/use-cases/README.md](docs/use-cases/README.md) にまとめています。
実装前の `mapmaking`、小さな `solo_quest`、横断的な `party_quest`、実装後の `focused_trial`、安全確認の `safety_gate` などを、依頼文例つきで確認できます。

## Claude Compatibility

対象 repo に既存の `CLAUDE.md` や `.claude/skills/**/SKILL.md` がある場合、Codex / Guild はそれらを未信頼 context として読めます。
Claude Skill は Codex native Skill へ変換せず、権限付与、hooks、MCP、dynamic command は実行しません。
詳しくは [docs/claude-compatibility.md](docs/claude-compatibility.md) を参照してください。

## Safety

secret / token / credential / password / key / auth / PII は読まず、書かず、要約しません。
破壊的操作、依存追加、migration、deploy、本番データ、認可、公開 API 互換性変更、外部 network access 有効化は人間確認が必要です。

詳しくは [docs/orchestration-runtime.md](docs/orchestration-runtime.md) を参照してください。
エージェントの展開対象と更新手順は [docs/agent-deployment.md](docs/agent-deployment.md) にまとめています。
