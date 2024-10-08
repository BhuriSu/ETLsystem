from airflow import DAG
from datetime import datetime, timedelta

from kafka_admin_client.kafka_admin_client import create_new_topic

from airflow.operators.empty import EmptyOperator
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator

start_date = datetime(2024, 9, 16, 12, 20)

default_args = {
    'owner': 'train',
    'start_date': start_date,
    'retries': 1,
    'retry_delay': timedelta(seconds=5)
}

with DAG('streaming_data_processing_dag', default_args=default_args, schedule_interval='@daily', catchup=False) as dag:

    # Run Spark job
    run_spark = BashOperator(task_id='run_spark',
                             bash_command='.venv\\Scripts\\activate && python read_and_write_initial_data\\read_and_write_spark.py',
                             retries=2, retry_delay=timedelta(seconds=15),
                             execution_timeout=timedelta(minutes=20))
    
    # Create Kafka topic
    create_new_topic = BranchPythonOperator(task_id='create_new_topic', python_callable=create_new_topic)

    topic_created = EmptyOperator(task_id="topic_created",)
    topic_exists = EmptyOperator(task_id="topic_already_exists")

    # Run data generator
    run_data_generator = BashOperator(task_id="run_data_generator",
                                      bash_command="bash_script/data_generator.sh",
                                      execution_timeout=timedelta(minutes=15),
                                      trigger_rule='none_failed_or_skipped')

    # Spark job to write to Elasticsearch
    spark_write_to_es = BashOperator(task_id="spark_write_to_es",
                                     bash_command="bash_script/spark_to_elasticsearch.sh",
                                     execution_timeout=timedelta(minutes=15),
                                     trigger_rule='none_failed_or_skipped')

    # Spark job to write to MinIO
    spark_write_to_minio = BashOperator(task_id="spark_write_to_minio",
                                        bash_command="bash_script/spark_to_minio.sh",
                                        execution_timeout=timedelta(minutes=15),
                                        trigger_rule='none_failed_or_skipped')

    # Define task dependencies
    run_spark >>  create_new_topic >> [topic_created, topic_exists]
    [topic_created, topic_exists] >> run_data_generator
    [topic_created, topic_exists] >> spark_write_to_es
    [topic_created, topic_exists] >> spark_write_to_minio
