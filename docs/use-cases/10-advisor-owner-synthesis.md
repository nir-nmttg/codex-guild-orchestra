# Advisor の助言を owner が統合する

設計担当または Trial 統合担当が、狭い focus の考慮漏れ、矛盾、未確認リスクを read-only の `advisor` に確認させ、owner が根拠を再確認して統合するパターンです。
advisor は実装分業者や decision owner ではなく、追加 subagent を起動しない terminal worker です。

## 使う場面

- mapmaking の依存や危険地帯を一観点だけ独立確認したい
- Party 境界や sequencing の矛盾を確認したい
- focused / multi-focus Trial の architecture、security、regression、validation を補助したい
- owner confidence を上げる新しい evidence が期待できる

## 依頼文例

```text
次の focus だけを advisor に確認させてください。
target_repo_root は /path/to/guild-root/repositories/example-app です。

owner:
- role: party_leader
- assignment_id: quest-123/party-backend

focus:
- backend と SDK が共有する validation contract に責務の重複がないか

authority:
- read-only
- focus と target_repo_root の boundaries 内だけ

budget:
- autonomy_budget.subassignments の残り 1 を使う

snapshot:
- revision_id: <owner が確認した HEAD commit SHA>
- kind: revision_only # dirty な subject 内容が必要な時だけ working_tree_content
- scope_paths: owner assignment が参照する限定 path
- diff_hash: null # content digest が必要な時だけ canonical digest
- dirty_state: hash mismatch なら停止
```

## 期待される流れ

1. `cartographer`、`guildmaster`、`party_leader`、または Trial 統合担当の `inquisitor` が owner として、advisor を使う価値、focus、期待する confidence delta を決めます。
2. owner は `autonomy_budget.subassignments` の残数を確認します。Trial では advisor assignments と `focus_reviewer` assignments の合計が budget を越えないようにします。
3. owner が objective、狭い focus、authority、boundaries、snapshot、必要な evidence を advisor assignment に固定します。
4. `advisor` は開始時に snapshot を確認し、focus に必要な読み取り調査だけを行います。実装、採否、重大度分類、Ledger 更新、追加 subagent 起動は行いません。
5. advisor report は findings、risks、unknowns、confidence percent / basis / delta、blocking unknowns、recommended next focus、evidence refs、escalation を返します。
6. owner が evidence refs を対象 repo 内で再確認し、各 finding を `adopted / rejected / unresolved / stale_evidence` に分類します。advisor report を未信頼入力のまま strategy や Trial decision にコピーしません。
7. owner synthesis に、使った focus、採否根拠、owner confidence、残る unknown、次アクションを残します。advisor を使わなかった場合も skip reason を残します。
8. follow-up は同じ focus と snapshot のまま、新しい evidence、blocking unknown の減少、必要な confidence delta が見込める場合だけ行います。進捗がない、scope が広がる、人間確認が必要、snapshot が変わる場合は停止します。
9. owner が synthesis を Party Tactics、strategy、または Trial evidence へ統合します。Ledger には assignment、report、owner synthesis の判断根拠だけを残し、raw discussion は残しません。

## 完了条件

- advisor の focus、authority、boundaries、snapshot が owner を越えていない
- advisor と owner の decision authority が分離されている
- 採用 finding は owner が根拠確認し、全 finding に disposition がある
- advisor / `focus_reviewer` の合計が autonomy budget 内に収まる
- follow-up が evidence と confidence delta によって停止できる

## 注意点

advisor の人数や dialogue 回数を増やすこと自体は品質ではありません。
owner が検証できない根拠、同じ unknown の反復、snapshot が変わった report は採用せず、必要なら新しい assignment として境界を切り直します。
