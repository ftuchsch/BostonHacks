"""Training script for the ΔScore regression model.

This script loads delta score training data, splits it into training and
validation sets, fits a regression model, reports the validation Mean Absolute
Error (MAE), and saves the trained pipeline to disk.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import HistGradientBoostingRegressor

# Default relative locations of resources inside the repository.
_DEFAULT_DATA_LOCATIONS: tuple[Path, ...] = (
    Path("Foldit_Web_Spec") / "10_DATA_SAMPLES" / "synthetic_deltas.csv",
    Path("10_DATA_SAMPLES") / "synthetic_deltas.csv",
)
_DEFAULT_MODEL_PATH = Path("app") / "server" / "models" / "delta_score.pkl"


def _resolve_existing_path(candidates: Iterable[Path]) -> Path:
    """Return the first existing path from *candidates*.

    Raises:
        FileNotFoundError: if none of the candidate paths exist.
    """

    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Unable to find a training dataset. Checked: "
        + ", ".join(str(path) for path in candidates)
    )


def load_training_data(csv_path: Path) -> tuple[pd.DataFrame, pd.Series]:
    """Load the delta score dataset from *csv_path*.

    Returns a tuple ``(features, target)``.
    """

    data = pd.read_csv(csv_path)
    if "delta_score" not in data.columns:
        raise KeyError("Expected 'delta_score' column in dataset")

    target = data["delta_score"]
    features = data.drop(columns=["delta_score"])
    return features, target


def build_model_pipeline(feature_frame: pd.DataFrame) -> Pipeline:
    """Create the preprocessing + model pipeline based on *feature_frame*.

    Numerical columns are standardised, while categorical columns are one-hot
    encoded. The regressor is a HistGradientBoostingRegressor, which performs
    well on tabular data and handles non-linear relationships.
    """

    categorical_cols = [
        name
        for name, dtype in feature_frame.dtypes.items()
        if dtype == "object" or dtype.name.startswith("category")
    ]
    numerical_cols = [col for col in feature_frame.columns if col not in categorical_cols]

    transformers = []
    if numerical_cols:
        transformers.append(("numerical", StandardScaler(), numerical_cols))
    if categorical_cols:
        transformers.append(
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                categorical_cols,
            )
        )

    if not transformers:
        raise ValueError("No features available to train the model.")

    preprocessor = ColumnTransformer(transformers=transformers, remainder="drop")

    model = HistGradientBoostingRegressor(random_state=42)

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", model),
    ])

    return pipeline


def train(
    data_path: Path,
    model_path: Path,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, float | int]:
    """Train the delta score model and persist it to *model_path*.

    Returns a mapping containing key training metrics.
    """

    features, target = load_training_data(data_path)
    pipeline = build_model_pipeline(features)

    X_train, X_val, y_train, y_val = train_test_split(
        features,
        target,
        test_size=test_size,
        random_state=random_state,
    )

    pipeline.fit(X_train, y_train)

    predictions = pipeline.predict(X_val)
    mae = float(mean_absolute_error(y_val, predictions))

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_path)

    return {"mae": mae, "samples": int(features.shape[0])}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the ΔScore regression model")
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="Path to the training CSV file. Defaults to the bundled synthetic dataset.",
    )
    parser.add_argument(
        "--model-out",
        type=Path,
        default=_DEFAULT_MODEL_PATH,
        help="File to write the trained model to.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Proportion of the dataset to allocate to validation.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed used for reproducibility.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    if args.data is None:
        data_candidates = tuple(repo_root / path for path in _DEFAULT_DATA_LOCATIONS)
        data_path = _resolve_existing_path(data_candidates)
    else:
        data_path = (repo_root / args.data) if not args.data.is_absolute() else args.data

    model_path = (
        repo_root / args.model_out if not args.model_out.is_absolute() else args.model_out
    )

    metrics = train(
        data_path=data_path,
        model_path=model_path,
        test_size=args.test_size,
        random_state=args.random_state,
    )

    print(json.dumps({
        "data_path": str(data_path),
        "model_path": str(model_path),
        "mae": metrics["mae"],
        "samples": metrics["samples"],
    }, indent=2))


if __name__ == "__main__":
    main()
