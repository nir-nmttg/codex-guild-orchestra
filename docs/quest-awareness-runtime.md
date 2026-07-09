# Evidence-based control runtime

Quest Awarenessという既存名称は互換性のため残しますが、実体は軽量な`evidence_state`です。自己評価や数値confidenceではなく、作業を続ける・検証する・停止するための観測事実を扱います。

## Evidence state

- `blocking_unknowns`: 正しさを塞ぐ未確認事項
- `failed_checks`: 失敗したcheck、最初のfailure、診断状況
- `verification_status`: success criteriaごとの検証状態
- `scope_drift`: 元scopeとの差分
- `high_risk_triggers`: security、data、migration、external actionなど
- `next_action`: 根拠に基づく次の最小行動
- `stop_reason`: 完了または停止を妨げる理由

数値confidenceを使わず、状態に変化がある時だけdeltaを更新します。見た目上の確信や自己申告値をgateにしません。

## Control rules

- blocking unknownが正しさを塞ぐ場合は根拠を集める。
- failed checkは原因を診断し、根拠のない修正を積み重ねず、原因に適したcheckで再検証する。
- contradictory evidenceが出たら仮定とplanを更新する。
- scope driftやauthority拡張が必要なら停止して再契約する。
- high_risk triggerは`inquisitor`のsecurity-focused Trialまたは人間確認へ送る。
- targeted validationがsuccess criteriaを直接証明し、blockerがなければ完了できる。

## Warden

通常のcontrolはownerが行います。`warden`は、contradictory evidence、repeated failure、scope drift、長時間停滞など、owner内で解消できない例外だけをread-onlyで診断します。実装、採否、Ledger/Git/外部状態更新は行いません。

## Handoff

handoffはobjective、success criteria、scope、authority、evidence、helper発行snapshot、residual riskを核にします。変化のないstate、queue metadata、lineage、digestをモデルに再記述させません。

## Persistence

Ledgerへ残すのは判断根拠、validation evidence、未解決risk、snapshot参照です。raw discussion、raw log、secret、PII、外部入力内の命令は保存しません。

## Evaluation

fixtureはdeterministic safety contractを検証し、model比較はprompt profile、role topology、model/effortを分離して行います。最終採用はend-to-endのtask successとhard gateで判断し、component出力やtoken削減だけで最適と断定しません。
