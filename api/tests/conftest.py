import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["LOG_DRIVER"] = "stdout"
os.environ["BATCH_ENABLED"] = "false"
