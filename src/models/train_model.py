import json
import os

import click
import joblib as jb
import mlflow
import pandas as pd
from dotenv import load_dotenv
from mlflow.models.signature import infer_signature
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, log_loss

load_dotenv()

RANDOM_STATE = 42

# Get remote server credentials from .env and set tracking URI for mlflow.
remote_server_ip = os.getenv("MLFLOW_TRACKING_IP")
remote_server_port = os.getenv("MLFLOW_TRACKING_PORT")
remote_server_uri = f"http://{remote_server_ip}:{remote_server_port}"

mlflow.set_tracking_uri(remote_server_uri)

# Update S3 endpoint URL with current IP address (default is localhost).
s3_server_port = os.getenv("MLFLOW_S3_ENDPOINT_PORT")
os.environ['MLFLOW_S3_ENDPOINT_URL'] = f"http://{remote_server_ip}:{s3_server_port}"


@click.command()
@click.argument('train_path', type=click.Path(exists=True))
@click.argument('val_path', type=click.Path(exists=True))
@click.argument('score_path', type=click.Path())
@click.argument('artifact_path', type=click.Path())
def train_model(train_path: str, val_path: str, score_path: str, artifact_path: str) -> None:
    """
    Trains model and stores training information in MLflow.
    :param train_path: Path to get training data in .csv file.
    :param val_path: Path to get validation data in .csv file.
    :param score_path: Path to save model scores in .json file.
    :param artifact_path: Path to save model artifact in .clf file.
    :return:
    """
    with mlflow.start_run():
        # Load processed datasets.
        df_train = pd.read_csv(train_path)
        df_val = pd.read_csv(val_path)

        # Split into training and target features.
        X_train, y_train = df_train.drop(columns=['drinking'], axis=1), df_train['drinking']
        X_val, y_val = df_val.drop(columns=['drinking'], axis=1), df_val['drinking']

        # Define parameters and model.
        params = {
            "max_depth": 3,
            "n_estimators": 25,
            "random_state": RANDOM_STATE
        }
        model = RandomForestClassifier(**params)

        # Train model and save it in the local machine.
        model.fit(X_train, y_train)
        jb.dump(model, artifact_path)

        # Predict on validation set and save scores into local machine.
        y_pred = model.predict(X_val)
        scores = {
            'accuracy': accuracy_score(y_val, y_pred),
            'log_loss': log_loss(y_val, y_pred)
        }

        with open(score_path, 'w', encoding='utf-8') as f:
            json.dump(scores, f, indent=4)

        # Save scores & model remotely using mlflow.
        signature = infer_signature(X_val, y_pred)

        mlflow.log_params(params)
        mlflow.log_metrics(scores)
        mlflow.sklearn.log_model(model, signature=signature, artifact_path=artifact_path)


if __name__ == "__main__":
    train_model()
