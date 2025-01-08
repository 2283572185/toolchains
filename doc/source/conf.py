import pathlib

from sphinx_pyproject import SphinxConfig

root_dir = pathlib.Path(__file__).parents[2]
config = SphinxConfig(root_dir / "pyproject.toml", globalns=globals())

project = name  # type:ignore
for key in config:
    globals()[key] = config[key]
