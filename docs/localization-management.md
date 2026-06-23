# 日本語化管理

このリポジトリでは、人間が読む説明文、手順、ステータスメッセージを日本語で管理します。

## 対象

- `README.md`
- `docs/**/*.md`
- `template/**/*.md`
- `template/**/*.toml`
- `template/**/*.json`
- `template/**/*.yaml`
- `template/**/*.yml`
- Pythonスクリプトの文字列リテラル（CLI説明、ログ、エラーメッセージを含む）

## 英語のまま残すもの

次は日本語化せず、意味が壊れないよう英語のまま残します。

- コマンド、オプション、環境変数
- ファイル名、ディレクトリ名、設定キー、JSONキー
- ギルド役割名、Skill名、hook名
- フレームワーク名、サービス名、一般的な技術用語
- ライセンス本文

許可する英語用語は [localization-allowlist.txt](localization-allowlist.txt) で管理します。

## 用語方針

ギルド側が扱う単位の人間向け表現は「クエスト」に統一します。内部スキーマでは Quest、assignment、Trial、report、message を正本語彙にします。ファイル名、CLI 名、SQLite table 名などの技術識別子は英語のまま残します。

## Guild 命名規約

人間向けの説明では Guild テーマの語彙を優先します。内部互換性のために英語識別子を残す場合は、初出または近い説明で日本語の意味を添えます。

| 避ける表現 | 推奨表現 | 残してよい場面 |
| --- | --- | --- |
| task / ticket | Quest / クエスト / 作業 | legacy 拒否テスト、旧 schema 説明 |
| route | 手順分岐 / 進め方 | CLI、外部ライブラリ、引用 |
| agent | 担当ロール / 担当 | `.codex/agents`、Codex 機能名、ファイル名 |
| worker | 担当 / 終端助言担当 | `workers` 設定キー、`terminal_worker` schema |
| assignment | 割り当て（assignment） | SQLite table、YAML key、event payload |
| report | 報告（report） | SQLite table、YAML key、event payload |
| state | 状態 / 動的状態 | SQLite entity、`runtime state` などの技術説明 |

廃止済みの `spark`、`scout`、`campaign` は active contract には戻しません。旧値拒否、削除済みファイル検出、互換性説明、モデル名など、残す理由が明確な場所だけで使います。

## 監査

未翻訳らしい英語文を確認します。

```bash
make audit-ja
```

テンプレート構造の検証と合わせて確認する場合は:

```bash
make validate
```

監査で検出された語が技術用語として妥当なら、本文を無理に訳さず `docs/localization-allowlist.txt` に追加してください。説明文として自然に日本語化できる場合は、本文を直します。
