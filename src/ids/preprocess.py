from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.utils.validation import check_is_fitted

from .common import ProtocolError
from .schema import FEATURES, FORBIDDEN


class NumericGuard(TransformerMixin, BaseEstimator):
    """Stateless numeric cleaning; schema is frozen when fit on Train."""

    def fit(self, X, y=None):
        names = list(X.columns)
        if set(names) & FORBIDDEN or not set(names).issubset(FEATURES):
            raise ProtocolError("Only approved flow-statistic features are allowed.")
        self.feature_names_in_ = np.asarray(names, dtype=object)
        self.n_features_in_ = len(names)
        return self

    def transform(self, X):
        check_is_fitted(self)
        names = list(self.feature_names_in_)
        if list(X.columns) != names:
            raise ProtocolError("Feature columns/order differ from the fitted pipeline.")
        frame = X.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        # Tree implementations use float32 internally. Treat unrepresentable values
        # as invalid rather than learning a clipping threshold from all data.
        return frame.where(frame.abs() <= np.finfo(np.float32).max).astype("float64")


class TrainNonconstantColumns(TransformerMixin, BaseEstimator):
    """Select from Train only, including all-missing-column removal."""

    def fit(self, X, y=None):
        self.keep_ = [c for c in X if X[c].nunique(dropna=True) > 1]
        self.dropped_ = [c for c in X if c not in self.keep_]
        if not self.keep_:
            raise ProtocolError("Every feature is constant/all-missing on Train.")
        return self

    def transform(self, X):
        check_is_fitted(self)
        return X.loc[:, self.keep_]


def make_pipeline(estimator) -> Pipeline:
    return Pipeline([
        ("numeric", NumericGuard()),
        ("columns", TrainNonconstantColumns()),
        ("imputer", SimpleImputer(strategy="median")),
        ("model", estimator),
    ])

