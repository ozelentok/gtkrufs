#!/usr/bin/env python3

import datetime
import errno
import stat
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path
from sys import stderr
from threading import Thread
from typing import Callable, Generator, cast
from urllib.parse import unquote

import fuse
from fuse import Direntry, Fuse
from inotify_simple import INotify, flags

fuse.fuse_python_api = fuse.FUSE_PYTHON_API_VERSION
RU_PATH = Path.home() / ".local/share/recently-used.xbel"


def log_error(func: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            trace = traceback.format_exc()
            print(trace, file=stderr)
            raise

    return wrapper


class GRUStat:
    def __init__(self):
        self.st_mode = 0
        self.st_ino = 0
        self.st_dev = 0
        self.st_nlink = 0
        self.st_uid = 0
        self.st_gid = 0
        self.st_size = 0
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0


class GRUFS(Fuse):
    _directories: dict[str, tuple[Path, datetime.datetime]]
    _mountpoint: Path
    _ru_watcher: Thread

    def __init__(self) -> None:
        super().__init__()
        self._directories = {}

    @log_error
    def _read_recent_dirs(self, mountpoint: Path) -> dict[str, tuple[Path, datetime.datetime]]:
        if not RU_PATH.exists():
            return {}

        tree = ET.parse(RU_PATH)
        root = tree.getroot()

        directories = {}

        for bookmark in root.findall("bookmark"):
            href = bookmark.get("href")
            visited = bookmark.get("visited")

            if not href or not visited or not href.startswith("file://"):
                continue

            parent_dir = Path(unquote(href.replace("file://", ""))).parent
            if (
                parent_dir == "/"
                or parent_dir.is_relative_to(mountpoint)
                or not parent_dir.exists()
            ):
                continue

            name = "_".join(parent_dir.parts[-4:][1:][::-1])

            timestamp = datetime.datetime.fromisoformat(visited.replace("Z", "+00:00"))
            if name not in directories or directories[name][1] < timestamp:
                directories[name] = (parent_dir, timestamp)

        return directories

    @log_error
    def fsinit(self) -> None:
        self._mountpoint = Path(cast(str, self.fuse_args.mountpoint))
        self._directories = self._read_recent_dirs(self._mountpoint)
        self._ru_watcher = Thread(target=self._watch_ru_file, name="RU Watcher")
        self._ru_watcher.start()

    @log_error
    def _watch_ru_file(self) -> None:
        inotify = INotify()
        watch_flags = flags.MOVED_TO
        inotify.add_watch(RU_PATH.parent, watch_flags)
        while True:
            ru_modified = False
            for evt in inotify.read():
                if evt.name == RU_PATH.name:
                    ru_modified = True

            if ru_modified:
                self._directories = self._read_recent_dirs(self._mountpoint)

    @log_error
    def getattr(self, path) -> GRUStat | int:
        st = GRUStat()
        if path == "/":
            st.st_mode = stat.S_IFDIR | 0o755
            st.st_nlink = 2
            return st

        p = Path(path)
        if len(p.parts) != 2:
            return -errno.ENOENT

        dir_name = str(p.parts[1])
        if dir_name not in self._directories:
            return -errno.ENOENT

        st.st_mode = stat.S_IFLNK | 0o777
        st.st_nlink = 1
        st.st_size = len(str(self._directories[dir_name][0]))
        st.st_mtime = int(self._directories[dir_name][1].timestamp())
        return st

    @log_error
    def readdir(self, path, _) -> Generator[Direntry, None, int | None]:
        if not path == "/":
            return -errno.ENOENT

        yield Direntry(".", type=stat.S_IFDIR)
        yield Direntry("..", type=stat.S_IFDIR)
        for name in self._directories:
            yield Direntry(name, type=stat.S_IFLNK)

    @log_error
    def readlink(self, path) -> str | int:
        p = Path(path)
        if len(p.parts) != 2:
            return -errno.ENOENT

        dir_name = str(p.parts[1])
        if dir_name in self._directories:
            return str(self._directories[dir_name][0])

        return -errno.ENOENT


def main() -> None:
    server = GRUFS()
    server.parse(errex=1)
    server.main()


if __name__ == "__main__":
    main()
