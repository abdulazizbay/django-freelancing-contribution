# ext/pygmentplugin.py
# Copyright (C) 2006-2016 the Choco authors and contributors <see AUTHORS file>
#
# This module is part of Choco and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

from pygments.lexers.web import \
    HtmlLexer, XmlLexer, JavascriptLexer, CssLexer
from pygments.lexers.agile import PythonLexer, Python3Lexer
from pygments.lexer import DelegatingLexer, RegexLexer, bygroups, \
    include, using
from pygments.token import \
    Text, Comment, Operator, Keyword, Name, String, Other
from pygments.formatters.html import HtmlFormatter
from pygments import highlight
from choco import compat


class ChocoLexer(RegexLexer):
    name = 'Choco'
    aliases = ['choco']
    filenames = ['*.mao']

    tokens = {
        'root': [
            (r'(\s*)(\%)(\s*end(?:\w+))(\n|\Z)',
             bygroups(Text, Comment.Preproc, Keyword, Other)),
            (r'(\s*)(\%(?!%))([^\n]*)(\n|\Z)',
             bygroups(Text, Comment.Preproc, using(PythonLexer), Other)),
            (r'(\s*)(##[^\n]*)(\n|\Z)',
             bygroups(Text, Comment.Preproc, Other)),
            (r'''(?s)<%doc>.*?</%doc>''', Comment.Preproc),
            (r'(<%)([\w\.\:]+)',
             bygroups(Comment.Preproc, Name.Builtin), 'tag'),
            (r'(</%)([\w\.\:]+)(>)',
             bygroups(Comment.Preproc, Name.Builtin, Comment.Preproc)),
            (r'<%(?=([\w\.\:]+))', Comment.Preproc, 'ondeftags'),
            (r'(<%(?:!?))(.*?)(%>)(?s)',
             bygroups(Comment.Preproc, using(PythonLexer), Comment.Preproc)),
            (r'(\$\{)(.*?)(\})',
             bygroups(Comment.Preproc, using(PythonLexer), Comment.Preproc)),
            (r'''(?sx)
                (.+?)               # anything, followed by:
                (?:
                 (?<=\n)(?=%(?!%)|\#\#) |  # an eval or comment line
                 (?=\#\*) |          # multiline comment
                 (?=</?%) |         # a python block
                                    # call start or end
                 (?=\$\{) |         # a substitution
                 (?<=\n)(?=\s*%) |
                                    # - don't consume
                 (\\\n) |           # an escaped newline
                 \Z                 # end of string
                )
            ''', bygroups(Other, Operator)),
            (r'\s+', Text),
        ],
        'ondeftags': [
            (r'<%', Comment.Preproc),
            (r'(?<=<%)(include|inherit|namespace|page)', Name.Builtin),
            include('tag'),
        ],
        'tag': [
            (r'((?:\w+)\s*=)\s*(".*?")',
             bygroups(Name.Attribute, String)),
            (r'/?\s*>', Comment.Preproc, '#pop'),
            (r'\s+', Text),
        ],
        'attr': [
            ('".*?"', String, '#pop'),
            ("'.*?'", String, '#pop'),
            (r'[^\s>]+', String, '#pop'),
        ],
    }


class ChocoHtmlLexer(DelegatingLexer):
    name = 'HTML+Choco'
    aliases = ['html+choco']

    def __init__(self, **options):
        super(ChocoHtmlLexer, self).__init__(HtmlLexer, ChocoLexer,
                                            **options)


class ChocoXmlLexer(DelegatingLexer):
    name = 'XML+Choco'
    aliases = ['xml+choco']

    def __init__(self, **options):
        super(ChocoXmlLexer, self).__init__(XmlLexer, ChocoLexer,
                                           **options)


class ChocoJavascriptLexer(DelegatingLexer):
    name = 'JavaScript+Choco'
    aliases = ['js+choco', 'javascript+choco']

    def __init__(self, **options):
        super(ChocoJavascriptLexer, self).__init__(JavascriptLexer,
                                                  ChocoLexer, **options)


class ChocoCssLexer(DelegatingLexer):
    name = 'CSS+Choco'
    aliases = ['css+choco']

    def __init__(self, **options):
        super(ChocoCssLexer, self).__init__(CssLexer, ChocoLexer,
                                           **options)


pygments_html_formatter = HtmlFormatter(cssclass='syntax-highlighted',
                                        linenos=True)


def syntax_highlight(filename='', language=None):
    choco_lexer = ChocoLexer()
    if compat.py3k:
        python_lexer = Python3Lexer()
    else:
        python_lexer = PythonLexer()
    if filename.startswith('memory:') or language == 'choco':
        return lambda string: highlight(string, choco_lexer,
                                        pygments_html_formatter)
    return lambda string: highlight(string, python_lexer,
                                    pygments_html_formatter)
