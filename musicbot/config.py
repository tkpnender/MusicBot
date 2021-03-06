import os
import sys
import codecs
import shutil
import logging
import configparser

from .exceptions import HelpfulError

log = logging.getLogger(__name__)


class Config:
    # noinspection PyUnresolvedReferences
    def __init__(self, config_file):
        self.config_file = config_file
        self.find_config()

        config = configparser.ConfigParser(interpolation=None)
        config.read(config_file, encoding='utf-8')

        confsections = {"Credentials", "Permissions", "Chat", "MusicBot"}.difference(config.sections())
        if confsections:
            raise HelpfulError(
                "1つまたは複数の必須設定セクションがありません。",
                "設定を修正してください。それぞれの[Section]はそれぞれ "
                "それ以外は何もない。次のセクションがありません:{}".format(
                    ', '.join(['[%s]' % s for s in confsections])
                ),
                preface="configの解析中にエラーが発生しました:\n"
            )

        self._confpreface = "configの読み込み中にエラーが発生しました:\n"
        self._confpreface2 = "configの検証中にエラーが発生しました:\n"

        self._login_token = config.get('Credentials', 'Token', fallback=ConfigDefaults.token)

        self.auth = ()

        self.spotify_clientid = config.get('Credentials', 'Spotify_ClientID', fallback=ConfigDefaults.spotify_clientid)
        self.spotify_clientsecret = config.get('Credentials', 'Spotify_ClientSecret', fallback=ConfigDefaults.spotify_clientsecret)

        self.owner_id = config.get('Permissions', 'OwnerID', fallback=ConfigDefaults.owner_id)
        self.dev_ids = config.get('Permissions', 'DevIDs', fallback=ConfigDefaults.dev_ids)

        self.command_prefix = config.get('Chat', 'CommandPrefix', fallback=ConfigDefaults.command_prefix)
        self.bound_channels = config.get('Chat', 'BindToChannels', fallback=ConfigDefaults.bound_channels)
        self.autojoin_channels =  config.get('Chat', 'AutojoinChannels', fallback=ConfigDefaults.autojoin_channels)

        self.default_volume = config.getfloat('MusicBot', 'DefaultVolume', fallback=ConfigDefaults.default_volume)
        self.skips_required = config.getint('MusicBot', 'SkipsRequired', fallback=ConfigDefaults.skips_required)
        self.skip_ratio_required = config.getfloat('MusicBot', 'SkipRatio', fallback=ConfigDefaults.skip_ratio_required)
        self.save_videos = config.getboolean('MusicBot', 'SaveVideos', fallback=ConfigDefaults.save_videos)
        self.now_playing_mentions = config.getboolean('MusicBot', 'NowPlayingMentions', fallback=ConfigDefaults.now_playing_mentions)
        self.auto_summon = config.getboolean('MusicBot', 'AutoSummon', fallback=ConfigDefaults.auto_summon)
        self.auto_playlist = config.getboolean('MusicBot', 'UseAutoPlaylist', fallback=ConfigDefaults.auto_playlist)
        self.auto_playlist_random = config.getboolean('MusicBot', 'AutoPlaylistRandom', fallback=ConfigDefaults.auto_playlist_random)
        self.auto_pause = config.getboolean('MusicBot', 'AutoPause', fallback=ConfigDefaults.auto_pause)
        self.delete_messages = config.getboolean('MusicBot', 'DeleteMessages', fallback=ConfigDefaults.delete_messages)
        self.delete_invoking = config.getboolean('MusicBot', 'DeleteInvoking', fallback=ConfigDefaults.delete_invoking)
        self.persistent_queue = config.getboolean('MusicBot', 'PersistentQueue', fallback=ConfigDefaults.persistent_queue)
        self.status_message = config.get('MusicBot', 'StatusMessage', fallback=ConfigDefaults.status_message)
        self.write_current_song = config.getboolean('MusicBot', 'WriteCurrentSong', fallback=ConfigDefaults.write_current_song)
        self.allow_author_skip = config.getboolean('MusicBot', 'AllowAuthorSkip', fallback=ConfigDefaults.allow_author_skip)
        self.use_experimental_equalization = config.getboolean('MusicBot', 'UseExperimentalEqualization', fallback=ConfigDefaults.use_experimental_equalization)
        self.embeds = config.getboolean('MusicBot', 'UseEmbeds', fallback=ConfigDefaults.embeds)
        self.queue_length = config.getint('MusicBot', 'QueueLength', fallback=ConfigDefaults.queue_length)
        self.remove_ap = config.getboolean('MusicBot', 'RemoveFromAPOnError', fallback=ConfigDefaults.remove_ap)
        self.show_config_at_start = config.getboolean('MusicBot', 'ShowConfigOnLaunch', fallback=ConfigDefaults.show_config_at_start)

        self.debug_level = config.get('MusicBot', 'DebugLevel', fallback=ConfigDefaults.debug_level)
        self.debug_level_str = self.debug_level
        self.debug_mode = False

        self.blacklist_file = config.get('Files', 'BlacklistFile', fallback=ConfigDefaults.blacklist_file)
        self.auto_playlist_file = config.get('Files', 'AutoPlaylistFile', fallback=ConfigDefaults.auto_playlist_file)
        self.i18n_file = config.get('Files', 'i18nFile', fallback=ConfigDefaults.i18n_file)
        self.auto_playlist_removed_file = None

        self.run_checks()

        self.missing_keys = set()
        self.check_changes(config)

        self.find_autoplaylist()

    def get_all_keys(self, conf):
        """すべての設定キーをリストとして返します"""
        sects = dict(conf.items())
        keys = []
        for k in sects:
            s = sects[k]
            keys += [key for key in s.keys()]
        return keys

    def check_changes(self, conf):
        exfile = 'config/example_options.ini'
        if os.path.isfile(exfile):
            usr_keys = self.get_all_keys(conf)
            exconf = configparser.ConfigParser(interpolation=None)
            if not exconf.read(exfile, encoding='utf-8'):
                return
            ex_keys = self.get_all_keys(exconf)
            if set(usr_keys) != set(ex_keys):
                self.missing_keys = set(ex_keys) - set(usr_keys)  # to raise this as an issue in bot.py later

    def run_checks(self):
        """
        ボット設定の検証ロジック。
        """
        if self.i18n_file != ConfigDefaults.i18n_file and not os.path.isfile(self.i18n_file):
            log.warning('i18n file does not exist. Trying to fallback to {0}.'.format(ConfigDefaults.i18n_file))
            self.i18n_file = ConfigDefaults.i18n_file

        if not os.path.isfile(self.i18n_file):
            raise HelpfulError(
                "i18nファイルが見つかりませんでした。フォールバックできませんでした。",
                "その結果、ボットは起動できません。いくつかのファイルを移動しましたか？ "
                "Gitの最近の変更を取り戻すか、ローカルのリポジトリをリセットしてみてください。",
                preface=self._confpreface
            )

        log.info('i18nを使う:{0}'.format(self.i18n_file))

        if not self._login_token:
            raise HelpfulError(
                "設定にボットトークンが指定されていません。",
                "v1.1.0以降、Discordボットアカウントを使用する必要があります。"
                " ",
                preface=self._confpreface
            )

        else:
            self.auth = (self._login_token,)

        if self.owner_id:
            self.owner_id = self.owner_id.lower()

            if self.owner_id.isdigit():
                if int(self.owner_id) < 10000:
                    raise HelpfulError(
                        "無効なOwnerIDが設定されました:{}".format(self.owner_id),

                        "OwnerIDを修正してください。 IDはちょうど数字でなければなりません。 "
                        "18文字、または「auto」です。自分のIDがわからない場合は、 "
                        "オプションの指示を入力するか、ヘルプサーバーに問い合わせてください。",
                        preface=self._confpreface
                    )

            elif self.owner_id == 'auto':
                pass # defer to async check

            else:
                self.owner_id = None

        if not self.owner_id:
            raise HelpfulError(
                "OwnerIDが設定されていません。",
                "OwnerIDオプションを{}に設定してください".format(self.config_file),
                preface=self._confpreface
            )

        if self.bound_channels:
            try:
                self.bound_channels = set(x for x in self.bound_channels.split() if x)
            except:
                log.warning("BindToChannelsのデータが無効で、任意のチャンネルにバインドされません。")
                self.bound_channels = set()

        if self.autojoin_channels:
            try:
                self.autojoin_channels = set(x for x in self.autojoin_channels.split() if x)
            except:
                log.warning("AutojoinChannelsデータが無効で、チャンネルに自動参加しません")
                self.autojoin_channels = set()

        self._spotify = False
        if self.spotify_clientid and self.spotify_clientsecret:
            self._spotify = True

        self.delete_invoking = self.delete_invoking and self.delete_messages

        self.bound_channels = set(item.replace(',', ' ').strip() for item in self.bound_channels)

        self.autojoin_channels = set(item.replace(',', ' ').strip() for item in self.autojoin_channels)

        ap_path, ap_name = os.path.split(self.auto_playlist_file)
        apn_name, apn_ext = os.path.splitext(ap_name)
        self.auto_playlist_removed_file = os.path.join(ap_path, apn_name + '_removed' + apn_ext)

        if hasattr(logging, self.debug_level.upper()):
            self.debug_level = getattr(logging, self.debug_level.upper())
        else:
            log.warning("無効なDebugLevelオプション\"{}\"が指定され、INFOに戻っています".format(self.debug_level_str))
            self.debug_level = logging.INFO
            self.debug_level_str = 'INFO'

        self.debug_mode = self.debug_level <= logging.DEBUG

        self.create_empty_file_ifnoexist('config/blacklist.txt')
        self.create_empty_file_ifnoexist('config/whitelist.txt')

    def create_empty_file_ifnoexist(self, path):
        if not os.path.isfile(path):
            open(path, 'a').close()
            log.warning('%sを作成' % path)

    # TODO: Add save function for future editing of options with commands
    #       Maybe add warnings about fields missing from the config file

    async def async_validate(self, bot):
        log.debug("オプションの検証中...")

        if self.owner_id == 'auto':
            if not bot.user.bot:
                raise HelpfulError(
                    "Invalid parameter \"auto\" for OwnerID option.",

                    "Only bot accounts can use the \"auto\" option.  Please "
                    "set the OwnerID in the config.",

                    preface=self._confpreface2
                )

            self.owner_id = bot.cached_app_info.owner.id
            log.debug("API経由でオーナーIDを取得しました")

        if self.owner_id == bot.user.id:
            raise HelpfulError(
                 "Your OwnerID is incorrect or you've used the wrong credentials.",

                "The bot's user ID and the id for OwnerID is identical. "
                "This is wrong. The bot needs a bot account to function, "
                "meaning you cannot use your own account to run the bot on. "
                "The OwnerID is the id of the owner, not the bot. "
                "Figure out which one is which and use the correct information.",

                preface=self._confpreface2
            )


    def find_config(self):
        config = configparser.ConfigParser(interpolation=None)

        if not os.path.isfile(self.config_file):
            if os.path.isfile(self.config_file + '.ini'):
                shutil.move(self.config_file + '.ini', self.config_file)
                log.info("{0}を{1}に移動すると、ファイル拡張子を有効にする必要があります。".format(
                    self.config_file + '.ini', self.config_file
                ))

            elif os.path.isfile('config/example_options.ini'):
                shutil.copy('config/example_options.ini', self.config_file)
                log.warning('Options file not found, copying example_options.ini')

            else:
                raise HelpfulError(
                    "設定ファイルがありません。 options.iniもexample_options.iniも見つかりませんでした。",
                    "アーカイブからファイルを取り戻すか、自分でリメイクしてコンテンツをコピーして貼り付けます "
                    "レポから。重要なファイルの削除をやめてください！"
                )

        if not config.read(self.config_file, encoding='utf-8'):
            c = configparser.ConfigParser()
            try:
                # load the config again and check to see if the user edited that one
                c.read(self.config_file, encoding='utf-8')

                if not int(c.get('Permissions', 'OwnerID', fallback=0)): # jake pls no flame
                    print(flush=True)
                    log.critical("config/options.iniを設定して、ボットを再実行してください。")
                    sys.exit(1)

            except ValueError: # Config id value was changed but its not valid
                raise HelpfulError(
                    '所有者IDの値「{}」が無効です。設定を読み込めません。'.format(
                        c.get('Permissions', 'OwnerID', fallback=None)
                    ),
                    "OwnerIDオプションにはユーザーIDまたは 'auto'が必要です。"
                )

            except Exception as e:
                print(flush=True)
                log.critical("config/example_options.iniを{}にコピーできません".format(self.config_file), exc_info=e)
                sys.exit(2)

    def find_autoplaylist(self):
        if not os.path.exists(self.auto_playlist_file):
            if os.path.exists('config/_autoplaylist.txt'):
                shutil.copy('config/_autoplaylist.txt', self.auto_playlist_file)
                log.debug("Copying _autoplaylist.txt to autoplaylist.txt")
            else:
                log.warning("自動再生リストファイルが見つかりませんでした。")


    def write_default_config(self, location):
        pass


class ConfigDefaults:
    owner_id = None

    token = None
    dev_ids = set()

    spotify_clientid = None
    spotify_clientsecret = None

    command_prefix = '!'
    bound_channels = set()
    autojoin_channels = set()

    default_volume = 0.15
    skips_required = 4
    skip_ratio_required = 0.5
    save_videos = True
    now_playing_mentions = False
    auto_summon = True
    auto_playlist = True
    auto_playlist_random = True
    auto_pause = True
    delete_messages = True
    delete_invoking = False
    persistent_queue = True
    debug_level = 'INFO'
    status_message = None
    write_current_song = False
    allow_author_skip = True
    use_experimental_equalization = False
    embeds = True
    queue_length = 10
    remove_ap = True
    show_config_at_start = False

    options_file = 'config/options.ini'
    blacklist_file = 'config/blacklist.txt'
    auto_playlist_file = 'config/autoplaylist.txt'  # this will change when I add playlists
    i18n_file = 'config/i18n/en.json'

setattr(ConfigDefaults, codecs.decode(b'ZW1haWw=', '\x62\x61\x73\x65\x36\x34').decode('ascii'), None)
setattr(ConfigDefaults, codecs.decode(b'cGFzc3dvcmQ=', '\x62\x61\x73\x65\x36\x34').decode('ascii'), None)
setattr(ConfigDefaults, codecs.decode(b'dG9rZW4=', '\x62\x61\x73\x65\x36\x34').decode('ascii'), None)

# These two are going to be wrappers for the id lists, with add/remove/load/save functions
# and id/object conversion so types aren't an issue
class Blacklist:
    pass

class Whitelist:
    pass
