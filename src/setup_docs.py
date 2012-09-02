#!/usr/bin/python
#
#    Use, distribution, and modification of the DRO Trimmer binaries, source code,
#    or documentation, is subject to the terms of the MIT license, as below.
#
#    Copyright (c) 2008 - 2012 Laurence Dougal Myers
#
#    Permission is hereby granted, free of charge, to any person obtaining a copy
#    of this software and associated documentation files (the "Software"), to deal
#    in the Software without restriction, including without limitation the rights
#    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#    copies of the Software, and to permit persons to whom the Software is
#    furnished to do so, subject to the following conditions:
#
#    The above copyright notice and this permission notice shall be included in
#    all copies or substantial portions of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#    THE SOFTWARE.
from __future__ import with_statement
import codecs
import datetime
import os
import sys
from creole import creole2html
import dro_globals as app_globals

in_wiki_file_name = "Home.wiki"
template_file_name = "doc_template.html"
output_file_name = "readme.html"

def main():
    if len(sys.argv) < 5:
        print "Insufficient arguments, please pass the input directory, the template directory, the output directory, and the documnent source URL."
        return 1
    try:
        in_dir = sys.argv[1]
        template_dir = sys.argv[2]
        out_dir = sys.argv[3]
        generated_source = sys.argv[4]

        generated_date = datetime.datetime.now().strftime("%d %b %Y, %H:%M:%S")
        
        with codecs.open(os.path.join(in_dir, in_wiki_file_name), 'r', 'utf-8') as in_file:
            creole_text = in_file.read()
        html_body = creole2html(creole_text)

        with file(os.path.join(template_dir, template_file_name), 'r') as template_file:
            html_output = template_file.read()
        html_output = html_output.format(
            title=app_globals.g_app_name + " " + app_globals.g_app_version,
            body=html_body,
            generated_date=generated_date,
            generated_source=generated_source)

        if not os.path.isdir(out_dir):
            os.mkdir(out_dir)
        with file(os.path.join(out_dir, output_file_name), 'w') as output_file:
            output_file.write(html_output)

        print "Successfully converted Creole wiki page {} to {} using template {}".format(
            in_wiki_file_name,
            output_file_name,
            template_file_name
        )

    except Exception, e:
        print e
        return 2

    return 0

if __name__ == "__main__": sys.exit(main())

