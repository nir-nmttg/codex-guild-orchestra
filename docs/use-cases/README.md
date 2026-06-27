# ユースケース集

このフォルダは、codex-guild-orchestra を一般公開されたテンプレートとして使う時の代表的な依頼パターンをまとめています。
正本は [オーケストレーションランタイム](../orchestration-runtime.md) と [Guild Quest Lifecycle](../guild-quest-lifecycle.md) です。

## 前提

- Codex はギルド規約ルートで起動します。
- 実作業リポジトリは `<guild_root>/repositories/<repo>` に置きます。
- `target_repo_root` は対象 repo の Git ルートだけです。
- secret / token / credential / password / key / auth / PII は読ませません。
- 破壊的操作、依存追加、migration、deploy、本番影響、認可、公開 API 互換性変更、外部 network access 有効化は人間確認を挟みます。

## パターン一覧

| パターン | 向いている場面 | 主な Rank / Trial |
| --- | --- | --- |
| [実装前の地図作成](01-mapmaking-before-implementation.md) | まだ直し方を決めず、調査と方針だけほしい | `mapmaking` / `none` or `self_check` |
| [小さな修正を自律実装する](02-small-fix-solo-quest.md) | 明確な不具合、軽い UI / docs / test 修正 | `solo_quest` / `self_check` |
| [横断変更を分業する](03-party-quest-cross-cutting-change.md) | 複数領域にまたがる変更、独立 Trial が有効 | `party_quest` / `focused_trial` |
| [実装済みブランチを確認する](04-focused-trial-after-implementation.md) | 仕上げ前に破綻、漏れ、回帰リスクを見たい | `focused_trial` |
| [人間確認が必要な変更を止める](05-safety-escalation.md) | migration、deploy、外部状態変更、秘密情報周辺 | `safety_gate` |
| [Ledger と Git 操作を明示する](06-ledger-and-local-git.md) | 作業記録、commit、PR 説明準備を分けたい | `solo_quest` + `courier` |
| [Claude context を参考情報として使う](07-claude-context.md) | 既存 repo に `CLAUDE.md` や `.claude/` がある | 任意 / risk-based |

## 選び方

迷う場合は、まず `mapmaking` で依頼します。
実装に進めるだけの目的、成功条件、境界、検証方針が揃ってから `solo_quest` 以上へ進めると、作業範囲を広げすぎずに済みます。

軽い修正でも、仕様判断、公開 API 互換性、認可、データ移行、本番影響が絡む場合は `safety_gate` として扱います。
逆に単なる質問、日時確認、短い説明は full Quest 化する必要はありません。

