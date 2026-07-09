# GPT-5.6 role model selection

この文書は、Codex Guild Orchestra の各 role に固定する model と reasoning effort の選定根拠を記録します。
以前の割り当てを正解として扱わず、role contract、失敗時の波及、並列頻度、代表 stress case の結果から決定しました。

## 前提

- 評価日: 2026-07-10
- Codex CLI: `0.144.0-alpha.4`
- model catalog:
  - `gpt-5.6-sol`: frontier agentic coding model
  - `gpt-5.6-terra`: balanced everyday agentic coding model
  - `gpt-5.6-luna`: fast and affordable agentic coding model
  - `gpt-5.3-codex-spark`: ultra-fast coding model
- 5.6 系は `low / medium / high / xhigh / max` を利用でき、Sol / Terra は `ultra` も利用できます。
- `ultra` は自動委譲が明示 assignment と terminal worker 契約に干渉し得るため候補から除外しました。
- `courier` はユーザー指定により `gpt-5.3-codex-spark / xhigh` を維持し、model 選定の対象外としました。

公式の [Codex Subagents guidance](https://developers.openai.com/codex/subagents/) に従い、曖昧で多段の planning、tool use、validation を伴う role は高能力側、read-heavy な supporting work は Terra、複雑なロジック、仮定、edge case を扱う role は `high` 以上を候補にしました。

## 評価方法

role contract から authority、禁止行為、必須出力を hard gate として先に定義しました。
候補は `/tmp` の隔離された read-only 環境で `codex exec --ephemeral` を使い、同じ self-contained prompt を与えて比較しました。
結果は統計的な性能評価ではなく、隣接候補に role 固有の hard-gate 差があるかを確認する representative smoke です。
token 数は実行時の目安であり、固定の性能値や価格としては扱いません。

## 代表ケースの結果

| role | 比較 | 観測結果 | 選定への反映 |
| --- | --- | --- | --- |
| Root | Sol `high` / `xhigh` | どちらも未確定 repository と deployment approval を停止できた。`high` は target を推測せず assignment も作らず、`xhigh` は両 repository の調査 assignment を追加した | 全依頼を通る Root は Sol / `high` に固定 |
| cartographer | Terra `high` | token rotation の互換 rollout、nullable migration、並行 refresh、rollback、observability を危険地帯として整理できた | read-heavy mapmaking は Terra / `high` で品質下限を満たす |
| party_leader | Terra `high` / Sol `high` | Terra は migration file の owner を落とした。Sol は全 file を2担当へ非重複で割り当て、sequencing と security / rollback Trial を維持した | assignment の波及を重視して Sol / `high` |
| adventurer | Terra `high` / Sol `high` | どちらも transactional outbox、idempotent retry、observability、focused tests を提示した | 上流で scope が限定され最大5並列のため Terra / `high` |
| inquisitor | Terra `high` / Sol `high` | どちらも authorization 前 write を Critical、full token logging を重大 finding として reject した。Sol は同じ hard gate を短く満たした | 誤 accept の波及を重視して Sol / `high` |
| advisor | Luna `high` / Terra `high` | どちらも populated table への NOT NULL 追加、deploy / backfill 順、locking risk を検出した。Luna は focus と unknowns を保ったまま簡潔だった | owner 再検証を前提に Luna / `high` |
| quest_sentinel | Luna `medium` / `high` | confidence 92 の scope-drift case で `medium` は誤った `confidence_below_75` trigger を追加し、`high` は security-sensitive scope drift だけを扱った | Luna / `high` に固定 |

`guildmaster` は guild-scale の Party 境界、sequencing、safety gate に限定される低頻度 role で、失敗時の blast radius が最大です。
このため Sol / `xhigh` を固定します。`max` は今回の代表比較に含めておらず、固定常用を正当化する根拠がないため採用しません。

## 固定マトリクス

| role | model | reasoning effort |
| --- | --- | --- |
| Root | `gpt-5.6-sol` | `high` |
| `adventurer` | `gpt-5.6-terra` | `high` |
| `advisor` | `gpt-5.6-luna` | `high` |
| `cartographer` | `gpt-5.6-terra` | `high` |
| `courier` | `gpt-5.3-codex-spark` | `xhigh` |
| `guildmaster` | `gpt-5.6-sol` | `xhigh` |
| `inquisitor` | `gpt-5.6-sol` | `high` |
| `party_leader` | `gpt-5.6-sol` | `high` |
| `quest_sentinel` | `gpt-5.6-luna` | `high` |

Root と全 subagent はこの値を固定し、Quest の難度による動的な reasoning effort 切り替えは行いません。
model catalog、role contract、authority、並列数、または代表 stress case の失敗傾向が変わった場合は、この記録と固定マトリクスを同時に再評価します。
