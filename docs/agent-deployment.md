# Agent deployment

Codexはギルド規約rootで起動し、作業repoを `<guild_root>/repositories/<repo>` に置きます。Rootは`target_repo_root`を固定し、top-level custom agentを直接起動します。

## Configuration

Root modelはSolに固定しますが、project-local reasoning effortは指定しません。起動時/UI/global configなどの利用者選択をそのまま使います。

```toml
model = "gpt-5.6-sol"
sandbox_mode = "read-only"
approval_policy = "on-request"

[sandbox_workspace_write]
network_access = true

[agents]
max_threads = 64
max_depth = 2
job_max_runtime_seconds = 1800
```

clean installと通常の再installはいずれもproject-local `model_reasoning_effort`を出力しません。導入先に旧指定があれば再install時に除去し、reasoning effortの選択はsession/global/user設定へ委ねます。installerやorchestrationはeffortを自動選択しません。

`workspace-write` agentの外部通信は有効です。外部通信を伴うコマンドも`approval_policy = "on-request"`と実行環境の承認境界に従います。

`inquisitor`だけが`features.multi_agent=true`で、risk-triggeredな単一focusを`examiner`へ委譲できます。その他のcustom agentは`features.multi_agent=false`のterminal workerです。`max_depth=2`と`max_threads=64`を設定し、policy上はRoot(depth 0)→Inquisitor(depth 1)→Examiner(depth 2)だけを許可します。role別`max_parallel`は`adventurer.max_parallel=32`、非adventurer合計16の計48とし、global 64との差16は特定roleの予約枠ではない未割当headroomとして残します。これらの値は同時実行の設定であり、総spawn数、token、costのhard capとは扱いません。

## Deployment role pairs

| agent | model | sandbox | reasoning | responsibility |
| --- | --- | --- | --- | --- |
| Root | `gpt-5.6-sol` | `read-only` | project-local未指定 | intake、境界、直接assignment、最終統合 |
| `adventurer` | `gpt-5.6-sol` | `workspace-write` | `high` | 一つのbounded scopeの実装と検証 |
| `artificer` | `gpt-5.6-sol` | `workspace-write` | `high` | 共有契約、cross-scope glue、統合検証 |
| `sage` | `gpt-5.6-sol` | `read-only` | `high` | 具体的な独立focusの助言 |
| `cartographer` | `gpt-5.6-sol` | `read-only` | `high` | read-only mapmaking |
| `courier` | `gpt-5.3-codex-spark` | `workspace-write` | `xhigh` | Ledgerと明示されたlocal Git操作 |
| `examiner` | `gpt-5.6-sol` | `read-only` | `high` | 単一focusのbounded review evidence |
| `guildmaster` | `gpt-5.6-sol` | `read-only` | `xhigh` | 複数Partyの広域戦略 |
| `inquisitor` | `gpt-5.6-sol` | `read-only` | `high` | Trial、finding統合、最終decision |
| `captain` | `gpt-5.6-sol` | `read-only` | `high` | scope、順序、integration、Trial設計 |
| `warden` | `gpt-5.6-sol` | `read-only` | `high` | 例外的な制御診断 |

現在の5.6 subagent deploymentは、live非劣性確認までSolを維持します。phase oneでは`adventurer`、`cartographer`、`examiner`、`warden`のTerra/highと、`sage`のLuna/highおよびTerra/highを同じhighで比較します。`artificer`と`captain`は今回の低コスト化対象外です。Courierは5.3-Spark/xhighを維持します。

subagentのreasoning effortはroleごとに固定し、実行中に動的変更しません。`guildmaster`は現行xhighとhigh、`inquisitor`は現行highとxhighをblind比較してから固定値を判断します。maxはroutine evalと全subagentから除外します。Rootの評価baselineはhighですが、runtime templateへはpinしません。

## Guild role naming

custom agentの機械IDは、責務を推測できる一語のGuild職へ統一します。

| retired ID | current ID | role boundary |
| --- | --- | --- |
| `party_leader` | `captain` | Partyのscope、順序、統合、Trial設計 |
| `integration_owner` | `artificer` | cross-scope契約、glue、統合検証 |
| `focus_reviewer` | `examiner` | Trialの単一focusに対する独立evidence |
| `advisor` | `sage` | owner判断を補う一論点のread-only助言 |
| `quest_sentinel` | `warden` | 通常制御で解消しない例外の診断 |

旧IDと新IDを同じruntimeで混在させません。通常installは旧agent fileを除去し、既存SQLite stateに旧worker ID、role、kindが残る場合はfail closedにします。必要なstateを保全したうえで`--backup --reset-runtime`または`--clean-install`を使ってください。

## Topology

```mermaid
flowchart TB
  root["Root\ncontract / direct assignment / synthesis"]
  plan["cartographer / captain / guildmaster\nread-only planning"]
  worker["adventurer\nbounded implementation"]
  integrate["artificer\nshared contract / glue / integration validation"]
  trial["inquisitor\nrisk-triggered Trial"]
  examiner["examiner\nterminal read-only focus"]
  sage["sage\nindependent read-only advice"]
  courier["courier\nLedger / explicit local Git"]

  root --> plan
  plan --> root
  root --> worker
  worker --> root
  root --> integrate
  integrate --> root
  root --> trial
  trial --> examiner
  examiner --> trial
  root --> sage
  sage --> root
  trial --> root
  root -.-> courier
```

Rootだけがtop-level agentを起動し、`captain`などはterminalです。唯一の例外として`inquisitor`が`examiner`を直接起動し、完了を待ってevidenceを検証・統合します。nested assignmentのscopeとauthorityは親より狭められますが、helper-issued subject snapshotは親Trialと完全一致させます。depth 2を超える再帰fan-outは禁止します。

## Integration

並列mutationでは次を必須にします。

1. 共通base snapshot
2. 重複しないowned scopeと共有artifactの単一owner
3. 各workerのowned-scope result
4. 全report後のmutation停止
5. `artificer`によるcross-scope glueと統合検証
6. integrated snapshotに対するTrial

`adventurer`へglobal integrationを兼務させません。

## Review roles

`sage`は具体的な独立focusがある時だけ使い、ownerがevidenceを確認します。`warden`は矛盾、反復失敗、scope drift、長時間停滞の例外時だけ使います。

`examiner.allowed_callers=[inquisitor]`はpolicy-onlyでありruntime ACLではありません。`event.actor`もidentity-backed caller証明ではありません。queueは実在TrialとのQuest/workflow/snapshot lineageを機械検証するだけで、actual spawn caller identityを証明しません。examinerはread-only terminal、inquisitorもread-onlyに固定し、write roleのchild起動は禁止します。approvalはassignment authorityを付与・拡張しません。examinerは必須ではなく、使う場合の1 Trialあたりpolicy capは3です。複数reviewerを使う時だけfocus分割を記録し、最終decisionは`inquisitor`が行います。

## Install

```bash
./scripts/install.sh --target /path/to/guild-root --mode copy
```

メジャー更新や旧構成を確実に片付ける場合:

```bash
./scripts/clean_install.sh --target /path/to/guild-root
```

既存導入を差分更新する場合:

```bash
./scripts/sync.sh --target /path/to/guild-root
```

source template内のsymlink、secret-like path、MCPなどの外部tool連携pathは拒否します。既存Ledgerの物理schemaが互換でない場合は自動migrationせず、backup/resetまたはclean installを使います。

## Validation

```bash
make validate
python3 scripts/model_selection_eval.py validate
python3 scripts/model_selection_eval.py plan
```

validatorは次を確認します。

- Root modelはSol、reasoning effortはproject-local未指定（評価baselineのhighとは分離）
- GuildmasterとInquisitorのSol high/xhigh比較、およびsubagent max禁止
- Courier Spark/xhighの維持
- inquisitorだけのnested capabilityと、その他custom agentのterminal設定
- `max_threads=64`、`max_depth=2`
- 全10 roleの`max_parallel`合計48、非adventurer合計16、`adventurer.max_parallel=32`、未割当headroom 16
- compact promptの行数と旧制約の不在
- target/secret/state-change/snapshot/lineageのfail-closed
- prompt profile、role topology、model/effortを分離した評価契約
- end-to-end final outcome hard gate

live model比較は外部送信許可とreview済みwrapper/profileがある場合だけ実行します。component scoreだけでproduction最適化を断定しません。
