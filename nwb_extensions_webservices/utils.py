import shutil
import tempfile
from contextlib import contextmanager

@contextmanager
def tmp_directory():
    tmp_dir = tempfile.mkdtemp('_extensions')
    yield tmp_dir
    shutil.rmtree(tmp_dir)
