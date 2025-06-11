"""
Glue ETL Script: Raw to Processed Data Transformation
Transforms raw IoT sensor data into processed format for analytics
"""

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import DataFrame
from pyspark.sql.functions import *
from pyspark.sql.types import *
import boto3

# Initialize Glue context
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)

# Get job parameters
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'SOURCE_DATABASE',
    'SOURCE_TABLE', 
    'TARGET_BUCKET'
])

job.init(args['JOB_NAME'], args)

# Job parameters
SOURCE_DATABASE = args['SOURCE_DATABASE']
SOURCE_TABLE = args['SOURCE_TABLE']
TARGET_BUCKET = args['TARGET_BUCKET']

def main():
    """
    Main ETL processing function
    """
    try:
        print(f"Starting ETL job: {args['JOB_NAME']}")
        print(f"Source: {SOURCE_DATABASE}.{SOURCE_TABLE}")
        print(f"Target: s3://{TARGET_BUCKET}/processed/")

        # 1️⃣ Read raw data from Glue catalog
        print("Reading raw IoT data...")
        raw_data = glueContext.create_dynamic_frame.from_catalog(
            database=SOURCE_DATABASE,
            table_name=SOURCE_TABLE,
            transformation_ctx="raw_data"
        )

        print(f"Raw data count: {raw_data.count()}")

        # 2️⃣ Convert to Spark DataFrame for transformations
        df = raw_data.toDF()

        # 3️⃣ Data quality checks and cleaning
        print("Performing data quality checks...")
        
        # Remove records with null device_id
        df = df.filter(col("device_id").isNotNull())
        
        # Remove records with invalid timestamps
        df = df.filter(col("timestamp").isNotNull() & (col("timestamp") > 0))
        
        # Remove records with impossible sensor values
        df = df.filter(
            (col("temperature").between(-50, 100)) &
            (col("humidity").between(0, 100))
        )

        print(f"Data count after quality checks: {df.count()}")

        # 4️⃣ Data enrichment and transformations
        print("Enriching data...")
        
        # Add derived columns
        df_enriched = df.withColumn(
            "reading_datetime", 
            from_unixtime(col("timestamp")).cast(TimestampType())
        ).withColumn(
            "hour_of_day", 
            hour(from_unixtime(col("timestamp")))
        ).withColumn(
            "day_of_week", 
            dayofweek(from_unixtime(col("timestamp")))
        ).withColumn(
            "temperature_category",
            when(col("temperature") < 10, "Cold")
            .when(col("temperature") < 25, "Moderate") 
            .when(col("temperature") < 35, "Warm")
            .otherwise("Hot")
        ).withColumn(
            "humidity_category",
            when(col("humidity") < 30, "Low")
            .when(col("humidity") < 60, "Normal")
            .otherwise("High")
        ).withColumn(
            "comfort_index",
            # Simple comfort index based on temperature and humidity
            when(
                (col("temperature").between(20, 26)) & 
                (col("humidity").between(40, 60)), 
                "Comfortable"
            ).when(
                (col("temperature") > 30) | (col("humidity") > 70), 
                "Uncomfortable"
            ).otherwise("Acceptable")
        )

        # 5️⃣ Aggregate data by device and hour
        print("Creating hourly aggregations...")
        
        hourly_agg = df_enriched.groupBy(
            "device_id",
            date_trunc("hour", col("reading_datetime")).alias("hour_timestamp"),
            "year", "month", "day"
        ).agg(
            count("*").alias("reading_count"),
            avg("temperature").alias("avg_temperature"),
            min("temperature").alias("min_temperature"), 
            max("temperature").alias("max_temperature"),
            stddev("temperature").alias("std_temperature"),
            avg("humidity").alias("avg_humidity"),
            min("humidity").alias("min_humidity"),
            max("humidity").alias("max_humidity"),
            stddev("humidity").alias("std_humidity"),
            first("temperature_category").alias("dominant_temp_category"),
            first("humidity_category").alias("dominant_humidity_category"),
            first("comfort_index").alias("dominant_comfort_index")
        )

        # 6️⃣ Calculate device statistics
        print("Calculating device statistics...")
        
        device_stats = df_enriched.groupBy("device_id").agg(
            count("*").alias("total_readings"),
            min("reading_datetime").alias("first_reading"),
            max("reading_datetime").alias("last_reading"),
            avg("temperature").alias("avg_temperature_overall"),
            avg("humidity").alias("avg_humidity_overall"),
            countDistinct(date_trunc("day", col("reading_datetime"))).alias("active_days")
        )

        # 7️⃣ Write processed data to S3
        print("Writing processed data to S3...")

        # Write detailed processed data
        processed_dynamic_frame = DynamicFrame.fromDF(
            df_enriched, 
            glueContext, 
            "processed_data"
        )
        
        glueContext.write_dynamic_frame.from_options(
            frame=processed_dynamic_frame,
            connection_type="s3",
            connection_options={
                "path": f"s3://{TARGET_BUCKET}/processed/detailed/",
                "partitionKeys": ["year", "month", "day"]
            },
            format="parquet",
            transformation_ctx="write_processed_detailed"
        )

        # Write hourly aggregations
        hourly_dynamic_frame = DynamicFrame.fromDF(
            hourly_agg, 
            glueContext, 
            "hourly_aggregations"
        )
        
        glueContext.write_dynamic_frame.from_options(
            frame=hourly_dynamic_frame,
            connection_type="s3", 
            connection_options={
                "path": f"s3://{TARGET_BUCKET}/processed/hourly/",
                "partitionKeys": ["year", "month", "day"]
            },
            format="parquet",
            transformation_ctx="write_hourly_agg"
        )

        # Write device statistics
        device_stats_dynamic_frame = DynamicFrame.fromDF(
            device_stats, 
            glueContext, 
            "device_statistics"
        )
        
        glueContext.write_dynamic_frame.from_options(
            frame=device_stats_dynamic_frame,
            connection_type="s3",
            connection_options={
                "path": f"s3://{TARGET_BUCKET}/processed/device_stats/"
            },
            format="parquet",
            transformation_ctx="write_device_stats"
        )

        # 8️⃣ Create processed data tables in Glue catalog
        print("Updating Glue catalog...")
        
        # Update catalog with new tables
        create_glue_tables()

        print("ETL job completed successfully!")
        
        # Return job metrics
        return {
            "status": "SUCCESS",
            "raw_records": raw_data.count(),
            "processed_records": df_enriched.count(),
            "hourly_aggregations": hourly_agg.count(),
            "unique_devices": device_stats.count()
        }

    except Exception as e:
        print(f"ETL job failed: {str(e)}")
        raise e


def create_glue_tables():
    """
    Create Glue catalog tables for processed data
    """
    glue_client = boto3.client('glue')
    
    try:
        # Processed detailed data table
        glue_client.create_table(
            DatabaseName=SOURCE_DATABASE,
            TableInput={
                'Name': 'processed_iot_data_detailed',
                'Description': 'Processed IoT sensor data with enrichments',
                'TableType': 'EXTERNAL_TABLE',
                'StorageDescriptor': {
                    'Columns': [
                        {'Name': 'device_id', 'Type': 'string'},
                        {'Name': 'timestamp', 'Type': 'bigint'},
                        {'Name': 'temperature', 'Type': 'double'},
                        {'Name': 'humidity', 'Type': 'double'},
                        {'Name': 'source_topic', 'Type': 'string'},
                        {'Name': 'event_time', 'Type': 'bigint'},
                        {'Name': 'reading_datetime', 'Type': 'timestamp'},
                        {'Name': 'hour_of_day', 'Type': 'int'},
                        {'Name': 'day_of_week', 'Type': 'int'},
                        {'Name': 'temperature_category', 'Type': 'string'},
                        {'Name': 'humidity_category', 'Type': 'string'},
                        {'Name': 'comfort_index', 'Type': 'string'}
                    ],
                    'Location': f's3://{TARGET_BUCKET}/processed/detailed/',
                    'InputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
                    'OutputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat',
                    'SerdeInfo': {
                        'SerializationLibrary': 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
                    }
                },
                'PartitionKeys': [
                    {'Name': 'year', 'Type': 'string'},
                    {'Name': 'month', 'Type': 'string'},
                    {'Name': 'day', 'Type': 'string'}
                ]
            }
        )
        print("Created processed_iot_data_detailed table")
        
    except glue_client.exceptions.AlreadyExistsException:
        print("processed_iot_data_detailed table already exists")
    
    try:
        # Hourly aggregations table
        glue_client.create_table(
            DatabaseName=SOURCE_DATABASE,
            TableInput={
                'Name': 'processed_iot_data_hourly',
                'Description': 'Hourly aggregated IoT sensor data',
                'TableType': 'EXTERNAL_TABLE',
                'StorageDescriptor': {
                    'Columns': [
                        {'Name': 'device_id', 'Type': 'string'},
                        {'Name': 'hour_timestamp', 'Type': 'timestamp'},
                        {'Name': 'reading_count', 'Type': 'bigint'},
                        {'Name': 'avg_temperature', 'Type': 'double'},
                        {'Name': 'min_temperature', 'Type': 'double'},
                        {'Name': 'max_temperature', 'Type': 'double'},
                        {'Name': 'std_temperature', 'Type': 'double'},
                        {'Name': 'avg_humidity', 'Type': 'double'},
                        {'Name': 'min_humidity', 'Type': 'double'},
                        {'Name': 'max_humidity', 'Type': 'double'},
                        {'Name': 'std_humidity', 'Type': 'double'},
                        {'Name': 'dominant_temp_category', 'Type': 'string'},
                        {'Name': 'dominant_humidity_category', 'Type': 'string'},
                        {'Name': 'dominant_comfort_index', 'Type': 'string'}
                    ],
                    'Location': f's3://{TARGET_BUCKET}/processed/hourly/',
                    'InputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
                    'OutputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat',
                    'SerdeInfo': {
                        'SerializationLibrary': 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
                    }
                },
                'PartitionKeys': [
                    {'Name': 'year', 'Type': 'string'},
                    {'Name': 'month', 'Type': 'string'},
                    {'Name': 'day', 'Type': 'string'}
                ]
            }
        )
        print("Created processed_iot_data_hourly table")
        
    except glue_client.exceptions.AlreadyExistsException:
        print("processed_iot_data_hourly table already exists")

    try:
        # Device statistics table
        glue_client.create_table(
            DatabaseName=SOURCE_DATABASE,
            TableInput={
                'Name': 'processed_device_statistics',
                'Description': 'Device-level statistics and metrics',
                'TableType': 'EXTERNAL_TABLE',
                'StorageDescriptor': {
                    'Columns': [
                        {'Name': 'device_id', 'Type': 'string'},
                        {'Name': 'total_readings', 'Type': 'bigint'},
                        {'Name': 'first_reading', 'Type': 'timestamp'},
                        {'Name': 'last_reading', 'Type': 'timestamp'},
                        {'Name': 'avg_temperature_overall', 'Type': 'double'},
                        {'Name': 'avg_humidity_overall', 'Type': 'double'},
                        {'Name': 'active_days', 'Type': 'bigint'}
                    ],
                    'Location': f's3://{TARGET_BUCKET}/processed/device_stats/',
                    'InputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
                    'OutputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat',
                    'SerdeInfo': {
                        'SerializationLibrary': 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
                    }
                }
            }
        )
        print("Created processed_device_statistics table")
        
    except glue_client.exceptions.AlreadyExistsException:
        print("processed_device_statistics table already exists")


if __name__ == "__main__":
    # Execute main ETL logic
    result = main()
    print(f"Job result: {result}")
    
    # Commit the job
    job.commit() 