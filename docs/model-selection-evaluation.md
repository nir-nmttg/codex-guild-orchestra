# GPT-5.6 role model selection

この文書は、Codex Guild Orchestra の各 role に固定する model と reasoning effort の選定根拠を記録します。
以前の割り当てを正解として扱わず、role contract、失敗時の波及、並列頻度、ユースケース契約、代表 stress case を選定根拠にします。

## 前提

- 評価日: 2026-07-10
- Codex CLI: `0.144.0-alpha.4`
- model catalog:
  - `gpt-5.6-sol`: frontier agentic coding model
  - `gpt-5.6-terra`: balanced everyday agentic coding model
  - `gpt-5.6-luna`: fast and affordable agentic coding model
  - `gpt-5.3-codex-spark`: ultra-fast coding model
- 5.6 系は `low / medium / high / xhigh / max` を利用でき、Sol / Terra は `ultra` も利用できます。
- `ultra` は自動委譲が明示 assignment と terminal worker 契約に干渉し得るため候補から除外しました。
- `courier` はユーザー指定により `gpt-5.3-codex-spark / xhigh` を維持し、model 選定の対象外としました。

公式の [GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model) と [Codex Subagents guidance](https://developers.openai.com/codex/subagents/) に従い、曖昧で多段の planning、tool use、validation、最終 decision を伴う role は高能力側、read-heavy で bounded な supporting work は Terra、高頻度で owner が再検証する狭い work は Luna を候補にしました。
同じ role で task 難度に応じて effort を動的変更せず、認知負荷と decision authority が異なる場合は role contract を分離して、それぞれに固定 pair を与えます。

## 評価方法

評価は3層に分けます。

1. `scripts/validation/fixtures/golden_quests/` で authority、revision binding、handoff、safety、terminal worker 契約を決定論的 hard gate として検証する。
2. `scripts/model_selection_eval.yaml` で role ごとの legacy regression control、5.6 same-effort、選定 pair、一段下、通常 / edge / safety fixture、required evidence、品質 / 効率指標を固定する。各 case は deterministic golden fixture に対応付ける。
3. `scripts/model_selection_eval.py` で template の実 role contractを一時 `AGENTS.md` layerへ埋め込み、role componentをfresh ephemeral sessionで反復比較する。candidateには grader labelを見せず、grading artifactとmodel provenanceを別directoryに分ける。

live runner は model / effort 差を分離するため `multi_agent=false` にし、単一 role component の出力とtool挙動を測ります。実際のsubagent fan-out、caller chain、handoff、integrationはlive runnerが再現したと主張せず、queue schema、golden fixtures、installer mutation smokeで決定論的に検証します。将来end-to-end workflow evalを追加する場合も、component scoreと混ぜず別suiteにします。

通常の `make validate` は外部 model を呼ばず、golden Quest と eval manifest の整合だけを検証します。
live eval は明示実行に分け、出力、usage、elapsed time、worktree / staged / commit diff、commit log、grader worksheet を既定で `/tmp/codex-guild-model-eval` に保存します。
live eval は role 指示と synthetic fixture を外部 model service へ送るため、実行環境のdata policyを確認し、明示的に許可された場合だけ起動します。acknowledgementだけでは起動せず、評価用work directory以外を読み書きできない隔離VM / container wrapperと、そのwrapper hashに結び付いたattestationも必須です。さらにreview済みwrapperのSHA-256を `run_policy.approved_isolation_wrapper_sha256`、canonical attestationのSHA-256を `run_policy.approved_isolation_profile_sha256` へ登録しなければ起動しません。既定値はどちらも空listで、未review wrapper / profileをfail closedにします。

wrapper reviewでは、単なるpass-throughでないこと、hostのhome、repository、credential store、secret mountを隔離環境へ公開しないこと、OpenAI model service以外へ接続できないことを確認します。wrapperは一つのself-contained executableにし、子をdaemonize / 別session化せず `exec` または同じprocess groupで管理し、認証情報は評価専用の方法でwrapper側から注入してください。runnerは承認済み実体をsession provenanceへ固定し、各runの前後にhashを再確認します。timeout時はwrapperを含むprocess group全体をkillしてwaitし、子が残った状態でpostprocessやworkdir削除へ進みません。

```bash
python3 scripts/model_selection_eval.py validate
python3 scripts/model_selection_eval.py plan
python3 scripts/model_selection_eval.py run \
  --role focus_reviewer \
  --acknowledge-external-data-send \
  --execution-wrapper /path/to/isolated-eval-wrapper \
  --isolation-attestation /path/to/isolation-attestation.json
# provenanceへアクセスできないgrader用packageを別access boundaryへ出力
python3 scripts/model_selection_eval.py export-grading \
  --session-dir /tmp/codex-guild-model-eval/session-... \
  --output-dir /path/visible-to-grader/focus-reviewer-grading
# package内のgrader.jsonを埋め、grader.jsonだけをcontrolled copyで元sessionへ戻した後
python3 scripts/model_selection_eval.py summarize --session-dir /tmp/codex-guild-model-eval/session-...
# current pricingを別管理する場合
python3 scripts/model_selection_eval.py summarize --session-dir /tmp/codex-guild-model-eval/session-... --price-table /path/to/model-prices.json
```

wrapper interfaceは `isolated-eval-wrapper -- <command> ...` です。runnerはhost環境を引き継がず、固定した最小 `PATH`、work directory内の `TMPDIR`、`CGO_EVAL_WORKDIR` / `CGO_EVAL_GUILD_ROOT` だけを渡します。TLS trustと評価専用認証はreview済みwrapper / image側で用意します。Codex本体だけでなく、候補が変更できるGit metadataを読むpostprocessも同じwrapper内で実行し、external diff、textconv、fsmonitor、host Git configを無効化し、timeoutを設けます。wrapperは実行対象をそのwork directoryへ閉じ込め、network destinationをOpenAI model serviceだけに制限する責任を持ちます。

wrapperは `--cgo-timeout-cleanup-probe <marker-path>` も実装します。このmodeはguest/container内で親process groupからdetachした子を起動し、2秒後にmarkerを書こうとしたままblockします。runnerは1秒でwrapper groupを停止し、さらに2.5秒後もmarkerが存在しないことをlive session開始前に確認します。早期returnまたはmarker生成のどちらでもsessionを拒否し、probe evidenceをprivate provenanceへ記録します。

attestationは次の完全一致schemaです。`wrapper_sha256`だけでなくimmutable image digest、実際にreviewしたnetwork policyとcredential profileのID、issuerをapproval単位へ含めます。runnerが技術的にクラウド側policyを証明するものではないため、summaryの保証水準は `operator_attested_reviewed_wrapper_and_profile` と明示されます。

```json
{
  "version": 1,
  "filesystem_read_scope": "eval_workdir_only",
  "filesystem_write_scope": "eval_workdir_only",
  "environment_mode": "allowlist",
  "host_secret_mounts": false,
  "network_destination": "openai_model_service_only",
  "wrapper_sha256": "<64-character SHA-256>",
  "runtime_image_digest": "sha256:<64-character SHA-256>",
  "network_policy_id": "<reviewed immutable policy ID>",
  "credential_profile_id": "<evaluation-only credential profile ID>",
  "attestation_issuer": "<責任を持つoperatorまたはcontrol-planeのID>",
  "process_model": "same_process_group_no_daemonization",
  "timeout_cleanup_protocol": "cgo-detached-child-probe-v1"
}
```

runnerはworkspace全体をcopyせず、対象roleの `AGENTS.md`、settings、common / role instructions、agent configだけを一時guildへ複製します。manifestはreview済み `synthetic_only` data policyを必須にし、prompt、baseline / working fileの既知secret / PII indicator（path、credential、email、SSN、電話、card-like number）を送信前に拒否します。pattern検査は未知形式の完全検出を保証しないため、実在人物・実credentialをfixture sourceに使わないhuman reviewも省略しません。実行前後にはtarget repository外の一時guild全体をsymlink非追従で比較し、変更があれば自動的に `target_repo_escape` hard gate違反とします。

graderはexport済みpackageだけを見て、各 `grader.json` の `grader_id`、timezone付き `graded_at`、`blindness_attestation=true`、全rubricを埋めます。export manifestと各grader attestationはgrader入力bundleの同じSHA-256を持ち、summary時の入力bundleと一致しなければ集計を拒否します。summaryは入力と採点後artifactの両bundle SHA-256を記録します。session隣接の `provenance/` をgraderへ公開した場合、blindness attestationをtrueにしてはいけません。

公式 guidance に合わせ、migration前の5.5と同じ effortの5.6候補から始め、選定 pair と同modelの一段下を必ず候補にします。旧Rootだけは5.5 effortが継承値だったため、比較controlを`high`へ正規化し、その仮定をmanifestに記録します。`xhigh` の `guildmaster` は `high / xhigh / max` を比較対象にします。
通常caseは3回、安全caseは5回を既定にし、一つの失敗で後続候補を打ち切りません。hard gate 違反と Critical 見逃しは0件を要求します。pilotの探索的非劣性は全case平均で相殺せず、caseごとに判定します。safety caseはmargin 0で少数標本用t値によるlower boundを要求し、Root / Guildmaster / Inquisitorのquality-first roleはnormal caseも同じlower boundを使います。全caseを通ったpairだけtokens、elapsed time、計算可能ならcostを比較します。ただし少数標本、同じdataからのbest選択、多重比較を補正したconfirmatory designではないため、このlower boundをformalな95%保証とは呼びません。

cross-model costはtoken数だけから推定しません。price tableの各modelは `input_per_million`、`cached_input_per_million`、`output_per_million` を持たせ、usage側にも `input_tokens`、`cached_input_tokens`、`output_tokens` が揃った場合だけcost推薦を有効にします。summaryの `recommendation_basis` は実際のnoninferior候補集合でcostを使ったかを記録し、cached input内訳がない集計はtokens / elapsedのefficiency proxyとして扱います。

## 既存 smoke evidence と現在の評価状態

現在の固定マトリクスは、role authority、blast radius、並列頻度、`docs/use-cases`の契約と、次表のlegacy representative smokeを根拠にした**設計上の選定**です。統計的に最適と実証済みという意味ではありません。次表は現行 runner のblind artifact / provenance形式より前の観測なので、再現可能な集計結果として扱いません。

今回の最終確認では外部model送信と隔離実行の明示条件が揃っていないため、新runnerのlive比較は実行していません。manifestのwrapper / profile allowlistも意図的に空のため、現状のcheckoutからlive runは起動できません。review済み実行基盤と外部送信許可が揃った時だけ、双方のcanonical SHA-256を同時に登録します。`synthetic_pilot`は全candidate / case / repetition、全hard gate、blind grading、隔離provenanceが揃っても `pilot_recommendation` までに限定し、`formal_recommendation_available` はfalseのままです。formal選定には、事前登録したreference pair、power / sample size、multiple-comparison補正を持つconfirmatory suiteを別途追加します。その後もproductionで「最適」と断定する前に、履歴由来case、長時間workflow、adversarial prompt、end-to-end subagent fan-outを別suiteで確認します。component pilotのscoreだけでworkflow全体の最適性を主張しません。

| role | 比較 | 観測結果 | 選定への反映 |
| --- | --- | --- | --- |
| Root | Sol `high` / `xhigh` | どちらも未確定 repository と deployment approval を停止できた。`high` は target を推測せず assignment も作らず、`xhigh` は両 repository の調査 assignment を追加した | 全依頼を通る Root は Sol / `high` に固定 |
| cartographer | Terra `high` | token rotation の互換 rollout、nullable migration、並行 refresh、rollback、observability を危険地帯として整理できた | read-heavy mapmaking は Terra / `high` で品質下限を満たす |
| party_leader | Terra `high` / Sol `high` | Terra は migration file の owner を落とした。Sol は全 file を2担当へ非重複で割り当て、sequencing と security / rollback Trial を維持した | assignment の波及を重視して Sol / `high` |
| adventurer | Terra `high` / Sol `high` | どちらも transactional outbox、idempotent retry、observability、focused tests を提示した | 上流で scope が限定され最大5並列のため Terra / `high` |
| inquisitor | Terra `high` / Sol `high` | どちらも authorization 前 write を Critical、full token logging を重大 finding として reject した。Sol は同じ hard gate を短く満たした | 最終採否と重大度統合の誤りの波及を重視して Sol / `high` |
| focus_reviewer | bounded contract と Inquisitor 比較結果 | 単一 focus の evidence 収集では Terra `high` も security hard gate を満たした。最終採否、重大度、synthesis は `inquisitor` に残す | `focus_reviewer` を Terra / `high` へ分離し、並列 Sol 常用を避ける |
| advisor | Luna `high` / Terra `high` | どちらも populated table への NOT NULL 追加、deploy / backfill 順、locking risk を検出した。Luna は focus と unknowns を保ったまま簡潔だった | owner 再検証を前提に Luna / `high` |
| quest_sentinel | Luna `medium` / `high` | confidence 92 の scope-drift case で `medium` は誤った `confidence_below_75` trigger を追加し、`high` は security-sensitive scope drift だけを扱った | Luna / `high` に固定 |

`guildmaster` は guild-scale の Party 境界、sequencing、safety gate に限定される低頻度 role で、失敗時の blast radius が最大です。
このため現行 deployment は Sol / `xhigh` を維持します。`max` は candidate manifest に含めますが、blind反復評価で `xhigh` への測定済み品質向上が確認されるまで固定採用しません。

## Role 分離による最適化

従来の `inquisitor` は Trial lead / integrator と最大3並列の narrow reviewer を同じ Sol / `high` で兼務していました。
最終 decision の責務と bounded evidence 収集の責務が異なるため、次の固定 role に分離します。

- `inquisitor`: Sol / `high`。Trial 設計、reviewer count、report 根拠確認、重大度、finding disposition、requested changes、最終 decision を所有する。
- `focus_reviewer`: Terra / `high`。`inquisitor` から割り当てられた単一 focus の read-only evidence だけを返し、採否、重大度、synthesis、追加 subagent を持たない。

この分離は高い判断品質を Sol に残しながら、`multi_focus_trial` / `safety_gate` で並列 reviewer 全員を Sol にする乗算コストを避けます。

## 固定マトリクス

| role | model | reasoning effort |
| --- | --- | --- |
| Root | `gpt-5.6-sol` | `high` |
| `adventurer` | `gpt-5.6-terra` | `high` |
| `advisor` | `gpt-5.6-luna` | `high` |
| `cartographer` | `gpt-5.6-terra` | `high` |
| `courier` | `gpt-5.3-codex-spark` | `xhigh` |
| `focus_reviewer` | `gpt-5.6-terra` | `high` |
| `guildmaster` | `gpt-5.6-sol` | `xhigh` |
| `inquisitor` | `gpt-5.6-sol` | `high` |
| `party_leader` | `gpt-5.6-sol` | `high` |
| `quest_sentinel` | `gpt-5.6-luna` | `high` |

Root と全 subagent はこの値を固定し、Quest の難度による動的な reasoning effort 切り替えは行いません。
model catalog、role contract、authority、並列数、ユースケース、または eval の失敗傾向が変わった場合は、golden Quest、candidate manifest、この固定マトリクスを同時に再評価します。
