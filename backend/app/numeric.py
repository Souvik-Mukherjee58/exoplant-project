"""Numeric helpers."""

from typing import Any

import numpy as np


def zero_where_missing(values: Any) -> np.ndarray:
    """A new array with 0.0 where a value is missing, for weighted sums whose weight is then 0 as well.

    Never np.nan_to_num on a Series: with pandas 2.2 and NumPy 2 (the pinned versions) it overwrites the original column, so
    that missing values silently become 0.0 in the data.
    """
    array = np.asarray(values, dtype=float)
    return np.where(np.isnan(array), 0.0, array)
