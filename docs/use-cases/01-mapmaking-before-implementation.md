# 実装前の地図作成

実装前に、対象領域、危険箇所、候補案、検証方針だけを整理したい時のパターンです。
コード変更は行わず、read-only の `cartographer` に地図を作らせます。

## 使う場面

- 未知のコード領域に手を入れる前に、影響範囲を見たい
- 仕様や設計の選択肢を比較したい
- いきなり修正せず、必要な Quest Rank を判断したい
- migration、認可、外部 API などの安全リスクがあるか先に知りたい

## 依頼文例

```text
この件は mapmaking として扱ってください。
target_repo_root は /path/to/guild-root/repositories/example-app です。

目的:
- 予約キャンセル処理の責務分割と影響範囲を整理する

やってよいこと:
- 対象 repo の読み取り
- 関連テストと既存設計の調査

やらないこと:
- 実装、ファイル編集、git 操作、Ledger 更新

出力:
- 現在の設計地図
- 危険箇所
- 候補案
- 推奨 Quest Rank
- Trial 方針
- 人間確認が必要な点
```

## 期待される流れ

1. Root が `target_repo_root` を `<guild_root>/repositories/<repo>` に固定します。
2. `Quest Charter` で read-only の authority と boundaries を明示します。
3. `cartographer` が対象領域を調べ、実装しない前提で地図を返します。
4. 必要なら次の `solo_quest`、`party_quest`、`safety_gate` に進めます。

## 完了条件

- 実装前に判断できるだけの根拠がある
- 触るべきファイル、触らないファイル、未確認リスクが分かる
- 次に取るべき Quest Rank と Trial depth が明示されている

## 注意点

`mapmaking` は作業を止めるためではなく、不要な変更を避けるための段階です。
方針だけで十分ならそこで終了し、実装が必要なら別 Quest として境界を切り直します。

