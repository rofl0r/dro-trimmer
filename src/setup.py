# example setup script stolen from PythonCard samples
# bits taken from http://www.py2exe.org/index.cgi/PythonCardSetup

from distutils.core import setup
import py2exe

# includes for py2exe
includes=[]
# NOTE: if any different components are added, you need to update this list to include them!
#for comp in ['button','textfield','multicolumnlist']:
#    includes += ['PythonCard.components.'+comp]
#print 'includes',includes

opts = { 'py2exe': { 'includes':includes } }
#print 'opts',opts

setup(version = "0.2.0",
      description = "DRO Trimmer",
      name = "DRO Trimmer",
      author = "Laurence Dougal Myers",
      author_email = "jestarjokin@jestarjokin.net",
      windows = [
        {
            "script": "drotrim.py",
            "icon_resources": [(1, "dt.ico")]
        }
      ],
      options=opts
      )

