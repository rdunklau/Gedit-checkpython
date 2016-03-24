import abc
import ast
import pep8

import re

import sys
from io import StringIO

from pyflakes import checker as flakeschecker


class ErrTypes(object):
    pass

ERROR = ErrTypes()
WARNING = ErrTypes()
STYLE = ErrTypes()

rePEP8 = re.compile(r'([^:]*):(\d*):(\d*): (\w\d*) (.*)')


class Message(object):

    def __init__(self, err_type, err_code, line, message, col=0):
        self.err_type = err_type
        self.err_code = err_code
        self.line = line
        self.message = message


class PyChecker(object):
    """Abstract base class for python code checkers."""

    __metacls__ = abc.ABCMeta

    @abc.abstractmethod
    def check(self, name, content):
        """Performs the actual check.

        name: A buffer name
        content: the content to check.

        returns a list of messages instances
        """
        pass

    def check_by_filename(self, filename):
        yield from self.check(
            filename,
            open(filename, 'r').read()
        )

    def check_list_of_files(self, filelist):
        for filename in filelist:
            for message in self.check_by_filename(filename):
                yield filename, message


class Pep8Checker(PyChecker):
    """A checker for the Pep8."""

    def __init__(self, ignore=[]):
        self.options = pep8.StyleGuide(config_file=True).options
        self.options.ignore += tuple(ignore)

    def check(self, name, content):
        lines = content.splitlines(True)
        # workaround - gedit always adds \n to the last line on save
        if content.endswith('\n'):
            lines.append('')
        else:
            lines[-1] = lines[-1] + '\n'
        # issue #6 - skip noqa
        lines = [
            line if not (
                line.strip().endswith('# noqa')
                or line.strip().endswith('# flake8: noqa')
            ) else '#'
            for line in lines
        ]
        old_stderr, sys.stderr = sys.stderr, StringIO()
        old_stdout, sys.stdout = sys.stdout, StringIO()
        try:
            pep8.Checker(name, lines=lines, options=self.options).check_all()
        except:
            pass
        finally:
            sys.stderr = old_stderr
            sys.stdout, result = old_stdout, sys.stdout
        result.seek(0)
        errors = [
            rePEP8.match(line)
            for line in result.readlines()
            if line
        ]
        errors = [e for e in errors if e]
        for match in sorted(errors, key=lambda x: x.group(2)):
            lineno = int(match.group(2))
            text = match.group(5)
            col = int(match.group(3) or -1)
            err_type = match.group(4)
            yield Message(STYLE, err_type, lineno, text, col=col)


class PyFlakesChecker(PyChecker):
    """A pyflakes checker."""

    def check(self, name, content):
        old_stderr, sys.stderr = sys.stderr, StringIO()
        content = content + '\n'
        try:
            tree = ast.parse(content, name)
        except:
            try:
                value = sys.exc_info()[1]
                lineno, offset = value.args[1][1:3]
            except IndexError:
                lineno, offset = 1, 0
            yield Message(ERROR, 'E', lineno, str(value), offset)
        else:
            messages = flakeschecker.Checker(tree, name).messages
            for w in messages:
                yield Message(
                    ERROR,
                    'E',
                    w.lineno,
                    '%s' % (w.message % w.message_args),
                    getattr(w, 'col', 0)
                )
        finally:
            sys.stderr = old_stderr


class AllCheckers(PyChecker):

    def __init__(self, pep8ignore=[]):
        self.checkers = [
            Pep8Checker(ignore=list(pep8ignore)),
            PyFlakesChecker(),
        ]

    def check(self, name, content):
        for checker in self.checkers:
            yield from checker.check(name, content)
