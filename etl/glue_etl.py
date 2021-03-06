import sys

from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from awsglue.dynamicframe import DynamicFrame
from pyspark.sql.functions import lit, monotonically_increasing_id

glueContext = GlueContext(SparkContext.getOrCreate())

job_args = getResolvedOptions(sys.argv, [
    'glue-db-name',
    'glue-table-name',
    's3-bucket-name'
])
# Data Catalog: database and table name
db_name = job_args['glue_db_name']
tbl_name = job_args['glue_table_name']


# Read data into a DynamicFrame using the Data Catalog metadata
dyf = glueContext.create_dynamic_frame.from_catalog(
    database=db_name, table_name=tbl_name
)
df = dyf.toDF()

orig_account_df = df.select('nameorig').distinct()
dest_account_df = df.select('namedest').distinct()
all_account_df = orig_account_df.union(dest_account_df).distinct()

accounts = all_account_df\
    .withColumnRenamed('nameorig', '~id')\
    .withColumn('~label', lit('ACCOUNT'))

accounts_dyf = DynamicFrame.fromDF(accounts, glueContext, "accounts")

# S3 location for output
output_dir = "s3://%s/transformed/vertex-accounts" % job_args['s3_bucket_name']
glueContext.write_dynamic_frame.from_options(
    frame=accounts_dyf,
    connection_type="s3",
    connection_options={"path": output_dir},
    format="csv"
)


transactions = df\
    .withColumn('~id', monotonically_increasing_id())\
    .withColumnRenamed('nameorig', '~from')\
    .withColumnRenamed('namedest', '~to')\
    .withColumnRenamed('type', '~label')\
    .withColumnRenamed('amount', 'amount:Double')\
    .withColumnRenamed('oldbalanceorg', 'oldbalanceOrg:Double')\
    .withColumnRenamed('newbalanceorig', 'newbalanceOrig:Double')\
    .withColumnRenamed('oldbalancedest', 'oldbalanceDest:Double')\
    .withColumnRenamed('newbalancedest', 'newbalanceDest:Double')\
    .withColumnRenamed('isfraud', 'isFraud:Int')\
    .withColumnRenamed('isflaggedfraud', 'isFlaggedFraud:Int')\
    .select(
        '~id', '~label', '~from', '~to', 'amount:Double',
        'oldbalanceorg:Double', 'newbalanceorig:Double',
        'oldbalancedest:Double', 'newbalancedest:Double',
        'isfraud:Int', 'isflaggedfraud:Int',
    )

transactions_dyf = DynamicFrame.fromDF(
    transactions, glueContext, "transactions"
)

# S3 location for output
output_dir = "s3://%s/transformed/edge-transactions" % job_args['s3_bucket_name']
glueContext.write_dynamic_frame.from_options(
    frame=transactions_dyf,
    connection_type="s3",
    connection_options={"path": output_dir},
    format="csv"
)