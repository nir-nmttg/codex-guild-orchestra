# ユースケース集

この配下は代表例であり、すべてのtaskに同じ手順やfieldを要求する規範ではありません。共通の正本は`AGENTS.md`と`settings.yaml`のcompact contractです。各例では成果、安全、検証に必要な部分だけを選びます。

このフォルダは、codex-guild-orchestra を一般公開されたテンプレートとして使う時の代表的な依頼パターンをまとめています。
正本は [オーケストレーションランタイム](../orchestration-runtime.md) と [Guild Quest Lifecycle](../guild-quest-lifecycle.md) です。

## 前提

- Codex はギルド規約ルートで起動します。
- 実作業リポジトリは `<guild_root>/repositories/<repo>` に置きます。
- `target_repo_root` は対象 repo の Git ルートだけです。
- secret / token / credential / password / key / auth / PII は読ませません。
- 破壊的操作、依存追加、migration、deploy、本番影響、認可、公開 API 互換性変更、外部 network access 有効化は人間確認を挟みます。
- local Git 書き込みは具体的な操作名と対象範囲が明示された時だけ行い、外部送信や Web 状態更新は実行直前にも人間確認を挟みます。

## 共通 snapshot 契約

Quest、assignment、report、Trial、Ledger / Git 操作は `subject_snapshot` で対象 state に結び付けます。snapshot は `.agents/orchestra/scripts/docker_python.sh .agents/orchestra/scripts/snapshot_digest.py --repo <target_repo_root> ...` で作る `cgo-snapshot-v1` を使い、次を持ちます。

helperは通常repoに加え、targetと同じ親directoryにあるprimary worktree、backlink、common Git dir構造を検証できるstandard linked worktreeを扱います。任意のgitdir/commondir、Git config include / `core.worktree`、object alternates、worktree固有config、file-valued external config、fsmonitor、textconv、external diff、hostの`GIT_*`注入は拒否または無効化します。

- `snapshot_id`: snapshot 自体の identity。content digest がある場合は同じ SHA-256
- `kind`: clean な読み取り対象の `revision_only`、working tree の最終内容を表す `working_tree_content`、固定 commit 間の `commit_range`
- `revision_id`: snapshot の基準になる `HEAD` commit SHA
- `base_ref` / `head_ref`: kind に必要な場合だけ固定する ref
- `scope_paths` / `untracked_paths`: subject scope。untracked は明示 path だけを含める
- `diff_hash`: content digest が必要な kind の canonical SHA-256。`revision_only` では `null`
- `dirty_state`: `clean / dirty` と、dirty state を許可、除外、または停止する方針

`working_tree_content` は `git diff HEAD --binary --full-index --no-ext-diff -- <scope>` 相当の tracked patch と、path 順に整列した明示 untracked file の mode / size / content SHA-256 を length-prefixed serialization にします。stage / unstaged という保管場所は digest に含めないため、内容が同じなら stage 前後で hash は変わりません。rename、file mode、binary は Git binary patch に含めます。

helper は `target_repo_root` と Git root の一致を先に確認し、secret-like / PII-like path、symlink、repo escape を内容読み取り前に拒否します。拒否された対象は hash で代替せず、`needs_human` または scope 再設計へ戻します。

mutation を伴う並列 Quest は一つの global hash を全 worker に共有しません。

1. 全 assignment の開始点となる `base_snapshot`
2. 各 worker の重複しない owned scope だけを hash した `result_snapshot`
3. integration barrier 後、編集を停止して作る `integrated_snapshot`

先行 report は別 owned scope の変更だけでは stale にしません。owned scope が重複した、同じ scope が後から変わった、base revision が変わった場合は stale とします。Trial、Ledger / Git は barrier 後の integrated snapshot だけを使います。

read-only mapmaking、sage、warden dialogue は同じ `snapshot_id` と subject scope を再利用します。mutation、HEAD / scope の変更、dirty-state signal があった時だけ再計算し、毎回 global working tree を走査しません。受け手は mutation boundary、Trial 開始前、Git 操作直前、または変更 signal 時に再確認します。不一致なら evidence を流用せず `stale_evidence` として停止します。

Ledger には `snapshot_id`、kind、`revision_id`、subject scope、必要な `diff_hash`、判断根拠、検証、残リスクだけを残し、raw diff、raw log、秘密値、PII は残しません。

## 共通 handoff 契約

handoffはobjective、success criteria、scope、authority、evidence、helper発行snapshot、residual riskを核にします。`evidence_state`はblocking unknown、failed check、verification、scope drift、高リスクtriggerに変化がある時だけdeltaを渡します。

queue metadata、lineage、digest、statusはvalidatorが生成・照合し、agentに再記述させません。

handoff が不足する場合は完了扱いにせず、`needs_human`、`request_changes`、`stale_evidence`、または escalation として返します。

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
| [Guild Quest を複数 Party で進める](08-guild-quest-strategy-and-parties.md) | 広い影響、安全判断、複数 Party の sequencing が必要 | `guild_quest` / `multi_focus_trial` or `safety_gate` |
| [Warden で例外診断する](09-warden-control-loop.md) | 矛盾、scope drift、反復失敗で通常制御が停滞した | 例外時のみ |
| [Sage の助言を owner が統合する](10-sage-owner-synthesis.md) | 設計や Trial の狭い focus で考慮漏れを減らしたい | 任意 / sage consultation |

## 選び方

迷う場合は、まず `mapmaking` で依頼します。
実装に進めるだけの目的、成功条件、境界、検証方針が揃ってから `solo_quest` 以上へ進めると、作業範囲を広げすぎずに済みます。

軽い修正でも、仕様判断、公開 API 互換性、認可、データ移行、本番影響が絡む場合は `safety_gate` として扱います。
逆に単なる質問、日時確認、短い説明は full Quest 化する必要はありません。
