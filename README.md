# agmsg-ars

[AGMSG](https://github.com/fujibee/agmsg) デスクトップアプリに、日本語環境向けのUI改善と運用補助を当てるための非公式パッチキットです。

AGMSG本体をforkして丸ごと持つのではなく、公式ソースに対して小さな
パッチ列を順番に適用する方式にしています。公式が更新されたときは、
壊れたパッチだけを直して追従する想定です。

## 状態

これは非公式のパッチキットです。無保証で提供しています。ビルド前に
パッチ内容を確認し、既存のAGMSGアプリは必ずバックアップしてください。
公式AGMSGの変更により、パッチがそのまま当たらなくなることがあります。

## 何が変わるか

現在のパッチ列は、AGMSGデスクトップアプリの見た目とCodex連携の扱いを
中心に変更します。

- メッセージ時刻を日本時間で表示
- 白・グレー・ネイビー基調の明るいテーマ
- パッチ版アプリが公式アップデートで上書きされないようにする保護
- `# チームルーム` と `# チャットルーム` をタブで切り替え、両方の下に共通の発言窓を表示
- ユーザーチャットの履歴はチャットルーム内だけに表示し、ペイン下の常時表示を行わない
- 公式のdelivery-mode判定とPTY stdin注入を維持し、native monitorとの
  二重配送を避ける
- Codex paneはPATH上のmonitor shimを通さず、ChatGPT.app同梱CLIを
  AGMSG内のPTYで直接起動する
- `Codex` を `gpt-5.6-luna / max` で起動する
- AGMSGをCodexから起動した場合も、親Codexの制御用環境変数を子Codexへ
  継承させず、通常の対話TUIとして起動する
- CodexのTUIが起動時に行う端末状態・色・キーボード問い合わせへ、埋め込みPTYから応答する
- Codex paneのヘッダーから、Codex標準の`/model` pickerを開ける
- `team_agent_args=yes` を宣言した対話CLIをチーム名付きで起動し、任意の
  OpenAI互換ローカルLLMをチームごとのpaneとして使えるようにする
- 公式コアと同じ信頼リストを使い、`plugins/types` の外部typeをデスクトップ
  アプリの起動候補として扱う
- 起動中のターミナルpaneを、メンバー名だけでなくチーム名込みで扱う
- パッチ版ビルドに、公式ベースcommit・パッチ数・パッチ列・ビルド時刻を
  `Info.plist` へ埋め込む

### Codexペインのモデルを変更する

Codexペインを開き、ヘッダー右側のモデル選択アイコンを押します。Codex CLI標準の
`/model` pickerが開くので、そのペインで使うモデルと推論強度を選択できます。
パッチ側にモデル一覧や独自プリセットは持たず、インストール済みCodex CLIが提供する
選択肢をそのまま表示します。

パッチごとの説明は [docs/patch-stack.md](docs/patch-stack.md) を参照してください。

## ローカルLLM連携サンプル

`examples/agmsg_llm/` に、CodexからAGMSG経由でローカルLLMへ相談する
汎用サンプルを置いています。

- 単発レビュー向けのOpenAI互換API bridge
- AGMSG paneが開いている間だけ会話を保持する対話CLI
- 依頼を送り、返答を待ってターミナルへ表示するhelper
- 依頼と返答の相関IDを保ったまま、Markdown本文の余分な空行を抑える整形

Qwen + llama.cppで動作確認していますが、エージェント名、接続先、モデル名を
変更すれば、ほかのOpenAI互換ローカルLLMでも利用できます。詳しくは
[examples/agmsg_llm/README.md](examples/agmsg_llm/README.md) を参照してください。

## 必要なもの

- macOS
- Git
- 公式AGMSGのビルドに必要なNode / pnpm環境
- 公式AGMSGのビルドに必要なRust / Tauri環境

ビルドスクリプトは、デフォルトでは公式AGMSGを `.upstream/agmsg` にcloneします。
既存のcloneを使いたい場合は `AGMSG_REPO` を指定してください。

## ビルド

```bash
scripts/update_agmsg_dev.sh --fetch
```

生成されたアプリは、デフォルトでは `dist/` に保存されます。

`agmsg-dev.app` としてインストールする場合:

```bash
scripts/update_agmsg_dev.sh --fetch --install
```

デフォルトのインストール先:

```text
$HOME/Applications/agmsg-dev.app
```

パスを変える場合:

```bash
AGMSG_REPO=/path/to/agmsg \
AGMSG_APP_DEST="$HOME/Applications/agmsg-dev.app" \
scripts/update_agmsg_dev.sh --base app-v0.1.5 --install
```

## 公式更新への追従

1. 公式AGMSGの新しいソースをfetchまたはcloneします。
2. 新しいbase refに対してビルドします。

   ```bash
   scripts/update_agmsg_dev.sh --fetch --base origin/main
   ```

3. パッチが当たらなくなった場合は、全体をfork化せず、壊れたパッチだけを
   新しい公式ソースに合わせて作り直します。
4. パッチ列は小さく、番号順に保ちます。

## 公開repoに入れないもの

このrepoはpublicで使う前提です。以下は入れません。

- AGMSG DBやチーム状態
- APIキー
- persona / trainingファイル
- LaunchAgent
- ローカルbridge runtime
- チャットログ
- 特定マシンの絶対パス

## ライセンス

MIT。AGMSG本体もMITライセンスです。このrepoには、AGMSG本体ではなく
差分パッチとドキュメントだけを置いています。
