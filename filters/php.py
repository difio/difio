#!/usr/bin/env python

################################################################################
#
#   Copyright (c) 2013, Alexander Todorov <atodorov@nospam.dif.io>
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
################################################################################


from pygments import token
from pygments.filter import Filter

class PHPAPIFilter(Filter):
    """
        Custom PHP filter for Pygments.
        Yields only namespace/class/interface/function/const definitions.
    """
#    def __init__(self, **options):
#        Filter.__init__(self, **options)

    def filter(self, lexer, stream):
        def_started = False
        open_brackets = 0
        keywords = [
                    'abstract', 'final',
                    'public', 'protected', 'private',
                    # 'var', # var properties are public but will mess with func variables
                    # and they are bad code anyway
                    'static',
                    'namespace', 'class', 'interface', 'trait', 'function', 'const',
                    ]

        for ttype, value in stream:
            # skip new lines for better formatting
            if (ttype is token.Text) and value.startswith('\n'):
                continue

            if (ttype is token.Keyword) and (value in keywords):
                if not def_started:
                    def_started = True
                    yield token.Text, "    " * open_brackets

            if (ttype is token.Punctuation):
                svalue = value.strip()
                closing_char = False
                if svalue.startswith('{'): # should be the same as endswith
                    open_brackets += 1
                    closing_char = True
                elif svalue.endswith('{'): # e.g. ){
                    open_brackets += 1
                    closing_char = True
                elif svalue.startswith('}'): # e.g. }, or })
                    open_brackets -= 1
                elif svalue.endswith('}'): # e.g. ;}
                    open_brackets -= 1
                elif svalue.endswith(';'): # e.g. ; or array();
                    closing_char = True

                if (closing_char) and def_started:
                    def_started = False
                    # for cases such as array(); - value is ();
                    if len(svalue) > 1:
                        yield token.Text, svalue[:-1]

                    yield token.Text, "\n"

            if def_started:
                yield ttype, value


if __name__ == "__main__":
    import os
    from pygments import highlight
    from pygments.lexers import PhpLexer
    from pygments.formatters import NullFormatter

    lex = PhpLexer(startinline=True)
    lex.add_filter(PHPAPIFilter())

    for (path, dirs, files) in os.walk('~/repos/git/symfony/src'):
        for fname in files:
            f = os.path.join(path, fname)
            if f.endswith(".php"):
                code = open(f, 'r').read()
                print "---------- start %s ----------" % f
                print highlight(code, lex, NullFormatter())
                print "---------- end %s ----------" % f
