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
- チームログを1つに保ったまま、下部の発言欄は常に使えるようにする
- 発言欄で `{appUser}として` ではなく `送信者 {appUser}` と表示
- `# チームルーム` と `# チャットルーム` をタブで切り替え
- チャットルーム側は吹き出し風に表示
- 同じプロジェクトパスに複数チームの `codex` がいる場合でも、
  Codex pane起動時の `/agmsg actas codex` 曖昧化を避ける
- 起動中のターミナルpaneを、メンバー名だけでなくチーム名込みで扱う
- パッチ版ビルドに、公式ベースcommit・パッチ数・パッチ列・ビルド時刻を
  `Info.plist` へ埋め込む

パッチごとの説明は [docs/patch-stack.md](docs/patch-stack.md) を参照してください。

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
scripts/update_agmsg_dev.sh --base app-v0.1.4 --install
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
