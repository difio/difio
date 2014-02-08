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

class JavaAPIFilter(Filter):
    """
        Custom Java filter for Pygments.
        Yields only package/class/interface/method definitions.

        See http://cui.unige.ch/isi/bnf/JAVA/BNFindex.html
            https://en.wikipedia.org/wiki/Java_syntax
    """
#    def __init__(self, **options):
#        Filter.__init__(self, **options)

    def filter(self, lexer, stream):
        def_started = False
        open_brackets = 0
        modifiers = [
            "public",
            "private",
            "protected",
            "static",
            "final",
            "native",
            "synchronized",
            "abstract",
            "threadsafe",
            "transient",
            "strictfp"
        ]

        for ttype, value in stream:
                # start of package definition
                # start of decorator definition
                # start of class/interface/method/variable declaration
            if ((ttype is token.Keyword.Namespace) and (value == 'package')) or \
                (ttype is token.Name.Decorator) or  \
                ((ttype is token.Keyword.Declaration) and (value in modifiers)):
                if not def_started:
                    def_started = True
                    yield token.Text, "    " * open_brackets

            if (ttype is token.Operator):
                svalue = value.strip()
                if svalue.startswith('{'): # should be the same as endswith
                    open_brackets += 1
                elif svalue.endswith('{'): # e.g. ){
                    open_brackets += 1
                elif svalue.startswith('}'): # e.g. }, or })
                    open_brackets -= 1
                elif svalue.endswith('}'): # e.g. ;}
                    open_brackets -= 1

            # end of package or variable definition
            if (ttype is token.Operator) and (value == ';') and def_started:
                def_started = False
                yield token.Text, ";\n"

            # end of decorator definition
# NB: @Decorator w/o brackets will not be matched here but will be matched below
# when the method/class definition is complete
            if (ttype is token.Operator) and (value == ')') and def_started:
                def_started = False
                yield token.Text, ")\n"

            # end of class/interface/method declaration
# BUG: this breaks decorators which have curly braces inside them, like
# @Target({ElementType.METHOD, ElementType.TYPE}) - only @Target( is shown
            if (ttype is token.Operator) and (value == '{') and def_started:
                def_started = False
                yield token.Text, "\n"


            if def_started:
                yield ttype, value


if __name__ == "__main__":
    import os
    from pygments import highlight
    from pygments.lexers import JavaLexer
    from pygments.formatters import NullFormatter

    lex = JavaLexer()
    lex.add_filter(JavaAPIFilter())

    for (path, dirs, files) in os.walk('~/repos/git/junit:junit/src/main/java/org/junit'):
        for fname in files:
            f = os.path.join(path, fname)
            if f.endswith("src/main/java/org/junit/Ignore.java"):
                code = open(f, 'r').read()
                print "---------- start %s ----------" % f
                print highlight(code, lex, NullFormatter())
                print "---------- end %s ----------" % f
