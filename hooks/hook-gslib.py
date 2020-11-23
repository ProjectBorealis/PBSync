import os
import importlib

package, files = ('gslib', ['VERSION', 'CHECKSUM'])

datas = []
proot = os.path.dirname(importlib.import_module(package).__file__)
datas.extend((os.path.join(proot, f), package) for f in files)
excludedimports = ['gslib.tests.util', 'gslib.tests']
