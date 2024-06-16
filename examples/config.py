from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongo_uri: str
    mongo_dbname: str
    mongo_dbname_test: str
    
    oracle_uri: str

    mongo_dctransfer: str
    mongo_dctransfer_xsync: str

    oracle_dctransfer: str
    oracle_dctransfer_outbox: str

    kafka_topic_dctransfer_circlebi_disa: str
    kafka_topic_dctransfer_disa_circlebi: str

    kafka_topic_debug: str

    github_oauth_client_id: str
    github_oauth_client_secret: str
    root_path: str = ""
    logging_level: str = "INFO"
    testing: bool = False
    
    model_config = SettingsConfigDict(env_file="../kafka-confluent/.env", extra="ignore")


settings = Settings()
