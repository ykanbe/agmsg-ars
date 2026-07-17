# パッチ列

このパッチ列を切り出した時点の主な対象base:

```text
app-v0.2.0
```

パッチは `patches/agmsg-dev/` にある `.patch` ファイルを、ファイル名の昇順で
適用します。

## パッチ一覧

- `0002-light-navy-theme.patch`
  - 暗色テーマを、白・グレー・ネイビー基調の明るいテーマに変えます。
- `0003-disable-dev-auto-updater.patch`
  - パッチ版devビルドが公式アップデートで自動上書きされないようにします。
- `0005-use-type-command-prefix-for-spawn.patch`
  - agent typeごとのAGMSGコマンドprefixを、起動時のactasと受信時のkickoffで
    尊重します。
- `0011-bypass-codex-monitor-shim-in-pty-pane.patch`
  - 組み込みtypeの `cli=codex` を起動するときはmonitor shimを環境変数で
    無効化します。信頼済みtype pluginが絶対パスを指定する場合は、そのCLIを
    アプリ内PTYで直接起動します。配送は公式のPTY注入経路を使います。
- `0014-split-team-and-chat-room-tabs.patch`
  - チームルームとチャットルームを固定タブに分け、発言窓を選択中の画面の
    下に配置します。ユーザーチャット履歴はチャットルーム内だけに表示し、
    ターミナルpane下の常設チャット・最小化・最大化UIは使いません。
- `0015-show-dev-build-provenance.patch`
  - 公式baseとローカルパッチ情報をdevビルドに埋め込み、表示できるようにします。
- `0017-scope-running-panes-by-team.patch`
  - 起動中paneをメンバー名だけでなくチーム名込みで識別します。
- `0020-launch-llm-cli-with-team.patch`
  - type manifestで `team_agent_args=yes` を宣言したCLIへ、対象チーム名と
    エージェント名を引数で渡します。これにより、ローカルLLMの対話CLI paneが
    どのチームへ返信するかを確定できます。受信時はCLIが解釈できるチーム付き
    イベントを、公式のPTY注入経路で渡します。
- `0021-sanitize-codex-session-env.patch`
  - AGMSG自体をCodexから起動した場合でも、子Codexへ親タスクの
    `CODEX_CI` / `CODEX_THREAD_ID` などを継承させません。通常の
    `CODEX_HOME` は維持し、対話TUIとして起動できるようにします。
- `0022-answer-terminal-status-queries.patch`
  - xterm.jsに届いたCodexの端末状態・色・Kittyキーボード問い合わせへPTY経由で
    応答し、TUIが初期化途中で停止しないようにします。
- `0023-open-codex-model-picker.patch`
  - `codex` paneのヘッダーにlucideアイコンのボタンを追加し、Codex標準の
    `/model` pickerをPTY経由で開きます。独自のモデルプリセットは追加しません。
- `0024-discover-trusted-type-plugins.patch`
  - 公式コアのtype registryと同じ優先順で、組み込みtype、`plugins/types`、
    `AGMSG_PLUGIN_DIRS` を列挙します。外部typeは `trusted-plugins` に登録された
    パスだけを起動候補にし、後順位の信頼済みプラグインによる上書きを認めます。

## 適用対象から外した旧パッチ

公式 `app-v0.2.0` に同等の機能が入ったものと、今回の運用では不要と判断したものは
適用対象から外し、内容だけ `patches/agmsg-dev/retired/` に保存しています。

- `0001-display-message-times-in-jst.patch`
  - 0.2.0でOSタイムゾーン自動検出と手動設定が公式実装されました。
- `0004-keep-composer-independent.patch`
- `0006-timeout-delivery-mode-status.patch`
- `0007-hide-app-user-history-by-default.patch`
- `0008-do-not-probe-delivery-mode-before-spawn.patch`
- `0009-japanese-composer-sender-label.patch`
- `0010-inject-codex-actas-after-pty-start.patch`
- `0012-inject-codex-agmsg-command-on-message.patch`
- `0013-do-not-inject-codex-actas-on-startup.patch`
- `0016-match-official-codex-spawn-command.patch`
- `0018-start-codex-pane-without-actas.patch`
- `0019-launch-codex-with-luna-model.patch`
- `0019-launch-codex-sol-with-sol-model.patch`

配送経路を変更していた旧パッチは、公式 `app-v0.2.0` の
`delivery-mode判定 → 非native paneへのPTY注入` に戻すため退役しました。
CodexはPATH上のmonitor shimを避け、CLI実体はAGMSGの信頼済みtype manifestを
優先して選びます。

## パッチを更新する手順

公式AGMSGの変更でパッチが衝突した場合:

1. 公式baseを一時worktreeへcheckoutします。
2. 失敗する直前までのパッチを適用します。
3. 失敗したパッチだけを、新しい公式ソースに合わせて作り直します。
4. 意図が同じならファイル番号は維持します。
