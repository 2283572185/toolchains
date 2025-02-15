#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK

import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent))
from toolchains.download import main

main()
