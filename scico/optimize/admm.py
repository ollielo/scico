# -*- coding: utf-8 -*-
# Copyright (C) 2022-2023 by SCICO Developers
# All rights reserved. BSD 3-clause License.
# This file is part of the SCICO package. Details of the copyright and
# user license can be found in the 'LICENSE' file distributed with the
# package.

"""ADMM solver and auxiliary classes."""

import sys

# isort: off
from ._admmaux import (
    SubproblemSolver,
    GenericSubproblemSolver,
    LinearSubproblemSolver,
    CircularConvolveSolver,
    FBlockCircularConvolveSolver,
    G0BlockCircularConvolveSolver,
)
from ._admm import ADMM

__all__ = [
    "SubproblemSolver",
    "GenericSubproblemSolver",
    "LinearSubproblemSolver",
    "CircularConvolveSolver",
    "FBlockCircularConvolveSolver",
    "G0BlockCircularConvolveSolver",
    "ADMM",
]

# Imported items in __all__ appear to originate in top-level linop module
for name in __all__:
    getattr(sys.modules[__name__], name).__module__ = __name__
