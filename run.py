from __future__ import print_function

import os
import sys
import time
import logging
import tempfile
import traceback
import subprocess

from shutil import disk_usage, rmtree
from base64 import b64decode

try:
    import pathlib
    import importlib.util
except ImportError:
    pass


class GIT(object):
    @classmethod
    def works(cls):
        try:
            return bool(subprocess.check_output('git --version', shell=True))
        except:
            return False


class PIP(object):
    @classmethod
    def run(cls, command, check_output=False):
        if not cls.works():
            raise RuntimeError("pipをインポートできませんでした。")

        try:
            return PIP.run_python_m(*command.split(), check_output=check_output)
        except subprocess.CalledProcessError as e:
            return e.returncode
        except:
            traceback.print_exc()
            print("Error using -m method")

    @classmethod
    def run_python_m(cls, *args, **kwargs):
        check_output = kwargs.pop('check_output', False)
        check = subprocess.check_output if check_output else subprocess.check_call
        return check([sys.executable, '-m', 'pip'] + list(args))

    @classmethod
    def run_pip_main(cls, *args, **kwargs):
        import pip

        args = list(args)
        check_output = kwargs.pop('check_output', False)

        if check_output:
            from io import StringIO

            out = StringIO()
            sys.stdout = out

            try:
                pip.main(args)
            except:
                traceback.print_exc()
            finally:
                sys.stdout = sys.__stdout__

                out.seek(0)
                pipdata = out.read()
                out.close()

                print(pipdata)
                return pipdata
        else:
            return pip.main(args)

    @classmethod
    def run_install(cls, cmd, quiet=False, check_output=False):
        return cls.run("install %s%s" % ('-q ' if quiet else '', cmd), check_output)

    @classmethod
    def run_show(cls, cmd, check_output=False):
        return cls.run("show %s" % cmd, check_output)

    @classmethod
    def works(cls):
        try:
            import pip
            return True
        except ImportError:
            return False

    # noinspection PyTypeChecker
    @classmethod
    def get_module_version(cls, mod):
        try:
            out = cls.run_show(mod, check_output=True)

            if isinstance(out, bytes):
                out = out.decode()

            datas = out.replace('\r\n', '\n').split('\n')
            expectedversion = datas[3]

            if expectedversion.startswith('Version: '):
                return expectedversion.split()[1]
            else:
                return [x.split()[1] for x in datas if x.startswith("Version: ")][0]
        except:
            pass

    @classmethod
    def get_requirements(cls, file='requirements.txt'):
        from pip.req import parse_requirements
        return list(parse_requirements(file))


# Setup initial loggers

tmpfile = tempfile.TemporaryFile('w+', encoding='utf8')
log = logging.getLogger('ランチャー')
log.setLevel(logging.DEBUG)

sh = logging.StreamHandler(stream=sys.stdout)
sh.setFormatter(logging.Formatter(
    fmt="[%(levelname)s] %(name)s: %(message)s"
))

sh.setLevel(logging.INFO)
log.addHandler(sh)

tfh = logging.StreamHandler(stream=tmpfile)
tfh.setFormatter(logging.Formatter(
    fmt="[%(relativeCreated).9f] %(asctime)s - %(levelname)s - %(name)s: %(message)s"
))
tfh.setLevel(logging.DEBUG)
log.addHandler(tfh)


def finalize_logging():
    if os.path.isfile("logs/musicbot.log"):
        log.info("古いミュージックボットのログを移動する")
        try:
            if os.path.isfile("logs/musicbot.log.last"):
                os.unlink("logs/musicbot.log.last")
            os.rename("logs/musicbot.log", "logs/musicbot.log.last")
        except:
            pass

    with open("logs/musicbot.log", 'w', encoding='utf8') as f:
        tmpfile.seek(0)
        f.write(tmpfile.read())
        tmpfile.close()

        f.write('\n')
        f.write(" PRE-RUN SANITY CHECKS PASSED ".center(80, '#'))
        f.write('\n\n')

    global tfh
    log.removeHandler(tfh)
    del tfh

    fh = logging.FileHandler("logs/musicbot.log", mode='a')
    fh.setFormatter(logging.Formatter(
        fmt="[%(relativeCreated).9f] %(name)s-%(levelname)s: %(message)s"
    ))
    fh.setLevel(logging.DEBUG)
    log.addHandler(fh)

    sh.setLevel(logging.INFO)

    dlog = logging.getLogger('discord')
    dlh = logging.StreamHandler(stream=sys.stdout)
    dlh.terminator = ''
    dlh.setFormatter(logging.Formatter('.'))
    dlog.addHandler(dlh)


def bugger_off(msg="Enterキーを押して続行します...", code=1):
    input(msg)
    sys.exit(code)


# TODO: all of this
def sanity_checks(optional=True):
    log.info("サニティチェックの開始")
    ## Required

    # Make sure we're on Python 3.5+
    req_ensure_py3()

    # Fix windows encoding fuckery
    req_ensure_encoding()

    # Make sure we're in a writeable env
    req_ensure_env()

    # Make our folders if needed
    req_ensure_folders()

    log.info("必要なチェックが完了しました。")

    ## Optional
    if not optional:
        return

    # Check disk usage
    opt_check_disk_space()

    log.info("オプションのチェックが完了しました。")


def req_ensure_py3():
    log.info("Python 3.5+のチェック")

    if sys.version_info < (3, 5):
        log.warning("Python 3.5以降が必要です。このバージョンは%sです", sys.version.split()[0])
        log.warning("Python 3.5の検索を試みています...")

        pycom = None

        if sys.platform.startswith('win'):
            log.info('Trying "py -3.5"')
            try:
                subprocess.check_output('py -3.5 -c "exit()"', shell=True)
                pycom = 'py -3.5'
            except:

                log.info('Trying "python3"')
                try:
                    subprocess.check_output('python3 -c "exit()"', shell=True)
                    pycom = 'python3'
                except:
                    pass

            if pycom:
                log.info("Python 3が見つかりました。ボットを起動...")
                pyexec(pycom, 'run.py')

                # I hope ^ works
                os.system('start cmd /k %s run.py' % pycom)
                sys.exit(0)

        else:
            log.info('Trying "python3.5"')
            try:
                pycom = subprocess.check_output('python3.5 -c "exit()"'.split()).strip().decode()
            except:
                pass

            if pycom:
                log.info("\n Python 3が見つかりました。ボットを再起動する: %s run.py\n", pycom)
                pyexec(pycom, 'run.py')

        log.critical("Python 3.5以降は見つかりませんでした。 Python 3.5を使ってボットを実行してください")
        bugger_off()


def req_ensure_encoding():
    log.info("コンソールエンコーディングの確認")

    if sys.platform.startswith('win') or sys.stdout.encoding.replace('-', '').lower() != 'utf8':
        log.info("コンソールエンコーディングをUTF-8に設定する")

        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf8', line_buffering=True)
        # only slightly evil    
        sys.__stdout__ = sh.stream = sys.stdout

        if os.environ.get('PYCHARM_HOSTED', None) not in (None, '0'):
            log.info("pycharm pseudoconsoleでの色の有効化")
            sys.stdout.isatty = lambda: True


def req_ensure_env():
    log.info("正しい環境にいることを保証します。")

    if os.environ.get('APP_ENV') != 'docker' and not os.path.isdir(b64decode('LmdpdA==').decode('utf-8')):
        log.critical(b64decode('Qm90IHdhc24ndCBpbnN0YWxsZWQgdXNpbmcgR2l0LiBSZWluc3RhbGwgdXNpbmcgaHR0cDovL2JpdC5seS9tdXNpY2JvdGRvY3Mu').decode('utf-8'))
        bugger_off()

    try:
        assert os.path.isdir('config'), 'folder "config" not found'
        assert os.path.isdir('musicbot'), 'folder "musicbot" not found'
        assert os.path.isfile('musicbot/__init__.py'), 'musicbot folder is not a Python module'

        assert importlib.util.find_spec('musicbot'), "musicbot module is not importable"
    except AssertionError as e:
        log.critical("失敗した環境チェック、%s", e)
        bugger_off()

    try:
        os.mkdir('musicbot-test-folder')
    except Exception:
        log.critical("現在の作業ディレクトリは書き込み可能ではないようです")
        log.critical("ボットを書き込み可能なフォルダに移動してください")
        bugger_off()
    finally:
        rmtree('musicbot-test-folder', True)

    if sys.platform.startswith('win'):
        log.info("local bins/フォルダをパスに追加する")
        os.environ['PATH'] += ';' + os.path.abspath('bin/')
        sys.path.append(os.path.abspath('bin/')) # might as well


def req_ensure_folders():
    pathlib.Path('logs').mkdir(exist_ok=True)
    pathlib.Path('data').mkdir(exist_ok=True)

def opt_check_disk_space(warnlimit_mb=200):
    if disk_usage('.').free < warnlimit_mb*1024*2:
        log.warning("このデバイスには%sMB未満の空き領域が残ります" % warnlimit_mb)


#################################################

def pyexec(pycom, *args, pycom2=None):
    pycom2 = pycom2 or pycom
    os.execlp(pycom, pycom2, *args)


def main():
    # TODO: *actual* argparsing

    if '--no-checks' not in sys.argv:
        sanity_checks()

    finalize_logging()

    import asyncio

    tried_requirementstxt = False
    tryagain = True

    loops = 0
    max_wait_time = 60

    while tryagain:
        # Maybe I need to try to import stuff first, then actually import stuff
        # It'd save me a lot of pain with all that awful exception type checking

        m = None
        try:
            from musicbot import MusicBot
            m = MusicBot()

            sh.terminator = ''
            sh.terminator = '\n'

            m.run()

        except SyntaxError:
            log.exception("構文エラー(これはあなたのせいではなくバグです)")
            break

        except ImportError:
            # TODO: if error module is in pip or dpy requirements...

            if not tried_requirementstxt:
                tried_requirementstxt = True

                log.exception("ボットを起動する際のエラー")
                log.info("依存関係をインストールしようとしています...")

                err = PIP.run_install('--upgrade -r requirements.txt')

                if err: # TODO: add the specific error check back as not to always tell users to sudo it
                    print()
                    log.critical("依存関係をインストールするには、%sが必要な場合があります。" %
                                 ['use sudo', 'run as admin'][sys.platform.startswith('win')])
                    break
                else:
                    print()
                    log.info("それがうまくいくことを望みます")
                    print()
            else:
                log.exception("不明なImportError、終了します。")
                break

        except Exception as e:
            if hasattr(e, '__module__') and e.__module__ == 'musicbot.exceptions':
                if e.__class__.__name__ == 'HelpfulError':
                    log.info(e.message)
                    break

                elif e.__class__.__name__ == "TerminateSignal":
                    break

                elif e.__class__.__name__ == "RestartSignal":
                    loops = 0
                    pass
            else:
                log.exception("ボットを起動する際のエラー")

        finally:
            if not m or not m.init_ok:
                if any(sys.exc_info()):
                    # How to log this without redundant messages...
                    traceback.print_exc()
                break

            asyncio.set_event_loop(asyncio.new_event_loop())
            loops += 1

        sleeptime = min(loops * 2, max_wait_time)
        if sleeptime:
            log.info("{}秒後に再開しています...".format(loops*2))
            time.sleep(sleeptime)

    print()
    log.info("すべて完了。")


if __name__ == '__main__':
    main()
