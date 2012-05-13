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


from distutils.core import setup
import os
import py2exe

# includes for py2exe
includes=[]

opts = { 'py2exe': { 
    'includes':includes,
    "dll_excludes": ["MSVCP90.dll"]
} }

setup(version = "3.6.0",
      description = "DRO Trimmer",
      name = "DRO Trimmer",
      author = "Laurence Dougal Myers",
      author_email = "jestarjokin@jestarjokin.net",
      windows = [
        {
            "script": "drotrim.py",
            "icon_resources": [(1, os.path.join("..", "dt.ico"))],
            "data_files": [(".", ["drotrim.ini"])]
        }
      ],
      console = [
        {
            "script": "dro_player.py"
        }
      ],
      options=opts
)
