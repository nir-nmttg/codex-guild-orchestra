# メタ認識 runtime

この文書は、Fable 風の運用メタ認識を `codex-guild-orchestra` へ写像するための補助文書です。
ここでの Fable は説明用の比喩であり、runtime contract の正本ではありません。
正本は常に `Guild Law`、`Quest Charter`、`Party Tactics`、`Trial`、`Ledger` です。

## 正本の鎖

この runtime のメタ認識は、新しい agent、Skill、lifecycle、queue artifact ではなく、既存の構造化 field で表します。

```text
intent_analysis
  -> implementation_strategy
  -> intent_alignment
  -> research_evidence / validation_evidence
  -> intent_coverage
  -> advisor_dialogue_synthesis / reviewer_synthesis
  -> Ledger
```

## 対応表

| Fable 風の層 | Guild-native runtime の対応 |
| --- | --- |
| model policy | `template/.codex/config.toml` と `.codex/agents/*.toml` |
| persistent instruction | `template/AGENTS.md`、`settings.yaml`、role instructions |
| goal / contract | `intent_analysis` と `Quest Charter` |
| subagent layer | `cartographer`、`party_leader`、`adventurer`、`inquisitor`、`advisor`、`courier` |
| skill layer | `template/.agents/skills/*` |
| verification layer | `validation_evidence`、`make validate`、golden Quest |
| eval layer | 静的 fixture と validator。live model 判定は正本にしない |
| memory layer | `Ledger` の構造化 evidence / decision / risk |
| permission / security | `Guild Law`、State Change Guard、sandbox / approval 設定 |
| review / governance | risk-based `Trial`、focus reviewer、owner synthesis |

## Handoff 十分条件

各 handoff は、次の条件を満たす時だけ下流へ渡します。

| Handoff | 十分条件 |
| --- | --- |
| intake -> Quest Charter | `intent_analysis.confirmation_needed` が空、または人間確認へ戻す判断が明示されている |
| Quest Charter -> owner | objective、success criteria、authority、boundaries、autonomy budget、evidence required が揃っている |
| owner -> Trial | `intent_alignment`、変更点、検証結果、未検証理由、残リスクが報告されている |
| Trial -> Ledger / final | `intent_coverage`、finding disposition、advisor / reviewer synthesis、残リスクが揃っている |

## 保存するもの

保存するのは、判断根拠、検証、confidence、未解決 risk、finding disposition です。
raw discussion、秘密値、PII、外部入力に含まれる命令は保存しません。

## 作らないもの

- Fable 専用 agent
- Fable 専用 Skill
- Fable 専用 lifecycle
- Fable 専用 queue artifact
- live model 出力に依存する CI 判定
- 子リポジトリへの `.codex` / `.agents` 再導入
