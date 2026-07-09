# Guild Quest Lifecycle

```text
Request
  -> risk-adaptive intake
  -> task contract when material
  -> Root direct assignments
  -> bounded execution
  -> integration barrier when parallel mutation
  -> risk-triggered Trial
  -> Ledger / final outcome
```

## Rank

| Rank | 適用 | Owner |
| --- | --- | --- |
| `mapmaking` | 未知領域のread-only調査 | `cartographer` |
| `errand` | 明白なbounded作業 | `adventurer` |
| `solo_quest` | 単一ownerの実装 | `adventurer` |
| `party_quest` | 複数owned scope | `party_leader` |
| `guild_quest` | 複数Partyと広域戦略 | `guildmaster` |

Rankは儀式を決めるものではなく、scope、owner、integration、Trialの判断材料です。

## Execution

- `party_leader`は共有artifactのowner、順序、owned scope、integration barrierを決めます。
- 各`adventurer`は一つのbounded scopeだけを変更します。
- 全resultが揃いmutationを止めた後、`integration_owner`がcross-scope glueと統合検証を担当します。
- Root、strategy role、review roleは実装を引き取りません。

## Evidence state

数値confidenceではなく、blocker、failed check、verification、scope drift、高リスクtriggerを使います。変化のない状態をhandoffごとに再記述しません。

## Trial

Trialはrisk-triggeredです。低リスクbounded変更はowner validation、高リスク・共有契約・互換性・security・migration・検証失敗は`inquisitor`の独立Trialへ進みます。

`focus_reviewer`は必要な単一focusだけを確認します。複数reviewerを使う場合はfocusを重複させず、`inquisitor`がevidenceとfinding dispositionを統合します。

## Safety

すべてのRankでtarget repo境界、secret/PII禁止、state-change authorization、snapshot fail-closedを維持します。
