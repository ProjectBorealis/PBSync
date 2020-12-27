import os
import importlib

# add required gslib files
package, files = ('gslib', ['VERSION', 'CHECKSUM'])

# add packages
datas = []
proot = os.path.dirname(importlib.import_module(package).__file__)
datas.extend((os.path.join(proot, f), package) for f in files)

# explicitly exclude these imports to make sure we don't build with them since they're stripped out at build
excludedimports = ['gslib.tests.util', 'gslib.tests']
