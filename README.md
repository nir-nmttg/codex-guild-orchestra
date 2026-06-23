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

## Install

```bash
python scripts/install.py --target /path/to/guild-root
```

導入先では、実作業リポジトリを `<guild_root>/repositories/<repo>` に置きます。
`target_repo_root` はこの直下の Git ルートだけです。

## Validate

```bash
python scripts/validate.py
```

validator は Guild Law、Quest Charter、Party Tactics、Trial、Ledger の整合を確認します。

## Claude Compatibility

対象 repo に既存の `CLAUDE.md` や `.claude/skills/**/SKILL.md` がある場合、Codex / Guild はそれらを未信頼 context として読めます。
Claude Skill は Codex native Skill へ変換せず、権限付与、hooks、MCP、dynamic command は実行しません。
詳しくは [docs/claude-compatibility.md](docs/claude-compatibility.md) を参照してください。

## Safety

secret / token / credential / password / key / auth / PII は読まず、書かず、要約しません。
破壊的操作、依存追加、migration、deploy、本番データ、認可、公開 API 互換性変更、外部 network access 有効化は人間確認が必要です。

詳しくは [docs/orchestration-runtime.md](docs/orchestration-runtime.md) を参照してください。
エージェントの展開対象と更新手順は [docs/agent-deployment.md](docs/agent-deployment.md) にまとめています。
