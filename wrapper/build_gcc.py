#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent))
from toolchains.build_gcc import main

main()
