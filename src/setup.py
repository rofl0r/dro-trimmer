#!/usr/bin/python
#
#    Use, distribution, and modification of the DRO Trimmer binaries, source code,
#    or documentation, is subject to the terms of the MIT license, as below.
#
#    Copyright (c) 2008 - 2013 Laurence Dougal Myers
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


from distutils.core import setup
import os
import py2exe
import dro_globals

# includes for py2exe
includes=[]

opts = { 'py2exe': { 
    'includes':includes,
    "dll_excludes": ["MSVCP90.dll"]
} }

def convert_version(in_version):
    ver_bits = [v[1:] for v in in_version.split()]
    if len(ver_bits) == 2:
        ver_bits.append("0")
    return '.'.join(ver_bits)

setup(version = convert_version(dro_globals.g_app_version),
      description = "DRO Trimmer",
      name = "DRO Trimmer",
      author = "Laurence Dougal Myers",
      author_email = "jestarjokin@jestarjokin.net",
      windows = [
        {
            "script": "drotrim.py",
            "icon_resources": [(1, "dt.ico")],
            "data_files": [(".", ["drotrim.ini"])]
        }
      ],
      console = [
        {
            "script": "dro_player.py"
        },
        {
            "script": "dro2to1.py"
        },
        {
            "script": "dro_split.py"
        },
      ],
      options=opts
)
