"""
spark_processing.py
1.Reads data from kafka in a structured streaming format to spark DF
2.Perform data preprocessing
3.Apply ML Model on data.
"""

# Import Libraries
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json
import pickle
import pandas as pd
from pyspark.sql.types import StructType, IntegerType, DoubleType, StringType, TimestampType
from pyspark.sql.functions import udf

# set Environment parameter (optional)'''
os.environ['PYSPARK_SUBMIT_ARGS'] = '--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.0.1'
global path
path = os.getcwd() + '\model'


#
def udf_ml_model(feat1, feat2, feat3, feat4, feat5, feat6, feat7, feat8, feat9, feat10, feat11, feat12):
    df = pd.DataFrame({'key': [feat1], 'time': [feat2], 'active_routes_count': [feat3], 'backup_routes_count': [feat4],
                       'deleted_routes_count': [feat5], 'paths_count': [feat6],
                       'performance_stat_global_config_items_processed': [feat7],
                       'performance_stat_vrf_inbound_update_messages': [feat8],
                       'protocol_route_memory': [feat9], 'total_neighbors_count': [feat10],
                       'vrf_path_count': [feat11], 'vrf_update_messages_received': [feat12]})
    # df = pd.DataFrame(row).transpose()
    # df.columns = cols
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    df = df.astype({'active_routes_count': 'float64',
                    'backup_routes_count': 'float64', 'deleted_routes_count': 'float64',
                    'paths_count': 'float64',
                    'performance_stat_global_config_items_processed': 'float64',
                    'performance_stat_vrf_inbound_update_messages': 'float64',
                    'protocol_route_memory': 'float64', 'total_neighbors_count': 'float64',
                    'vrf_path_count': 'float64', 'vrf_update_messages_received': 'float64'})
    node_name = df["key"][0]
    # load scaler file
    print(type(node_name), node_name)
    scaler_file_name = node_name + "_scaler.pkl"
    spath = os.path.join(path, scaler_file_name)
    with open(spath, 'rb') as f:
        scaler = pickle.load(f)

    # load model file
    model_file_name = node_name + "_model.pkl"
    mpath = os.path.join(path, model_file_name)
    with open(mpath, 'rb') as f:
        model = pickle.load(f)

    # preprocess new data point
    df_new = df.drop(['key', 'time'], axis=1)
    df_new_scaled = scaler.transform(df_new)
    # apply model
    y_pred_outliers = model.predict(df_new_scaled)
    return int(y_pred_outliers)


# Build a spark session
spark = SparkSession \
    .builder \
    .appName("network") \
    .getOrCreate()

# Define Schema for incoming json data
user_schema = StructType() \
    .add("key", StringType()) \
    .add("time", TimestampType()) \
    .add("active_routes_count", DoubleType()) \
    .add("backup_routes_count", DoubleType()) \
    .add("deleted_routes_count", DoubleType()) \
    .add("paths_count", DoubleType()) \
    .add("performance_stat_global_config_items_processed", DoubleType()) \
    .add("performance_stat_vrf_inbound_update_messages", DoubleType()) \
    .add("protocol_route_memory", DoubleType()) \
    .add("total_neighbors_count", DoubleType()) \
    .add("vrf_path_count", DoubleType()) \
    .add("vrf_update_messages_received", DoubleType())

# read stream from kafka topic data_plane
df = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9092") \
    .option("subscribe", "data_plane") \
    .load()

# convert data to string format
raw_df = df.selectExpr("CAST(key AS STRING)", "CAST(value AS STRING)")

# providing timestamp format for parsing
TimestampFormat = "yyyy-MM-dd HH:mm:ss.f"
jsonOptions = {"timestampFormat": TimestampFormat}

# explode single value column from stream to json schema columns
raw_df = raw_df.withColumn("value", from_json(col="value", schema=user_schema, options=jsonOptions)).select("value.*")

# register User defined function get_distance()
udf_ml_model = udf(udf_ml_model, IntegerType())
raw_df = raw_df.withColumn('Anomaly',
                               udf_ml_model(raw_df.key, raw_df.time, raw_df.active_routes_count,
                                            raw_df.backup_routes_count,
                                            raw_df.deleted_routes_count, raw_df.paths_count,
                                            raw_df.performance_stat_global_config_items_processed,
                                            raw_df.performance_stat_vrf_inbound_update_messages,
                                            raw_df.protocol_route_memory, raw_df.total_neighbors_count,
                                            raw_df.vrf_path_count, raw_df.vrf_update_messages_received))


# Function to process each row
def process_row(batch_df,epoch_id):
    if not batch_df.rdd.isEmpty():
        batch_df.write \
            .format("jdbc") \
            .option("url", "jdbc:postgresql://localhost:5433/postgres") \
            .option("dbtable", "public.data_plane") \
            .option("user", "postgres") \
            .option("password", "123456") \
            .mode("append")\
            .save()


query = raw_df \
    .writeStream \
    .trigger(processingTime='10 seconds') \
    .foreachBatch(process_row) \
    .start()


'''query = raw_df \
    .writeStream \
    .outputMode("append") \
    .trigger(processingTime='10 seconds') \
    .format("console") \
    .start()'''

query.awaitTermination()
