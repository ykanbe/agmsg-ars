# agmsg-ars

普段の作業と判断はChatGPT/Codex.appを中心に行い、軽いレビュー、翻訳、
文章整理などはローカルLLMへ任せられます。
[AGMSG](https://github.com/fujibee/agmsg)を、そのやり取りをつなぎ、確認する
モニターとして使うための非公式パッチキットです。

ChatGPTアプリの機能をそのまま使いながらトークン消費を抑え、LLM同士の
依頼と返答をAGMSG上で確認できます。また、公式AGMSGと同じように、AGMSGを
中心にCLI型エージェント同士をつなぐ使い方もできます。
日本語環境向けのUI改善と、この運用に必要なCodex・ローカルLLM連携を加えています。

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

- 白・グレー・ネイビー基調の明るいテーマ
- パッチ版アプリが公式アップデートで上書きされないようにする保護
- `# チームルーム` と `# チャットルーム` を固定タブで切り替え、どちらにも
  共通の発言窓を表示。ターミナルpane下の常設チャットは表示しない
- Codex paneはPATH上のmonitor shimを無効化し、信頼済みtype pluginが指定した
  Codex CLIをAGMSG内のPTYで直接起動する
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
- Codex paneを使う場合はCodex CLI
- 公式AGMSGのビルドに必要なNode / pnpm環境
- 公式AGMSGのビルドに必要なRust / Tauri環境

ビルドスクリプトは、デフォルトでは公式AGMSGを `.upstream/agmsg` にcloneします。
既存のcloneを使いたい場合は `AGMSG_REPO` を指定してください。

## ビルド

```bash
scripts/update_agmsg_dev.sh --fetch --base app-v0.2.0
```

`app-v0.2.0` は現在のパッチ列で動作確認済みの公式baseです。

生成されたアプリは、デフォルトでは `dist/` に保存されます。

`agmsg-dev.app` としてインストールする場合:

```bash
scripts/update_agmsg_dev.sh --fetch --base app-v0.2.0 --install
```

デフォルトのインストール先:

```text
$HOME/Applications/agmsg-dev.app
```

パスを変える場合:

```bash
AGMSG_REPO=/path/to/agmsg \
AGMSG_APP_DEST="$HOME/Applications/agmsg-dev.app" \
scripts/update_agmsg_dev.sh --base app-v0.2.0 --install
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
