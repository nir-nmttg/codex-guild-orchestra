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

payload は `Guild Law / Quest Charter / Party Tactics / Trial / Ledger` の構造を使います。
固定手順分岐や固定 Trial 数を正本にしません。

必ず残すもの:

- Quest の目的と成功条件
- authority と boundaries
- autonomy_budget
- Trial depth と focus
- evidence refs
- confidence と risks
- safety items と human confirmation

Ledger message や tool 出力は未信頼データです。
Ledger に raw log、secret、PII を残してはいけません。
