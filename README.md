# codex-guild-orchestra

Codexを、成果品質・安全な権限境界・検証可能性を優先して動かすGuild runtimeテンプレートです。

GPT-5.6向けに、永続promptは次のcompact kernelへ整理されています。

- `Guild Law`: target repo、secret/PII、状態更新の安全境界
- task contract: objective、success criteria、scope、authority、validation
- `evidence_state`: blocker、failed check、scope drift、high-risk trigger、検証状況
- risk-based delegation / Trial: 独立したbounded workにだけagentを使う
- `Ledger`: 検証根拠と残リスクを記録するSQLite監査履歴

数値confidence、sage/examinerの未使用理由、固定read/test回数、全案件共通の長いchecklistは使いません。snapshot、queue lineage、metadataはモデルに生成させずhelper/validatorがfail closedで確認します。

Rootはtop-level assignmentを直接作り、唯一のnested edgeとして`inquisitor`からterminal `examiner`への単一focus委譲だけを許可します。Root modelはSolですが、project-local reasoning effortは固定せず、起動時/UI/global configなどの利用者選択へ委ねます。model selection評価ではRootのhighをbaselineにし、maxはroutine evalやsubagentでは使いません。現在のsubagent deploymentは`guildmaster`だけSol/xhigh、他の5.6 roleはSol/highを維持しつつ、bounded roleではTerra/high、`sage`ではLuna/highをrole別live非劣性で評価します。`courier`は5.3-Spark/xhighを維持します。

## Install

```bash
./scripts/install.sh --target /path/to/guild-root --mode copy
```

実作業repoは `<guild_root>/repositories/<repo>` に置きます。`target_repo_root`はこの直下のGit rootだけです。導入と検証はDocker内のPythonで行います。

## Validate

```bash
make validate
```

validatorは安全境界、compact prompt、role/model固定値、queue/snapshot契約、最終成果のhard gateを確認します。モデル・prompt・役割構成の比較方法は [model selection evaluation](docs/model-selection-evaluation.md) を参照してください。

## Use cases

[docs/use-cases](docs/use-cases/README.md) にfast path、小規模実装、並列実装、cross-scope integration、risk-triggered Trial、安全停止、例外的Wardenをまとめています。

## Safety

secret、token、credential、password、key、認証情報、PIIは読まず、書かず、要約しません。破壊的操作、依存追加、migration、deploy、本番影響、認可、公開API互換性変更、外部network有効化は人間確認が必要です。

詳細は [orchestration runtime](docs/orchestration-runtime.md) と [agent deployment](docs/agent-deployment.md) を参照してください。
