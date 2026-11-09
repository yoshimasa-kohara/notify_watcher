# 通知監視(notify_watcher)

AI(Claude など)に時間のかかる作業を任せている間、ほかのことをしていても、終わったときや確認が必要なときに音で知らせてくれる Windows 用の便利ツール。

AI に調査・設計・コードの修正などを頼むと、返事が出るまで数分〜数十分かかることがある。
その間に別の作業をしていると、終わったことに気づかずに時間を無駄にしたり、
「コマンドを実行してよいか」の許可を待たせたまま止めてしまったりする。
このツールを常駐させておき、AI への指示に「終わったらファイルを置いて」と書いておくだけで、
画面を見張らなくても音で気づけるようになる。

しくみは単純で、`call` フォルダにファイルが置かれたら通知音を鳴らし、鳴り終わったらそのファイルを削除する。
ファイルを置くだけでよいので、AI だけでなく、ほかのプログラムやバッチの「処理が終わった」「確認してほしい」の通知にも使える。

- ファイルを1つ置くだけで鳴らせるので、どんな言語・ツールからでも使える
- ファイル名で音を鳴らし分ける(`確認` / `完了` / それ以外)
- 音量は設定ファイルで変えられる。保存すれば再起動なしで反映される
- Python の標準ライブラリだけで動く。追加のインストールは不要

## 動く環境

- Windows 10 / 11
- Python 3.11 以上(設定ファイルの読み込みに標準ライブラリの `tomllib` を使うため)

mp3 の再生に Windows の MCI(エムシーアイ)という機能を使っているので、Windows 以外では動かない。

## フォルダの構成

置く場所はどこでもよい。以下の説明では `C:\tools\notify_watcher` に置いたものとして書く。

```
C:\tools\notify_watcher\
├─ notify_watcher.py   … 監視プログラム本体
├─ notify_watcher.toml … 設定ファイル(音量)
├─ README.md           … この説明
├─ LICENSE             … ライセンス
├─ call\               … 通知したいときに、ここにファイルを置く
│   └─ .gitkeep        … Git で空フォルダを残すためのもの(プログラムは無視する)
├─ 通知音\
│   ├─ 確認.mp3
│   ├─ 完了.mp3
│   └─ 通知.mp3
├─ logs\               … ログ(自動で作られる)
└─ 通知OFF             … 音を止めたいときだけ手で置く(普段はない)
```

## 使い方

### 通知を鳴らす

`call` フォルダにファイルを置く。ファイルの中身は空でよい。

| 置くファイルの名前 | 鳴る音 |
|---|---|
| `確認` | `通知音\確認.mp3` |
| `完了` | `通知音\完了.mp3` |
| 上記以外 | `通知音\通知.mp3` |

- 「確認.txt」のように拡張子がついていても、「確認」と同じ扱いになる
- 鳴り終わったら、置いたファイルは自動で削除される
- 複数置いた場合は、置いた順に1つずつ鳴る
- `call` フォルダは1秒おきに確認しているので、置いてから鳴るまで最大で1〜2秒かかる

ほかのプログラムから鳴らす例:

```bat
rem バッチファイル(.bat)から
type nul > "C:\tools\notify_watcher\call\完了"
```

```powershell
# PowerShell から
New-Item -ItemType File "C:\tools\notify_watcher\call\確認"
```

```python
# Python から
from pathlib import Path
Path(r"C:\tools\notify_watcher\call\完了").touch()
```

AI エージェントに使わせる場合は、指示文(Claude のプロジェクトの指示や `CLAUDE.md` など)に次のように書いておく。

```
作業が終わったら C:\tools\notify_watcher\call\完了 に空のファイルを置いてください。
私の確認や許可が必要なときは C:\tools\notify_watcher\call\確認 に空のファイルを置いてください。
```

### 音を止める(通知OFF)

`notify_watcher.py` と同じフォルダに `通知OFF` という名前のファイルを置く。

- 置いている間は音が鳴らない。`call` に置かれたファイルは、これまでどおり削除される
- 音を戻すときは、`通知OFF` ファイルを手で削除する。プログラムは `通知OFF` を削除しない
- 「通知OFF.txt」のように拡張子がついていてもよい(エクスプローラーの「新規作成 → テキスト ドキュメント」で作れる)
- プログラムの再起動は不要

### 通知音を変える

`通知音` フォルダの mp3 ファイルを、同じ名前のファイルで差し替える。
ファイル名を変える場合や鳴らし分けを増やす場合は、`notify_watcher.py` の `SOUND_MAP` を直してから、
プログラムを再起動する(後述の「止める・起動し直す」)。

### 音量を変える(設定ファイル)

`notify_watcher.toml` をメモ帳などで開き、数値を書き換えて保存する。
**保存すると次の通知から反映される。プログラムの再起動はいらない。**

```toml
# 全部の通知音の音量(0〜100)
"音量" = 70

# 音ごとの音量(0〜100)。書いていない音は上の「音量」になる
["音ごとの音量"]
"確認" = 100
"完了" = 40
```

- 音量は 0〜100 で書く。Windows の音量を上限とした大きさになる(Windows の音量が 30 で「音量」が 50 なら、30 の半分くらい)。Windows の音量そのものは変えない
- `["音ごとの音量"]` のキーは、`通知音` フォルダの mp3 のファイル名(拡張子なし)
- **日本語の項目名は `"音量"` のように `"` で囲む**(TOML という書式の決まり)
- 行の先頭に `#` をつけると、その行は無視される(メモ書きに使える)
- 0〜100 の範囲外の数は、0 か 100 に丸める(ログに警告が出る)
- 書き間違いで読めないときや、ファイルがないときは、ログに警告を出し、最後に正しく読めた設定で鳴らす。
  一度も読めていなければ音量 100 で鳴らす。書き間違いで通知が止まることはない
- 設定を変えたあと、最初の通知のときに「設定を読み込みました」とログに出る

## 常駐させる(タスクスケジューラへの登録)

Windows にログオンしたときに自動で起動するよう、タスクスケジューラに登録する。
画面に黒いウィンドウが出ないように、`python.exe` ではなく `pythonw.exe` で起動する。

### 登録する

PowerShell を開いて、次のコマンドを実行する(管理者として実行する必要はない)。
1行目の `$dir` は、このプログラムを置いたフォルダに書き換える。

```powershell
$dir = "C:\tools\notify_watcher"
$pyw = python -c "import sys, pathlib; print(pathlib.Path(sys.executable).with_name('pythonw.exe'))"
$action = New-ScheduledTaskAction -Execute $pyw -Argument "`"$dir\notify_watcher.py`"" -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "通知監視" -Action $action -Trigger $trigger -Settings $settings
```

設定の意味:

| 設定 | 意味 |
|---|---|
| `$pyw = python -c ...` | 使っている Python の `pythonw.exe` の場所(実体のパス)を調べる |
| `-AtLogOn -User ...` | このユーザーがログオンしたときに起動する。ログオン中のユーザーとして動くので、音が鳴る |
| `-ExecutionTimeLimit 0` | 実行時間の上限をなくす(既定では3日で止められてしまう) |
| `-RestartCount 3 -RestartInterval 1分` | 異常終了したら、1分おきに3回まで起動し直す |
| `-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries` | ノートPCでバッテリー駆動のときも動かす |

> **注意:ユーザー名は「コンピューター名\ユーザー名」の形で指定する**
>
> `-User $env:USERNAME`(ユーザー名だけ)で登録すると、コンピューター名とユーザー名が同じPCでは次のエラーになることがある。
>
> ```
> Register-ScheduledTask : パラメーターが間違っています。
> ```
>
> 名前だけではどちらを指しているか決まらないためと思われる。
> `"$env:USERDOMAIN\$env:USERNAME"` と書けば登録できる。

> **注意:`pythonw.exe` のパス**
>
> `C:\Users\<ユーザー名>\AppData\Local\Microsoft\WindowsApps\pythonw.exe` は Python インストールマネージャーやストア版の入口(エイリアス)なので、
> タスクには実体のパスを指定する。上の `$pyw` の行は、その実体のパスを調べている。
> Python のバージョンを上げてパスが変わった場合は、登録を消してから登録し直す。

### 登録後すぐに起動する

登録しただけでは、次のログオンまで起動しない。すぐに動かすときは次を実行する。

```powershell
Start-ScheduledTask -TaskName "通知監視"
```

### 動いているか確認する

```powershell
Get-ScheduledTask -TaskName "通知監視" | Select-Object TaskName, State
```

`State` が `Running` なら動いている。あわせて `logs\notify_watcher.log` に「監視を開始します」と出ているかを見る。

### 止める・起動し直す

`notify_watcher.py` を書き換えたときは、起動し直さないと反映されない。

```powershell
# 止める
Stop-ScheduledTask -TaskName "通知監視"

# 起動し直す
Stop-ScheduledTask -TaskName "通知監視"; Start-ScheduledTask -TaskName "通知監視"
```

### 登録を消す

```powershell
Unregister-ScheduledTask -TaskName "通知監視" -Confirm:$false
```

### 画面から登録する場合

1. タスクスケジューラを開き、「タスクの作成」を選ぶ
2. 「全般」タブ:名前を `通知監視` にし、「ユーザーがログオンしているときのみ実行する」を選ぶ
3. 「トリガー」タブ:「新規」→「タスクの開始」を「ログオン時」、「特定のユーザー」を自分にする
4. 「操作」タブ:「新規」→「プログラムの開始」
   - プログラム:`pythonw.exe` の実体のパス(PowerShell で `python -c "import sys; print(sys.executable)"` を実行し、表示された `python.exe` を `pythonw.exe` に読み替える)
   - 引数の追加:`"C:\tools\notify_watcher\notify_watcher.py"`
   - 開始:`C:\tools\notify_watcher`
5. 「条件」タブ:「コンピューターを AC 電源で使用している場合のみタスクを開始する」のチェックを外す
6. 「設定」タブ:「タスクを停止するまでの時間」のチェックを外す。「タスクが失敗した場合の再起動の間隔」を1分・3回にする

## 手動で動かす(試すとき)

タスクスケジューラを使わずに、画面にログを出しながら動かすこともできる。`Ctrl+C` で止まる。

```powershell
python "C:\tools\notify_watcher\notify_watcher.py"
```

常駐中のものがあるときは、二重起動を防ぐため「すでに起動しているため終了します」と出てすぐ終わる。
試すときは、先に `Stop-ScheduledTask -TaskName "通知監視"` で止めておく。

## ログ

- 場所:`logs\notify_watcher.log`
- 日付が変わると前日分が `notify_watcher.log.2026-10-23` のような名前に切り替わり、30日分残る
- 記録する内容:監視の開始、ファイルの検知と鳴らした音、削除、エラー

例:

```
2026-10-23 16:23:04,140 [INFO] 設定を読み込みました: 音量 100 / 音ごとの音量 なし
2026-10-23 16:23:04,144 [INFO] 監視を開始します: C:\tools\notify_watcher\call
2026-10-23 16:23:08,149 [INFO] 検知: 確認 → 通知OFF(通知OFF のため鳴らしません)
2026-10-23 16:23:08,150 [INFO] 削除: 確認
2026-10-23 16:23:12,160 [INFO] 設定を読み込みました: 音量 70 / 音ごとの音量 {'完了': 40}
2026-10-23 16:23:12,163 [INFO] 検知: 完了 → 完了.mp3(音量 40)
2026-10-23 16:23:15,401 [INFO] 削除: 完了
```

## 困ったとき

| 症状 | 確認すること |
|---|---|
| 音が鳴らない | `通知OFF` ファイルが置かれていないか。`notify_watcher.toml` の音量が 0 になっていないか。PCの音量・出力先のスピーカー。タスクが `Running` か |
| 音量を変えても変わらない | ログに「設定ファイルを読めませんでした」が出ていないか(理由も出る)。日本語の項目名を `"` で囲んでいるか |
| ファイルが消えない | タスクが `Running` か。ログに「削除できませんでした」が出ていないか(ほかのプログラムがファイルを開いたままになっている) |
| ログに「通知音のファイルがありません」 | `通知音` フォルダに mp3 があるか、名前が合っているか |
| ログに「通知音を鳴らせませんでした」 | mp3 ファイルが壊れていないか。この場合も `call` のファイルは削除される |
| タスクが起動しない | `pythonw.exe` のパスが変わっていないか(上の「`pythonw.exe` のパス」を参照) |

## しくみ

- mp3 は Windows の MCI(`winmm.dll` の `mciSendStringW`)で鳴らしている
- 置かれてから0.5秒たったファイルだけを処理する(書き込み途中のファイルを消さないため)
- `notify_watcher.toml` は通知を鳴らすたびに読み直している(起動時にも一度読む)
- 二重起動は Windows のミューテックスで防いでいる
- `call` の中のフォルダは無視する(ファイルだけが対象)
- `call\.gitkeep` は無視する(音を鳴らさず、削除もしない)。Git で空の `call` フォルダを残すために置いている

## ライセンス

MIT License。個人・商用を問わず、自由に使用・改変・再配布できる。詳しくは [LICENSE](LICENSE) を参照。

`通知音` フォルダの mp3 も、このプログラムのために独自に作った音なので、同じ MIT License で自由に使える。
