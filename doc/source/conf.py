from sphinx_pyproject import SphinxConfig
import pathlib
import sys

root_dir = pathlib.Path(__file__).parents[2]
config = SphinxConfig(root_dir / "pyproject.toml", globalns=globals())

project = name  # type:ignore
for key in config:
    globals()[key] = config[key]


sys.path.insert(0, str(root_dir))
