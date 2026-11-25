"""Train and compare sentiment classifiers, then save the best one.

Usage:
    python src/train.py

Outputs:
    models/sentiment_model.joblib      best pipeline (git-ignored)
    results/metrics.json               scores for every model
    results/model_comparison.png       accuracy / F1 bar chart
    results/confusion_matrix.png       confusion matrix of the best model
    results/top_features.csv           most positive / negative words
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    f1_score,
)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import load_reviews  # noqa: E402
from preprocess import clean_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
MODELS = ROOT / "models"
SEED = 42


def build_pipelines() -> dict[str, Pipeline]:
    def tfidf() -> TfidfVectorizer:
        return TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_df=0.9, sublinear_tf=True)

    return {
        "Naive Bayes": Pipeline([("tfidf", tfidf()), ("clf", MultinomialNB(alpha=0.5))]),
        "Logistic Regression": Pipeline(
            [("tfidf", tfidf()), ("clf", LogisticRegression(C=10, max_iter=2000))]
        ),
        # Calibrated so the SVM also outputs probabilities for predict.py
        "Linear SVM": Pipeline(
            [("tfidf", tfidf()), ("clf", CalibratedClassifierCV(LinearSVC(C=1.0), cv=5))]
        ),
    }


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    MODELS.mkdir(exist_ok=True)

    df = load_reviews()
    df["clean"] = df["text"].map(clean_text)
    X_train, X_test, y_train, y_test = train_test_split(
        df["clean"], df["label"], test_size=0.2, stratify=df["label"], random_state=SEED
    )
    print(f"Train: {len(X_train)}  Test: {len(X_test)}")

    metrics: dict[str, dict] = {}
    fitted: dict[str, Pipeline] = {}
    for name, pipe in build_pipelines().items():
        cv = cross_val_score(pipe, X_train, y_train, cv=5, scoring="accuracy")
        pipe.fit(X_train, y_train)
        pred = pipe.predict(X_test)
        metrics[name] = {
            "cv_accuracy_mean": round(float(cv.mean()), 4),
            "cv_accuracy_std": round(float(cv.std()), 4),
            "test_accuracy": round(accuracy_score(y_test, pred), 4),
            "test_f1": round(f1_score(y_test, pred), 4),
        }
        fitted[name] = pipe
        print(f"{name:<20} CV {cv.mean():.3f} ± {cv.std():.3f} | "
              f"test acc {metrics[name]['test_accuracy']:.3f} | F1 {metrics[name]['test_f1']:.3f}")

    # Pick the winner on cross-validation (not the test set) to avoid leakage.
    best_name = max(metrics, key=lambda n: metrics[n]["cv_accuracy_mean"])
    best = fitted[best_name]
    pred = best.predict(X_test)
    print(f"\nBest model: {best_name}\n")
    print(classification_report(y_test, pred, target_names=["negative", "positive"]))

    joblib.dump(best, MODELS / "sentiment_model.joblib")
    (RESULTS / "metrics.json").write_text(
        json.dumps({"best_model": best_name, "models": metrics}, indent=2)
    )

    # Model comparison chart
    names = list(metrics)
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x - 0.18, [metrics[n]["test_accuracy"] for n in names], 0.36, label="Accuracy")
    ax.bar(x + 0.18, [metrics[n]["test_f1"] for n in names], 0.36, label="F1")
    ax.set_xticks(x, names)
    ax.set_ylim(0.6, 1.0)
    ax.set_ylabel("Score on held-out test set")
    ax.set_title("Sentiment classifier comparison")
    ax.legend()
    fig.tight_layout()
    fig.savefig(RESULTS / "model_comparison.png", dpi=150)
    plt.close(fig)

    # Confusion matrix
    fig, ax = plt.subplots(figsize=(4.5, 4))
    ConfusionMatrixDisplay.from_predictions(
        y_test, pred, display_labels=["negative", "positive"], cmap="Blues", ax=ax, colorbar=False
    )
    ax.set_title(f"Confusion matrix — {best_name}")
    fig.tight_layout()
    fig.savefig(RESULTS / "confusion_matrix.png", dpi=150)
    plt.close(fig)

    # Most informative words (linear models only)
    clf = best.named_steps["clf"]
    vocab = np.array(best.named_steps["tfidf"].get_feature_names_out())
    if hasattr(clf, "calibrated_classifiers_"):  # average SVM weights across folds
        coefs = np.mean([c.estimator.coef_.ravel() for c in clf.calibrated_classifiers_], axis=0)
    elif hasattr(clf, "coef_"):
        coefs = clf.coef_.ravel()
    else:  # Naive Bayes: log-probability ratio
        coefs = clf.feature_log_prob_[1] - clf.feature_log_prob_[0]
    order = np.argsort(coefs)
    with open(RESULTS / "top_features.csv", "w", encoding="utf-8") as fh:
        fh.write("rank,most_negative,most_positive\n")
        for i in range(25):
            fh.write(f"{i + 1},{vocab[order[i]]},{vocab[order[-(i + 1)]]}\n")

    print(f"Saved model to {MODELS / 'sentiment_model.joblib'} and results to {RESULTS}/")


if __name__ == "__main__":
    main()
