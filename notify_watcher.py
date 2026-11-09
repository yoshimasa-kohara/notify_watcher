"""通知監視プログラム。

call フォルダにファイルが置かれたら、ファイル名に応じた通知音(mp3)を鳴らし、
鳴り終わったらそのファイルを削除する。

    確認     → 通知音\\確認.mp3
    完了     → 通知音\\完了.mp3
    それ以外 → 通知音\\通知.mp3

通知OFF ファイル(このプログラムと同じフォルダ)が置かれている間は音を鳴らさず、
call のファイルを削除するだけにする。通知OFF ファイルは利用者が手で置き・消しするので、ここでは消さない。

音量は設定ファイル notify_watcher.toml(このプログラムと同じフォルダ)で決める。
通知を鳴らすたびに読み直すので、書き換えてもプログラムの再起動はいらない。
読めないときは、最後に正しく読めた設定(一度も読めていなければ音量100)で鳴らす。

標準ライブラリだけで動く(mp3 の再生は Windows の MCI(エムシーアイ)を使う)。
"""

import ctypes
import logging
import sys
import time
import tomllib
from dataclasses import dataclass, field
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

BASE_DIR: Path = Path(__file__).resolve().parent
CALL_DIR: Path = BASE_DIR / "call"
SOUND_DIR: Path = BASE_DIR / "通知音"
LOG_DIR: Path = BASE_DIR / "logs"

# ファイル名(拡張子なし) → 鳴らす mp3。どれにも当たらなければ DEFAULT_SOUND
SOUND_MAP: dict[str, Path] = {
    "確認": SOUND_DIR / "確認.mp3",
    "完了": SOUND_DIR / "完了.mp3",
}
DEFAULT_SOUND: Path = SOUND_DIR / "通知.mp3"
# 設定ファイル
SETTINGS_FILE: Path = BASE_DIR / "notify_watcher.toml"
# 設定ファイルの項目名
KEY_VOLUME: str = "音量"
KEY_SOUND_VOLUMES: str = "音ごとの音量"
# 設定ファイルが一度も読めていないときの音量
DEFAULT_VOLUME: int = 100
# このファイルがあるときは音を鳴らさない(「通知OFF.txt」のような拡張子つきも同じ扱い)
MUTE_NAME: str = "通知OFF"
# call フォルダにあっても無視するファイル(Git で空フォルダを残すためのもの)
IGNORE_NAMES: set[str] = {".gitkeep"}

# call フォルダを見に行く間隔(秒)
POLL_SECONDS: float = 1.0
# 書き込み中のファイルを避けるため、置かれてからこの秒数たったものだけ処理する
SETTLE_SECONDS: float = 0.5
# 二重起動を防ぐためのミューテックス名
MUTEX_NAME: str = "Local\\notify_watcher_通知監視"
ERROR_ALREADY_EXISTS: int = 183

logger: logging.Logger = logging.getLogger("notify_watcher")


@dataclass(frozen=True)
class Settings:
    """設定ファイルの内容。音量はどちらも 0〜100。"""

    volume: int = DEFAULT_VOLUME
    # mp3 のファイル名(拡張子なし) → 音量
    sound_volumes: dict[str, int] = field(default_factory=dict)


# 最後に正しく読めた設定。一度も読めていなければ既定値
last_settings: Settings = Settings()


def setup_logging() -> None:
    """logs フォルダに日ごとのログを出す(30日分残す)。"""
    LOG_DIR.mkdir(exist_ok=True)
    handler = TimedRotatingFileHandler(
        LOG_DIR / "notify_watcher.log", when="midnight", backupCount=30, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    # pythonw で起動したときは標準出力がないので、コンソールがあるときだけ画面にも出す
    if sys.stdout is not None:
        logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.setLevel(logging.INFO)


def acquire_single_instance() -> object | None:
    """二重起動なら None を返す。戻り値のハンドルはプログラム終了まで持っておく。"""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return None
    return handle


def mci(command: str) -> None:
    """MCI のコマンドを送る。失敗したら例外にする。"""
    buffer = ctypes.create_unicode_buffer(256)
    error = ctypes.windll.winmm.mciSendStringW(command, buffer, len(buffer), None)
    if error != 0:
        message = ctypes.create_unicode_buffer(256)
        ctypes.windll.winmm.mciGetErrorStringW(error, message, len(message))
        raise RuntimeError(f"MCI エラー({error}): {message.value} / コマンド: {command}")


def to_volume(value: object, name: str) -> int:
    """設定の値を音量(0〜100)にする。数でなければ例外にする。範囲外は 0 か 100 に丸める。"""
    # TOML の true/false は Python では int の仲間なので、先にはじく
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"「{name}」は 0〜100 の数で書いてください(今の値: {value!r})")
    volume = int(value)
    if not 0 <= volume <= 100:
        clamped = max(0, min(volume, 100))
        logger.warning("「%s」が 0〜100 の範囲外なので %d にします(今の値: %s)", name, clamped, value)
        return clamped
    return volume


def parse_settings(data: dict) -> Settings:
    """TOML を読んだ結果から Settings を作る。書き方がおかしければ例外にする。"""
    volume = to_volume(data.get(KEY_VOLUME, DEFAULT_VOLUME), KEY_VOLUME)

    table = data.get(KEY_SOUND_VOLUMES, {})
    if not isinstance(table, dict):
        raise ValueError(f"「{KEY_SOUND_VOLUMES}」は [{KEY_SOUND_VOLUMES}] の表として書いてください")
    sound_volumes = {
        str(name): to_volume(value, f"{KEY_SOUND_VOLUMES}.{name}") for name, value in table.items()
    }
    return Settings(volume=volume, sound_volumes=sound_volumes)


def load_settings() -> Settings:
    """設定ファイルを読む。読めなければ警告を出し、最後に正しく読めた設定を返す。"""
    global last_settings
    try:
        # メモ帳で「UTF-8(BOM付き)」で保存されても読めるように utf-8-sig で読む
        text = SETTINGS_FILE.read_text(encoding="utf-8-sig")
        settings = parse_settings(tomllib.loads(text))
    except FileNotFoundError:
        logger.warning("設定ファイルがありません: %s(音量 %d で鳴らします)", SETTINGS_FILE, last_settings.volume)
        return last_settings
    except Exception as e:
        logger.warning(
            "設定ファイルを読めませんでした: %s(前の設定で鳴らします)/ 理由: %s", SETTINGS_FILE.name, e
        )
        return last_settings

    if settings != last_settings:
        logger.info(
            "設定を読み込みました: 音量 %d / 音ごとの音量 %s", settings.volume, settings.sound_volumes or "なし"
        )
    last_settings = settings
    return settings


def get_volume(sound: Path, settings: Settings) -> int:
    """鳴らす音の音量(0〜100)を決める。音ごとの音量がなければ全体の音量にする。"""
    return settings.sound_volumes.get(sound.stem, settings.volume)


def play_sound(sound: Path, volume: int) -> None:
    """mp3 を指定の音量(0〜100)で鳴らし、鳴り終わるまで待つ。"""
    alias = "notify_sound"
    mci(f'open "{sound}" type mpegvideo alias {alias}')
    try:
        try:
            # MCI の音量は 0〜1000 で指定する
            mci(f"setaudio {alias} volume to {volume * 10}")
        except RuntimeError:
            # 音量を変えられなくても、音は鳴らす
            logger.exception("音量を変えられませんでした(そのままの音量で鳴らします): %s", sound)
        mci(f"play {alias} wait")
    finally:
        mci(f"close {alias}")


def select_sound(file: Path) -> Path:
    """ファイル名に応じて鳴らす mp3 を決める。「確認.txt」のような拡張子つきも同じ扱いにする。"""
    return SOUND_MAP.get(file.name, SOUND_MAP.get(file.stem, DEFAULT_SOUND))


def is_muted() -> bool:
    """通知OFF ファイルが置かれているか。"""
    return (BASE_DIR / MUTE_NAME).is_file() or any(
        p.is_file() for p in BASE_DIR.glob(f"{MUTE_NAME}.*")
    )


def delete_file(file: Path) -> None:
    """ファイルを消す。ほかのプログラムが掴んでいるときは少し待って再試行する。"""
    for _ in range(10):
        try:
            file.unlink(missing_ok=True)
            return
        except PermissionError:
            time.sleep(0.5)
    logger.error("削除できませんでした: %s", file)


def find_ready_files() -> list[Path]:
    """call フォルダのうち、書き込みが終わっていそうなファイルを古い順に返す。"""
    now = time.time()
    files: list[Path] = []
    for path in CALL_DIR.iterdir():
        if path.name.lower() in IGNORE_NAMES:
            continue
        try:
            if path.is_file() and now - path.stat().st_mtime >= SETTLE_SECONDS:
                files.append(path)
        except FileNotFoundError:
            continue  # 見ている間に消された
    return sorted(files, key=lambda p: p.stat().st_mtime)


def handle_file(file: Path) -> None:
    sound = select_sound(file)
    if is_muted():
        logger.info("検知: %s → %s(通知OFF のため鳴らしません)", file.name, MUTE_NAME)
        delete_file(file)
        logger.info("削除: %s", file.name)
        return
    volume = get_volume(sound, load_settings())
    logger.info("検知: %s → %s(音量 %d)", file.name, sound.name, volume)
    try:
        play_sound(sound, volume)
    except Exception:
        # 音が鳴らせなくてもファイルは消す(残すと毎秒鳴らし直そうとしてしまうため)
        logger.exception("通知音を鳴らせませんでした: %s", sound)
    delete_file(file)
    logger.info("削除: %s", file.name)


def main() -> int:
    setup_logging()
    mutex = acquire_single_instance()
    if mutex is None:
        logger.warning("すでに起動しているため終了します")
        return 1

    CALL_DIR.mkdir(exist_ok=True)
    for sound in [*SOUND_MAP.values(), DEFAULT_SOUND]:
        if not sound.exists():
            logger.warning("通知音のファイルがありません: %s", sound)
    load_settings()  # 起動時にも一度読んで、設定の間違いに早めに気づけるようにする
    logger.info("監視を開始します: %s", CALL_DIR)

    while True:
        try:
            for file in find_ready_files():
                handle_file(file)
        except Exception:
            # 想定外のエラーでも常駐は続ける
            logger.exception("監視中にエラーが起きました")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("監視を終了します")
