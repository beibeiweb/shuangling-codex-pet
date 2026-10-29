import runpy
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    sys.exit('Python 3.11 or newer is required: https://www.python.org/downloads/windows/')
runpy.run_path(str(Path(__file__).with_name('install.py')), run_name='__main__')
