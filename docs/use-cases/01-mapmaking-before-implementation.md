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

cartographer がやらないこと:
- 実装、ファイル編集、git 操作、Ledger 更新

出力:
- intent_analysis
- 現在の設計地図
- 危険箇所
- 候補案
- implementation_strategy 候補
- 推奨 Quest Rank
- Trial 方針
- 人間確認が必要な点
- `evidence_state` のblocker、未確認リスク、検証状況
- evidence refs と sage synthesis
- `subject_snapshot`（clean なら `revision_only`。dirty な subject 内容が必要な時だけ限定 scope の `working_tree_content`）
```

## 期待される流れ

1. Root が `target_repo_root` を `<guild_root>/repositories/<repo>` に固定します。
2. `Quest Charter` で read-only の authority と boundaries を明示します。
3. Root が依頼文を直訳せず、推定意図、本質的な成果、仮定、曖昧点、`confirmation_needed` を `intent_analysis` に整理します。
4. Root が共通 snapshot 契約に従って `subject_snapshot` を固定し、`cartographer` は開始時に一致を確認します。clean な read-only mapmaking は `revision_only` を再利用し、空 global diff の hash を毎回作りません。
5. `cartographer` が対象領域を調べ、実装しない前提で地図と `implementation_strategy` 候補を返します。sage を使った場合は根拠を再確認し、採用、却下、未解決の disposition を sage synthesis に残します。
6. report にはevidence refs、重要な未確認事項、検証状況、snapshot参照を含めます。
7. 必要なら Root が別の `solo_quest`、`party_quest`、`safety_gate` として intake をやり直し、mapmaking の仮定を事実扱いせず新しい Charter へ handoff します。
8. 次 Quest の開始時に snapshot が変わっていた場合は `stale_evidence` とし、影響する地図と危険箇所を再確認します。

## 完了条件

- 実装前に判断できるだけの根拠がある
- 触るべきファイル、触らないファイル、未確認リスクが分かる
- 本質的な成果と、実装前に人間確認が必要な点が分かる
- 次に取るべき Quest Rank と Trial depth が明示されている
- `evidence_state`、根拠、必要なsage synthesis、snapshotが次のQuestへ渡せる

## 注意点

`mapmaking` は作業を止めるためではなく、不要な変更を避けるための段階です。
方針だけで十分ならそこで終了し、実装が必要なら別 Quest として境界を切り直します。
別 Quest では authority、boundaries、成功条件、snapshot を再発行し、古い report だけを根拠に実装へ進みません。
