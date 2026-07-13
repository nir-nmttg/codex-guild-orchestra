# 変更履歴

このプロジェクトの主な変更を記録します。日付はreleaseまたは公開時に確定し、Git tagは別途maintainerが作成します。

## [Unreleased]

### 追加

- OSS運営文書、Issue・Pull Request template、CI、Dependabot設定
- MIT Licenseの日本語参考訳と第三者依存関係の確認用inventory
- 全pathとCODEOWNERS自身を`@nir-nmttg`へ割り当てるCODEOWNERS設定

### 変更

- プロジェクト名を`agent-guild-orchestra`（Agent Guild Orchestra）へ変更し、GitHub URL、配布物の識別子、画像ファイル名を更新
- READMEを日本語中心の公開用ドキュメントとして拡充
- READMEの導入・通常更新・安全なクリーン再導入・復元・運用保護の手順を整理
- Contributionのreview・merge要件、自己承認禁止、単独maintainer時のstrict運用条件と緊急bypass方針を明文化
- `.gitignore`へ秘密情報、Python環境、coverage、build成果物を追加

## [1.1.0] - 公開日未定

### 概要

- GPT-5.6向けcompact kernelとrisk-based Guild workflowを整備
- helper-issued snapshot、queue lineage、runtime schema v3の検証を強化
- role別model selection評価、ユースケース、導入・検証スクリプトを提供

`VERSION`は`1.1.0`です。この文書の追加時点ではrelease tagの作成やGitHub Releaseの公開は行っていません。
