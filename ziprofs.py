#!/usr/bin/env python3
from __future__ import print_function, absolute_import, division

import logging

from errno import EACCES
from os.path import realpath
from sys import argv, exit
from threading import Lock

import errno
import logging
import os
import zipfile
import stat

from fusepy import FUSE, FuseOSError, Operations, LoggingMixIn, S_IFDIR
from collections import OrderedDict


class CachedZipFactory(object):
    MAX_CACHE_SIZE=100
    cache = OrderedDict()
    log = logging.getLogger('ziprofs.cache')

    def _cleanup(self, zf: object):
        zf.close()
        del zf

    def _add(self, path: str):
        if path in self.cache:
            return
        if len(self.cache) == self.MAX_CACHE_SIZE:
            oldkey, oldvalue = self.cache.popitem(last=False)
            self.log.debug('Popping cache entry: %s', oldkey)
            self._cleanup(oldvalue[1])
        mtime = os.lstat(path).st_mtime
        self.log.debug("Caching path (%s:%s)", path, mtime)
        self.cache[path] = (mtime, zipfile.ZipFile(path))

    def get(self, path: str) -> object:
        if path in self.cache:
            self.cache.move_to_end(path)
            mtime = os.lstat(path).st_mtime
            if mtime > self.cache[path][0]:
                oldvalue = self.cache.pop(path)
                self._cleanup(oldvalue[1])
                self._add(path)
        else:
            self._add(path)
        return self.cache[path][1]


class ZipROFS(LoggingMixIn, Operations):
    zip_factory = CachedZipFactory()

    def __init__(self, root):
        self.root = realpath(root)
        self.rwlock = Lock()

    def __call__(self, op, path, *args):
        return super(ZipROFS, self).__call__(op, self.root + path, *args)

    @staticmethod
    def get_zip_path(path: str) -> str:
        parts = []
        head, tail = os.path.split(path)
        while tail:
            parts.append(tail)
            head, tail = os.path.split(head)
        parts.reverse()
        cur_path = '/'
        for part in parts:
            cur_path = os.path.join(cur_path, part)
            if zipfile.is_zipfile(cur_path):
                return cur_path
        return None

    def access(self, path, mode):
        if not os.access(path, mode):
            raise FuseOSError(EACCES)

    def getattr(self, path, fh=None):
        zip_path = self.get_zip_path(path)
        self.log.debug('zip path: %s', zip_path)
        st = os.lstat(zip_path) if zip_path else os.lstat(path)
        result = {key: getattr(st, key) for key in ('st_atime', 'st_ctime',
            'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid')}
        if zip_path == path:
            result['st_mode'] = S_IFDIR | (result['st_mode'] & 0o555)
        elif zip_path:
            zf = self.zip_factory.get(zip_path)
            subpath = path[len(zip_path)+1:]
            try:
                info = zf.getinfo(subpath)
                result['st_size'] = info.file_size
                result['st_mode'] = stat.S_IFREG | 0o555
            except KeyError:
                # check if it is a valid subdirectory
                infolist = zf.infolist()
                found = False
                for info in infolist:
                    if info.filename.find(subpath + '/') == 0:
                        found = True
                if found:
                    result['st_mode'] = S_IFDIR | 0o555
                else:
                    raise FuseOSError(errno.ENOENT)
        return result

    getxattr = None

    listxattr = None

    open = os.open

    def read(self, path, size, offset, fh):
        with self.rwlock:
            os.lseek(fh, offset, 0)
            return os.read(fh, size)

    def readdir(self, path, fh):
        zip_path = self.get_zip_path(path)
        if not zip_path:
            return ['.', '..'] + os.listdir(path)
        subpath = path[len(zip_path)+1:]
        zf = self.zip_factory.get(zip_path)
        infolist = zf.infolist()

        result = ['.', '..']
        subdirs = set()
        for info in infolist:
            self.log.debug(info.filename)
            if info.filename.find(subpath) == 0 and info.filename > subpath:
                suffix = info.filename[len(subpath)+1 if subpath else 0:]
                if not suffix:
                    continue
                if '/' not in suffix:
                    result.append(suffix)
                    self.log.debug("adding %s", suffix)
                else:
                    subdirs.add(suffix[:suffix.find('/')])
                    self.log.debug("adding %s", suffix[:suffix.find('/')])
        result.extend(subdirs)
        return result


    def release(self, path, fh):
        return os.close(fh)

    def statfs(self, path):
        stv = os.statvfs(path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    utimens = os.utime


if __name__ == '__main__':
    if len(argv) != 3:
        print('usage: %s <root> <mountpoint>' % argv[0])
        exit(1)
    logging.basicConfig(level=logging.DEBUG)

    fuse = FUSE(ZipROFS(argv[1]), argv[2], foreground=True)
