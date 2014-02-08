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

class PythonAPIFilter(Filter):
    """
        Custom Python filter for Pygments.
        Yields only class/def definitions and decorators
    """
#    def __init__(self, **options):
#        Filter.__init__(self, **options)

    def filter(self, lexer, stream):
        def_started = False
        decorator_started = False
        seen_def = False
        indents = []

        for ttype, value in stream:

            # save leading indents
            if (ttype is token.Text) and (not def_started) and (not decorator_started):
                if (value != "\n"):
                    indents.append((ttype, value))
                else:
                    indents = []

            if (ttype is token.Name.Decorator) and (not decorator_started):
                decorator_started = True
                if seen_def:
                    yield token.Text, "\n"

                if (not indents) and seen_def:
                    yield token.Text, "\n"

                for t, v in indents:
                    yield t, v
                indents = []

                seen_def = True # print leading new lines


            if (ttype is token.Keyword) and (value in ['def', 'class']):
                    def_started = True
                    if not decorator_started:
                        # output leading idents and new lines
                        # only if first definition is already printed
                        if seen_def:
                            yield token.Text, "\n"

                        if (not indents) and seen_def:
                            yield token.Text, "\n"

                    decorator_started = False

                    for t, v in indents:
                        yield t, v
                    indents = []

                    seen_def = True # print leading new lines

            if def_started or decorator_started:
                yield ttype, value

            if  (ttype is token.Punctuation) and (value == ':'):
                def_started = False

if __name__ == "__main__":
    from pygments import highlight
    from pygments.lexers import PythonLexer
    from pygments.formatters import NullFormatter

    lex = PythonLexer()
    lex.add_filter(PythonAPIFilter())

    for f in [__file__, "../views.py", '../admin.py']:
        code = open(f, 'r').read()
        print "---------- %s ----------" % f
        print highlight(code, lex, NullFormatter())
