# コントリビューションガイド

agent-guild-orchestraへの関心と協力に感謝します。小さな修正も歓迎します。変更の目的と影響範囲を明確にし、検証可能なPull Requestにしてください。

## ライセンスと権利

本プロジェクトへ提出されたContributionは、別途明示的に合意しない限り、本プロジェクトと同じMIT Licenseで提供されます（inbound = outbound）。Contributionを提出することで、提出者は次を表明します。

- 自分で作成した、または提出する権限を正当に有する内容であること
- 雇用契約、委託契約、第三者の権利その他の義務に反しないこと
- 第三者コードを含む場合、その出典、ライセンス、変更点を明示し、本プロジェクトで再配布できること
- secret、token、認証情報、個人情報、非公開情報を含めていないこと

提出されたContributionの著作権は、提出者または正当な権利者に残ります。このガイドはContributor License Agreementではなく、提出者の権利を譲渡させるものではありません。

## Issueを作成する前に

1. 既存のIssueとドキュメントを検索してください。
2. セキュリティ上の問題は公開Issueにせず、[SECURITY.md](SECURITY.md)の非公開報告手順を利用してください。
3. バグの場合は、再現に必要な最小情報と、機密情報を除いたログを用意してください。
4. 大きな設計変更、依存追加、公開契約の変更は、実装前にIssueで合意を得てください。

## 開発と検証

必要な前提条件は[README](README.md#前提条件)を参照してください。変更後は、リポジトリが提供する検証経路を実行します。

```bash
make validate
git diff --check
```

インストーラーを変更した場合は、少なくともdry-runも確認してください。

```bash
make install-dry-run
```

検証を実行できなかった場合は、Pull Requestに理由と未確認リスクを記載してください。失敗した検証を省略して成功扱いにしないでください。

## Pull Request

- 誰でもIssueやPull Requestで変更を提案できます。`main`へ直接pushせず、必ずbranchからPull Requestを作成してください。
- 一つのPull Requestには、独立して説明・検証できる一つの目的を持たせてください。
- 既存の利用者変更を不要に上書きせず、目的外の整形やrenameを混ぜないでください。
- 変更内容、理由、検証結果、互換性への影響、残リスクを記載してください。
- ユーザー向け変更は必要に応じて`README.md`、関連文書、`CHANGELOG.md`も更新してください。
- 依存関係を追加または更新する場合は、必要性、ライセンス、供給網リスクを説明してください。

maintainerは、品質、安全性、scope、権利関係を確認し、修正や追加検証を依頼することがあります。

## Reviewとmerge

merge要件を満たす承認として扱うのは、対象リポジトリにwriteまたはadmin権限を持ち、かつ[CODEOWNERS](.github/CODEOWNERS)に指定されたreviewerの承認だけです。Pull Request作成者は自分のPull Requestを自己承認できません。作成者自身がwrite・admin権限を持つCODEOWNERであっても、別の適格なCODEOWNERによる承認が必要です。

現在のCODEOWNERは`@nir-nmttg`一名だけです。そのため、本人が作成したPull Requestにも承認を必須とするno-bypassのstrict運用を行うには、別のwriteまたはadmin権限を持つCODEOWNERを追加する必要があります。

この運用はCODEOWNERSファイルだけでは強制されません。maintainerはGitHubの`main` branch protectionまたはrulesetで、Pull Request、必要なCI、CODEOWNER review、古い承認の扱いなどを設定してください。

単独maintainerで、repository recoveryや緊急のsecurity対応のためにowner・adminのbypassを残す場合も、通常のmergeには使用しません。やむを得ずbypassした場合は、理由、検証結果、残リスクをPull Requestまたは追跡可能な記録へ残してください。
