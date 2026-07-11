# パッチ列

このパッチ列を切り出した時点の主な対象base:

```text
app-v0.1.4
```

パッチは `patches/agmsg-dev/` にある `.patch` ファイルを、ファイル名の昇順で
適用します。

## パッチ一覧

- `0001-display-message-times-in-jst.patch`
  - デスクトップアプリのメッセージ時刻を日本時間で表示します。
- `0002-light-navy-theme.patch`
  - 暗色テーマを、白・グレー・ネイビー基調の明るいテーマに変えます。
- `0003-disable-dev-auto-updater.patch`
  - パッチ版devビルドが公式アップデートで自動上書きされないようにします。
- `0004-keep-composer-independent.patch`
  - app-user履歴を隠しても、下部の発言欄は使えるようにします。
- `0005-use-type-command-prefix-for-spawn.patch`
  - agent typeごとのAGMSGコマンドprefixを尊重します。
- `0006-timeout-delivery-mode-status.patch`
  - delivery-mode確認が遅い場合に、pane起動を長く止めないようにします。
- `0007-hide-app-user-history-by-default.patch`
  - 重複して見えるapp-user履歴をデフォルトで隠します。
- `0008-do-not-probe-delivery-mode-before-spawn.patch`
  - pane起動前に同期的なdelivery-mode確認をしないようにします。
- `0009-japanese-composer-sender-label.patch`
  - 発言欄の日本語を `送信者` 表記にします。
- `0010-inject-codex-actas-after-pty-start.patch`
  - Codex起動後にactasを入れる実験的変更です。後続パッチとの履歴整合のため
    残しています。
- `0011-bypass-codex-monitor-shim-in-pty-pane.patch`
  - app paneからCodexを起動するとき、PATH shimではなくChatGPT.app同梱の
    Codex CLIを起動します。AGMSG側のtype manifestが古いCodex.appパスを返す
    場合も、このパッチで吸収します。
- `0012-inject-codex-agmsg-command-on-message.patch`
  - Codex pane宛にAGMSGメッセージが来たとき、`inbox.sh` / `send.sh` を使う
    短い指示を注入します。
- `0013-do-not-inject-codex-actas-on-startup.patch`
  - Codex pane起動時の `actas` 注入を止めます。
- `0014-split-team-and-chat-room-tabs.patch`
  - `# チームルーム` と `# チャットルーム` をタブ化し、チャット側を吹き出し表示にします。
- `0015-show-dev-build-provenance.patch`
  - 公式baseとローカルパッチ情報をdevビルドに埋め込み、表示できるようにします。
- `0016-match-official-codex-spawn-command.patch`
  - Codex起動コマンドの形を公式アプリ側に寄せます。
- `0017-scope-running-panes-by-team.patch`
  - 起動中paneをメンバー名だけでなくチーム名込みで識別します。
- `0018-start-codex-pane-without-actas.patch`
  - Codex paneは `actas` なしで起動し、AGMSG受信時のチーム付き指示で処理します。
- `0019-launch-codex-sol-with-sol-model.patch`
  - `Codex` を `gpt-5.6-sol / low`、`Codex-Sol` を
    `gpt-5.6-sol / xhigh` で起動します。AGMSG以外のCodex設定には影響しません。
- `0020-launch-llm-cli-with-team.patch`
  - `local-llm-cli` を起動するとき、対象チーム名とエージェント名を引数で
    渡します。これにより、ローカルLLMの対話CLI paneがどのチームへ返信するかを
    確定できます。

## パッチを更新する手順

公式AGMSGの変更でパッチが衝突した場合:

1. 公式baseを一時worktreeへcheckoutします。
2. 失敗する直前までのパッチを適用します。
3. 失敗したパッチだけを、新しい公式ソースに合わせて作り直します。
4. 意図が同じならファイル番号は維持します。
