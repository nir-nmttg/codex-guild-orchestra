# codex-guild-orchestra

Codexを、成果品質、安全な権限境界、検証可能性を優先して動かすためのGuild runtimeテンプレートです。実作業のリポジトリとオーケストレーション用の静的契約・動的状態を分離し、リスクに応じた委譲と検証を支援します。

現在のバージョンは `1.1.0` です。

> [!IMPORTANT]
> このプロジェクトは独立したコミュニティプロジェクトであり、OpenAIによる公式提供、提携、支援、承認を受けたものではありません。Codex、GPTおよびOpenAIはOpenAIの商標または登録商標です。本プロジェクトはOpenAIのロゴを使用しません。

## 特徴

- `Guild Law`: 対象リポジトリ、secret・PII、状態更新に関する安全境界
- task contract: objective、success criteria、scope、authority、validationの明確化
- `evidence_state`: blocker、失敗したcheck、scope drift、high-risk trigger、検証状況の追跡
- risk-based delegation / Trial: 独立して境界を切れる作業だけをagentへ委譲
- `Ledger`: 検証根拠と残リスクを記録するSQLite監査履歴
- helper-issued snapshotとqueue lineageのfail-closedな検証

数値confidence、固定回数のread・test、全案件共通の長いchecklistには依存しません。Rootはtop-level assignmentを直接作り、唯一のnested edgeとして`inquisitor`からterminal `examiner`への単一focus委譲だけを許可します。モデル選択の方針と現在のrole別構成は[モデル選択評価](docs/model-selection-evaluation.md)を参照してください。

## 前提条件

- Git
- Docker EngineまたはDocker Desktop（`docker build`と`docker run`を実行できること）
- Codexのproject-local設定とcustom agentを利用できる環境
- Docker imageの初回build時に、base imageとPython依存関係を取得できるネットワーク

ホストへPythonパッケージを直接インストールする必要はありません。検証と導入スクリプトはDocker内のPythonで実行されます。

## インストール

導入先には、子リポジトリではなく、その親となるGuild rootを指定します。既存環境へ導入する場合は、先にdry-runし、`--backup`を付けてください。

```bash
./scripts/install.sh --target /path/to/guild-root --mode copy --dry-run
./scripts/install.sh --target /path/to/guild-root --mode copy --backup
```

実作業リポジトリは`<guild_root>/repositories/<repo>`に置きます。`target_repo_root`はこの直下にある個別リポジトリのGit rootだけです。

### 変更される範囲

インストーラーは指定したGuild rootの次の範囲を作成または更新します。

- `AGENTS.md`内の`codex-guild-orchestra`管理ブロック
- `.agents/orchestra/`と、ownerが本プロジェクトである`.agents/skills/`
- `.codex/`
- `.orchestra/`（queue、Ledger、dashboardなどの動的状態）
- `repositories/`ディレクトリ
- Gitリポジトリの場合は`.git/info/exclude`内の管理ブロック（`--no-git-exclude`で省略可能）

`--backup`を付けると、既存の`AGENTS.md`、`.git/info/exclude`、`.agents/`、`.codex/`、`.orchestra/`を`<guild_root>/.codex-guild-orchestra-backups/<timestamp>/`へコピーしてから導入します。`repositories/`配下の実作業リポジトリはバックアップ、移動、削除の対象ではありません。

更新時は、同じバックアップ処理を行う次のコマンドも利用できます。

```bash
./scripts/sync.sh --target /path/to/guild-root
```

## 検証

```bash
make validate
```

validatorは安全境界、compact prompt、role・modelの固定値、queue・snapshot契約、最終成果のhard gate、日本語化方針を確認します。インストール予定だけを確認する場合は次を実行します。

```bash
make install-dry-run
```

## アンインストールと復元

自動アンインストールコマンドは現在ありません。復元が必要な場合はCodexや関連プロセスを停止し、現在の状態を別途保全したうえで、`.codex-guild-orchestra-backups/<timestamp>/`に保存された各パスを元のGuild rootへ戻してください。バックアップに存在しない新規作成物は自動では削除されません。

管理対象を手動で除去する場合も、`repositories/`配下には触れず、上記「変更される範囲」だけを対象にしてください。`AGENTS.md`と`.git/info/exclude`はファイル全体ではなく、本プロジェクトの開始・終了markerで囲まれた管理ブロックだけを除去します。`.orchestra/`には監査履歴が含まれるため、削除前に必要な保全を行ってください。

`clean_install.sh`はアンインストーラーではありません。管理対象を整理して再導入するためのコマンドであり、動的状態を初期化します。

## 対応範囲と既知の制約

- 導入modeは現在`copy`のみです。
- runtime schema v3を前提とします。古いschemaの状態は、そのまま保持更新できない場合があります。
- Docker imageはbuild時に外部registryとPython package indexへ接続します。オフライン環境では事前準備が必要です。
- Codexやモデルの提供状況、設定形式、利用条件の変更により、role設定の調整が必要になる場合があります。
- 本プロジェクトの安全境界は運用を支援する契約であり、OS、container、GitHubなどのアクセス制御を代替しません。
- `repositories/`配下のアプリケーション自体の品質、ライセンス、セキュリティは各リポジトリの管理者が確認してください。

利用例は[ユースケース集](docs/use-cases/README.md)、設計の詳細は[orchestration runtime](docs/orchestration-runtime.md)と[agent deployment](docs/agent-deployment.md)を参照してください。

## セキュリティ

secret、token、credential、password、key、認証情報、PIIは読まず、書かず、要約しません。破壊的操作、依存追加、migration、deploy、本番影響、認可、公開API互換性変更、外部network有効化には人間の確認を要求します。

脆弱性の可能性がある情報を公開Issueへ投稿しないでください。報告方法と対応バージョンは[セキュリティポリシー](SECURITY.md)を参照してください。

## コントリビューションとサポート

IssueやPull Requestを送る前に[コントリビューションガイド](CONTRIBUTING.md)と[行動規範](CODE_OF_CONDUCT.md)を確認してください。利用方法の質問とサポート範囲は[サポート方針](SUPPORT.md)に記載しています。

直接依存関係のライセンスinventoryは[第三者ライセンスに関する通知](THIRD_PARTY_NOTICES.md)を参照してください。

## ライセンス

このプロジェクトは[MIT License](LICENSE)で提供されます。[日本語参考訳](LICENSE.ja.md)も用意していますが、法的効力を持つ条件は英語版の`LICENSE`が優先します。
