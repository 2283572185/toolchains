python
import gdb  # type: ignore
import os
import sys

share_dir: str = os.path.abspath(os.path.join(sys.path[0], "../../"))
python_dir: str = ""
for dir in os.listdir(share_dir):
    current_dir = os.path.join(share_dir, dir, "python")
    if dir.startswith("gcc") and os.path.isdir(current_dir):
        python_dir = current_dir
        break
if python_dir:
    if python_dir not in sys.path:
        sys.path.insert(0, python_dir)
    from libstdcxx.v6 import register_libstdcxx_printers  # type: ignore

    register_libstdcxx_printers(gdb.current_objfile())
else:
    print("Cannot find gcc python support because share/gcc*/python directory does not exist.")
end
