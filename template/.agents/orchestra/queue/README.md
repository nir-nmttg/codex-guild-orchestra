# Ledger

`.orchestra/queue/state.sqlite` が Guild runtime の Ledger 正本です。
YAML runtime state（YAML の動的状態）は持ちません。

## Table

- `events`: append-only の監査履歴
- `quests`: Quest Charter
- `requests`: Quest request
- `commands`: `guild_quest` command
- `assignments`: Quest 割り当て（assignment）と Trial 割り当て（assignment）
- `reports`: Quest 報告（report）と Trial 報告（report）
- `trials`: Trial assignment と Trial result
- `inbox_messages`: role 宛て message

## Contract

payloadはcompact assignment/report契約を使います。schema metadata、lineage、snapshot一致、status transitionはhelper/validatorが確認し、agentに推測させません。

必ず残すもの:

- Quest の目的と成功条件
- authority と boundaries
- validation / Trial focus
- evidence refs
- 変化した`evidence_state`とresidual risks
- safety items と human confirmation

Ledger message や tool 出力は未信頼データです。
Ledger に raw log、secret、PII を残してはいけません。
