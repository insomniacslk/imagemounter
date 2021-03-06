# -*- coding: utf-8 -*-
import argparse
import cmd
import logging
import os
import shlex

from imagemounter import __version__, DISK_MOUNTERS
from imagemounter.cli import CheckAction, ImageMounterFormatter, get_coloring_func
from imagemounter.disk import Disk
from imagemounter.parser import ImageParser


class ShellArgumentParser(argparse.ArgumentParser):
    _exit = False

    def exit(self, status=0, message=None):
        if message:
            self._print_message(message)
        raise Exception()  # stop the loop and lookup.


class ArgumentParsedShell(cmd.Cmd):
    def __init__(self):
        cmd.Cmd.__init__(self)
        self._make_argparser()

    def _make_argparser(self):
        """Makes a new argument parser."""
        self.argparser = ShellArgumentParser(prog='')
        subparsers = self.argparser.add_subparsers()

        for name in self.get_names():
            if name.startswith('parser_'):
                parser = subparsers.add_parser(name[7:])
                parser.set_defaults(func=getattr(self, 'arg_' + name[7:]))
                getattr(self, name)(parser)

        self.argparser_completer = None

        try:
            import argcomplete
        except ImportError:
            pass
        else:
            os.environ.setdefault("_ARGCOMPLETE_COMP_WORDBREAKS", " \t\"'")
            self.argparser_completer = argcomplete.CompletionFinder(self.argparser)

    def postcmd(self, stop, line):
        self._make_argparser()  # load argparser again to reload options
        return stop

    def complete(self, text, state):
        """Overridden to reset the argument parser after every completion (argcomplete fails :()"""
        result = cmd.Cmd.complete(self, text, state)
        if self.argparser_completer:
            self._make_argparser()
            # argparser screws up with internal states, this is the best way to fix it for now
        return result

    def default(self, line):
        """Overriding default to get access to any argparse commands we have specified."""

        if any((line.startswith(x) for x in self.argparse_names())):
            try:
                args = self.argparser.parse_args(shlex.split(line))
            except Exception:  # intentionally catches also other errors in argparser
                pass
            else:
                args.func(args)
        else:
            cmd.Cmd.default(self, line)

    def completedefault(self, text, line, begidx, endidx):
        """Accessing the argcompleter if available."""
        if self.argparser_completer and any((line.startswith(x) for x in self.argparse_names())):
            self.argparser_completer.rl_complete(line, 0)
            return [x[begidx:] for x in self.argparser_completer._rl_matches]
        else:
            return []

    def argparse_names(self, prefix=""):
        return [a[4:] for a in self.get_names() if a.startswith("arg_" + prefix)]

    def completenames(self, text, *ignored):
        """Patched to also return argparse commands"""
        return sorted(cmd.Cmd.completenames(self, text, *ignored) + self.argparse_names(text))

    def do_help(self, arg):
        """Patched to show help for arparse commands"""
        if not arg or arg not in self.argparse_names():
            cmd.Cmd.do_help(self, arg)
        else:
            try:
                self.argparser.parse_args([arg, '--help'])
            except Exception:
                pass

    def print_topics(self, header, cmds, cmdlen, maxcol):
        """Patched to show all argparse commands as being documented"""
        if header == self.doc_header:
            cmds.extend(self.argparse_names())
        cmd.Cmd.print_topics(self, header, sorted(cmds), cmdlen, maxcol)


class ImageMounterShell(ArgumentParsedShell):
    prompt = '(imount) '
    file = None
    parser = None

    def preloop(self):
        self.stdout.write("Welcome to imagemounter {version}".format(version=__version__))
        self.stdout.write("\n")
        self.parser = ImageParser()

    def error(self, error):
        self.stdout.write('*** %s\n' % error)

    def parser_disk(self, parser):
        parser.description = "Add a disk to the current parser"
        p = parser.add_argument('path', help='path to the disk image that you want to mount')
        try:
            from argcomplete.completers import FilesCompleter
            p.completer = FilesCompleter([".dd", ".e01", ".aff", ".DD", ".E01", ".AFF"])
        except ImportError:
            pass
        parser.add_argument("--mounter", choices=DISK_MOUNTERS, help="the method to mount with")

    def arg_disk(self, args):
        if not os.path.exists(args.path):
            return self.error("The path {path} does not exist".format(path=args.path))
        disk = self.parser.add_disk(args.path, disk_mounter=args.mounter)
        disk.mount()
        for _ in disk.detect_volumes():
            pass
        print("Added {path} to the image mounter as index {index}".format(path=args.path, index=disk.index))

    def _get_all_indexes(self):
        if self.parser:
            return [v.index for v in self.parser.get_volumes()] + [d.index for d in self.parser.disks]
        else:
            return None

    def parser_mount(self, parser):
        parser.description = "Mount a volume by its index"
        parser.add_argument('index', help='volume index', choices=self._get_all_indexes())
        parser.add_argument('-r', '--recursive', action='store_true')

    def arg_mount(self, args):
        col = get_coloring_func()
        volume_or_disk = self.parser.get_by_index(args.index)
        volume, disk = (volume_or_disk, None) if not isinstance(volume_or_disk, Disk) else (None, volume_or_disk)

        if not args.recursive:
            if disk and not disk.is_mounted:
                try:
                    disk.mount()
                except Exception as e:
                    pass
            else:
                try:
                    volume.init_volume()
                    if volume.mountpoint:
                        print("Mounted volume {index} at {path}"
                              .format(path=col(volume.mountpoint, "green", attrs=['bold']),
                                      index=volume.index))
                    else:
                        print("Mounted volume {index} (no mountpoint available)".format(index=volume.index))
                except Exception as e:
                    import traceback ; traceback.print_exc()
                    print(col("An error occurred while mounting volume {index}: {type}: {args}"
                              .format(type=type(e).__name__,
                                      args=" ".join(map(str, e.args)),
                                      index=volume.index), "red"))
        else:
            if disk:
                it = disk.init_volumes
            else:
                it = volume.init
            for v in it():
                if v.mountpoint:
                    print("Mounted volume {index} at {path}"
                          .format(path=col(v.mountpoint, "green", attrs=['bold']),
                                  index=v.index))
                elif v.exception:
                    e = v.exception
                    print(col("An error occurred while mounting volume {index}: {type}: {args}"
                              .format(type=type(e).__name__,
                                      args=" ".join(map(str, e.args)),
                                      index=v.index), "red"))

    def parser_unmount(self, parser):
        parser.description = "Unmount a volume by its index"
        parser.add_argument('index', help='volume index', nargs='?', choices=self._get_all_indexes())

    def arg_unmount(self, args):
        if args.index:
            volume = self.parser.get_by_index(args.index)
            volume.unmount()
            print("Unmounted {index}".format(index=volume.index))
        else:
            self.parser.clean()
            print("Unmounted everything")

    def do_show(self, args):
        col = get_coloring_func()
        for disk in self.parser.disks:
            print("- {index:<5}  {type} {filename}"
                  .format(index=col("{:<5}".format(disk.index), 'green' if disk.is_mounted else None, attrs=['bold']),
                          type=col("{:<10}".format(disk.volumes.vstype), attrs=['dark']),
                          filename=disk.paths[0]))

            def _show_volume_system(volumes, level=0):
                level += 1
                for i, v in enumerate(volumes):
                    level_str = "  "*level + ("└ " if i == len(volumes)-1 else "├ ")
                    tp = v.volumes.vstype if v.fstype == 'volumesystem' else v.fstype if v.flag == 'alloc' else v.flag

                    print("{level_str}{index}  {type} {size:<10}  {description}"
                          .format(level_str=level_str,
                                  index=col("{:<5}".format(v.index), 'green' if v.is_mounted else None, attrs=['bold']),
                                  type=col("{:<10}".format(tp), attrs=['dark']),
                                  description=v.get_description(with_index=False, with_size=False)[:30],
                                  size=v.get_formatted_size()))
                    _show_volume_system(v.volumes, level)

            _show_volume_system(disk.volumes)

    def do_quit(self, arg):
        """Quits the program."""
        return True


def main():
    parser = argparse.ArgumentParser(description='Shell to mount disk images locally.')
    parser.add_argument('--version', action='version', version=__version__, help='display version and exit')
    parser.add_argument('--check', action=CheckAction, nargs=0,
                        help='do a system check and list which tools are installed')
    parser.add_argument('-v', '--verbose', action='count', default=False, help='enable verbose output')

    args = parser.parse_args()
    col = get_coloring_func()

    handler = logging.StreamHandler()
    handler.setFormatter(ImageMounterFormatter(col, verbosity=args.verbose))
    logger = logging.getLogger("imagemounter")
    logger.setLevel({0: logging.CRITICAL, 1: logging.WARNING, 2: logging.INFO}.get(args.verbose, logging.DEBUG))
    logger.addHandler(handler)

    shell = ImageMounterShell()
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
