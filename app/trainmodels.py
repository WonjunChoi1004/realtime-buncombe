import os, joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import roc_auc_score
from app.utils import load_cfg, log

# Expects a CSV you provide: data/static/training_samples.csv
# Columns: cell_id, geometry_wkt, elev_40m, slope_40m, soil_depth_cm, R1d,R3d,R7d,R30d,Max3d,Max30d, label

def main():
    cfg = load_cfg()
    L = log("train")
    models_dir = cfg["paths"]["models_dir"]
    os.makedirs(models_dir, exist_ok=True)

    train_csv = "data/static/training_samples.csv"
    df = pd.read_csv(train_csv)

    feats = cfg["features"]["static"] + cfg["features"]["rainfall"]
    X, y = df[feats], df["label"].astype(int)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, stratify=y, random_state=42)

    models = {
        "logistic": Pipeline([("scaler", StandardScaler(with_mean=False)), ("clf", LogisticRegression(max_iter=300))]),
        "rf": RandomForestClassifier(n_estimators=400, n_jobs=-1, random_state=42),
        "xgb": XGBClassifier(n_estimators=600, max_depth=6, learning_rate=0.06, subsample=0.9, colsample_bytree=0.85, n_jobs=-1, eval_metric="logloss", random_state=42)
    }

    for name, mdl in models.items():
        mdl.fit(Xtr, ytr)
        auc = roc_auc_score(yte, mdl.predict_proba(Xte)[:,1])
        out = cfg["models"]["logistic" if name=="logistic" else ("rf" if name=="rf" else "xgb")]
        joblib.dump(mdl, out)
        L.info(f"{name} AUC={auc:.3f} → {out}")

if __name__ == "__main__":
    main()
