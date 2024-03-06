# choco/lexer.py
# Copyright (C) 2006-2016 the Choco authors and contributors <see AUTHORS file>
#
# This module is part of Choco and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

"""provides the Lexer class for parsing template strings into parse trees."""

import re
import codecs
from choco import nodes, errors, compat
from choco.pygen import adjust_whitespace

_regexp_cache = {}


class Lexer(object):

    def __init__(self, text, filename=None,
                 disable_unicode=False,
                 input_encoding=None, preprocessor=None):
        self.text = text
        self.filename = filename
        self.template = nodes.TemplateNode(self.filename)
        self.matched_lineno = 1
        self.matched_charpos = 0
        self.lineno = 1
        self.match_position = 0
        self.tag = []
        self.control_line = []
        self.ternary_stack = []
        self.disable_unicode = disable_unicode
        self.encoding = input_encoding

        if compat.py3k and disable_unicode:
            raise errors.UnsupportedError(
                "Choco for Python 3 does not "
                "support disabling Unicode")

        if preprocessor is None:
            self.preprocessor = []
        elif not hasattr(preprocessor, '__iter__'):
            self.preprocessor = [preprocessor]
        else:
            self.preprocessor = preprocessor

    @property
    def exception_kwargs(self):
        return {'source': self.text,
                'lineno': self.matched_lineno,
                'pos': self.matched_charpos,
                'filename': self.filename}

    def match(self, regexp, flags=None):
        """compile the given regexp, cache the reg, and call match_reg()."""

        try:
            reg = _regexp_cache[(regexp, flags)]
        except KeyError:
            if flags:
                reg = re.compile(regexp, flags)
            else:
                reg = re.compile(regexp)
            _regexp_cache[(regexp, flags)] = reg

        return self.match_reg(reg)

    def match_reg(self, reg):
        """match the given regular expression object to the current text
        position.

        if a match occurs, update the current text and line position.

        """

        mp = self.match_position

        match = reg.match(self.text, self.match_position)
        if match:
            (start, end) = match.span()
            if end == start:
                self.match_position = end + 1
            else:
                self.match_position = end
            self.matched_lineno = self.lineno
            lines = re.findall(r"\n", self.text[mp:self.match_position])
            cp = mp - 1
            while (cp >= 0 and cp < self.textlength and self.text[cp] != '\n'):
                cp -= 1
            self.matched_charpos = mp - cp
            self.lineno += len(lines)
            # print "MATCHED:", match.group(0), "LINE START:",
            # self.matched_lineno, "LINE END:", self.lineno
        # print "MATCH:", regexp, "\n", self.text[mp : mp + 15], \
        #          (match and "TRUE" or "FALSE")
        return match

    def parse_until_text(self, watch_nesting, *text):
        startpos = self.match_position
        text_re = r'|'.join(text)
        brace_level = 0
        paren_level = 0
        bracket_level = 0
        while True:
            match = self.match(r'#.*\n')
            if match:
                continue
            match = self.match(r'(\"\"\"|\'\'\'|\"|\')[^\\]*?(\\.[^\\]*?)*\1',
                               re.S)
            if match:
                continue
            match = self.match(r'(%s)' % text_re)
            if match and not (watch_nesting
                              and (brace_level > 0 or paren_level > 0
                                   or bracket_level > 0)):
                return \
                    self.text[startpos:
                              self.match_position - len(match.group(1))],\
                    match.group(1)
            elif not match:
                match = self.match(r"(.*?)(?=\"|\'|#|%s)" % text_re, re.S)
            if match:
                brace_level += match.group(1).count('{')
                brace_level -= match.group(1).count('}')
                paren_level += match.group(1).count('(')
                paren_level -= match.group(1).count(')')
                bracket_level += match.group(1).count('[')
                bracket_level -= match.group(1).count(']')
                continue
            raise errors.SyntaxException(
                "Expected: %s" %
                ','.join(text),
                **self.exception_kwargs)

    def append_node(self, nodecls, *args, **kwargs):
        kwargs.setdefault('source', self.text)
        kwargs.setdefault('lineno', self.matched_lineno)
        kwargs.setdefault('pos', self.matched_charpos)
        kwargs['filename'] = self.filename
        node = nodecls(*args, **kwargs)
        if len(self.tag):
            self.tag[-1].nodes.append(node)
        else:
            self.template.nodes.append(node)
        # build a set of child nodes for the control line
        # (used for loop variable detection)
        # also build a set of child nodes on ternary control lines
        # (used for determining if a pass needs to be auto-inserted
        if self.control_line:
            control_frame = self.control_line[-1]
            control_frame.nodes.append(node)
            if not (isinstance(node, nodes.ControlLine) and
                    control_frame.is_ternary(node.keyword)):
                if self.ternary_stack and self.ternary_stack[-1]:
                    self.ternary_stack[-1][-1].nodes.append(node)
        if isinstance(node, nodes.Tag):
            if len(self.tag):
                node.parent = self.tag[-1]
            self.tag.append(node)
        elif isinstance(node, nodes.ControlLine):
            if node.isend:
                self.control_line.pop()
                self.ternary_stack.pop()
            elif node.is_primary:
                self.control_line.append(node)
                self.ternary_stack.append([])
            elif self.control_line and \
                    self.control_line[-1].is_ternary(node.keyword):
                self.ternary_stack[-1].append(node)
            elif self.control_line and \
                    not self.control_line[-1].is_ternary(node.keyword):
                raise errors.SyntaxException(
                    "Keyword '%s' not a legal ternary for keyword '%s'" %
                    (node.keyword, self.control_line[-1].keyword),
                    **self.exception_kwargs)

    _CODING_RE = re.compile(r'#.*coding[:=]\s*([-\w.]+).*\r?\n')

    def decode_raw_stream(self, text, decode_raw, known_encoding, filename):
        """given string/unicode or bytes/string, determine encoding
           from magic encoding comment, return body as unicode
           or raw if decode_raw=False

        """
        if isinstance(text, compat.text_type):
            m = self._CODING_RE.match(text)
            encoding = m and m.group(1) or known_encoding or 'ascii'
            return encoding, text

        if text.startswith(codecs.BOM_UTF8):
            text = text[len(codecs.BOM_UTF8):]
            parsed_encoding = 'utf-8'
            m = self._CODING_RE.match(text.decode('utf-8', 'ignore'))
            if m is not None and m.group(1) != 'utf-8':
                raise errors.CompileException(
                    "Found utf-8 BOM in file, with conflicting "
                    "magic encoding comment of '%s'" % m.group(1),
                    text.decode('utf-8', 'ignore'),
                    0, 0, filename)
        else:
            m = self._CODING_RE.match(text.decode('utf-8', 'ignore'))
            if m:
                parsed_encoding = m.group(1)
            else:
                parsed_encoding = known_encoding or 'ascii'

        if decode_raw:
            try:
                text = text.decode(parsed_encoding)
            except UnicodeDecodeError:
                raise errors.CompileException(
                    "Unicode decode operation of encoding '%s' failed" %
                    parsed_encoding,
                    text.decode('utf-8', 'ignore'),
                    0, 0, filename)

        return parsed_encoding, text

    def parse(self):
        self.encoding, self.text = self.decode_raw_stream(
            self.text,
            not self.disable_unicode,
            self.encoding,
            self.filename)

        for preproc in self.preprocessor:
            self.text = preproc(self.text)

        # push the match marker past the
        # encoding comment.
        self.match_reg(self._CODING_RE)

        self.textlength = len(self.text)

        while (True):
            if self.match_position > self.textlength:
                break

            if self.match_end():
                break
            if self.match_expression():
                continue
            if self.match_control_line():
                continue
            if self.match_comment():
                continue
            if self.match_tag_start():
                continue
            if self.match_tag_end():
                continue
            if self.match_ui_tag():
                continue
            if self.match_python_block():
                continue
            if self.match_text():
                continue

            if self.match_position > self.textlength:
                break
            raise errors.CompileException("assertion failed")

        if len(self.tag):
            raise errors.SyntaxException("Unclosed tag: <%%%s>" %
                                             self.tag[-1].keyword,
                                             **self.exception_kwargs)
        if len(self.control_line):
            raise errors.SyntaxException(
                "Unterminated control keyword: '%s'" %
                self.control_line[-1].keyword,
                self.text,
                self.control_line[-1].lineno,
                self.control_line[-1].pos, self.filename)
            
        return self.template

    def match_tag_start(self):
        match = self.match(r'''
            \<%     # opening tag

            ([\w\.\:]+)   # keyword

            ((?:\s+\w+|\s*=\s*|".*?"|'.*?')*)  # attrname, = \
                                               #        sign, string expression

            \s*     # more whitespace

            (/)?>   # closing

            ''',

                           re.I | re.S | re.X)

        if match:
            keyword, attr, isend = match.groups()
            self.keyword = keyword
            attributes = {}
            if attr:
                for att in re.findall(
                        r"\s*(\w+)\s*=\s*(?:'([^']*)'|\"([^\"]*)\")", attr):
                    key, val1, val2 = att
                    text = val1 or val2
                    text = text.replace('\r\n', '\n')
                    attributes[key] = text
            self.append_node(nodes.Tag, keyword, attributes)
            if isend:
                self.tag.pop()
            else:
                if keyword == 'text':
                    match = self.match(r'(.*?)(?=\</%text>)', re.S)
                    if not match:
                        raise errors.SyntaxException(
                            "Unclosed tag: <%%%s>" %
                            self.tag[-1].keyword,
                            **self.exception_kwargs)
                    self.append_node(nodes.Text, match.group(1))
                    return self.match_tag_end()
            return True
        else:
            return False

    def match_tag_end(self):
        match = self.match(r'\</%[\t ]*(.+?)[\t ]*>')
        if match:
            if not len(self.tag):
                raise errors.SyntaxException(
                    "Closing tag without opening tag: </%%%s>" %
                    match.group(1),
                    **self.exception_kwargs)
            elif self.tag[-1].keyword != match.group(1):
                raise errors.SyntaxException(
                    "Closing tag </%%%s> does not match tag: <%%%s>" %
                    (match.group(1), self.tag[-1].keyword),
                    **self.exception_kwargs)
            self.tag.pop()
            return True
        else:
            return False

    def match_end(self):
        match = self.match(r'\Z', re.S)
        if match:
            string = match.group()
            if string:
                return string
            else:
                return True
        else:
            return False

    def match_text(self):
        match = self.match(r"""
                (.*?)         # anything, followed by:
                (
                 (?<=\n)(?=[ \t]*(?=%|\#\#)) # an eval or line-based
                                             # comment preceded by a
                                             # consumed newline and whitespace
                 |
                 (?=\${)      # an expression
                 |
                 (?=</?[%&])  # a substitution or block or call start or end
                              # - don't consume
                 |
                 (\\\r?\n)    # an escaped newline  - throw away
                 |
                 \Z           # end of string
                )""", re.X | re.S)

        if match:
            text = match.group(1)
            if text:
                self.append_node(nodes.Text, text)
            return True
        else:
            return False

    def match_python_block(self):
        match = self.match(r"<%(!)?")
        if match:
            line, pos = self.matched_lineno, self.matched_charpos
            text, end = self.parse_until_text(False, r'%>')
            # the trailing newline helps
            # compiler.parse() not complain about indentation
            text = adjust_whitespace(text) + "\n"
            self.append_node(
                nodes.Code,
                text,
                match.group(1) == '!', lineno=line, pos=pos)
            return True
        else:
            return False



    VAR_REGEX = re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*?')

    def match_ui_tag(self):
        match = self.match(r"<%(@)")
        if match:
            line, pos = self.matched_lineno, self.matched_charpos
            text, end = self.parse_until_text(False, r'/>')
            # the trailing newline helps
            # compiler.parse() not complain about indentation
            text = text.strip()
            parts = text.split("(", 1)
            ui_name = parts[0]
            ui_args = parts[1][:-1]

            if not self.VAR_REGEX.match(ui_name):
                raise errors.SyntaxException(
                            "ui name '%s' is invalid!" %
                            (ui_name,),
                            **self.exception_kwargs)

            self.append_node(
                nodes.Ui,
                text, ui_name, ui_args, lineno=line, pos=pos)
            return True
        else:
            return False

    def match_expression(self):
        match = self.match(r"\${")
        if match:
            line, pos = self.matched_lineno, self.matched_charpos
            text, end = self.parse_until_text(True, r'\|', r'}')
            if end == '|':
                escapes, end = self.parse_until_text(True, r'}')
            else:
                escapes = ""
            text = text.replace('\r\n', '\n')
            self.append_node(
                nodes.Expression,
                text, escapes.strip(),
                lineno=line, pos=pos)
            return True
        else:
            return False

    def match_control_line(self):
        match = self.match(
            r"(?<=^)[\t ]*(%(?!%)|##)[\t ]*((?:(?:\\r?\n)|[^\r\n])*)"
            r"(?:\r?\n|\Z)", re.M)
        if match:
            operator = match.group(1)
            text = match.group(2)
            if operator == '%':
                m2 = re.match(r'(end)?(\w+)\s*(.*)', text)
                if not m2:
                    raise errors.SyntaxException(
                        "Invalid control line: '%s'" %
                        text,
                        **self.exception_kwargs)
                isend, keyword = m2.group(1, 2)
                isend = (isend is not None)

                if isend:
                    if not len(self.control_line):
                        raise errors.SyntaxException(
                            "No starting keyword '%s' for '%s'" %
                            (keyword, text),
                            **self.exception_kwargs)
                    elif self.control_line[-1].keyword != keyword:
                        raise errors.SyntaxException(
                            "Keyword '%s' doesn't match keyword '%s'" %
                            (text, self.control_line[-1].keyword),
                            **self.exception_kwargs)
                self.append_node(nodes.ControlLine, keyword, isend, text)
            else:
                self.append_node(nodes.Comment, text)
            return True
        else:
            return False

    def match_comment(self):
        """matches the multiline version of a comment"""
        match = self.match(r"<%doc>(.*?)</%doc>", re.S)
        if match:
            self.append_node(nodes.Comment, match.group(1))
            return True
        else:
            return False
