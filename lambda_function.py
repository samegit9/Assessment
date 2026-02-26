import pandas as pd
import json
import re
import boto3
import urllib.parse
import os
from  datetime import datetime, date
import tempfile
from Controller import DataExtractor
# import matplotlib.pyplot as plt

s3_client = boto3.client('s3')


def lambda_handler(event, context):
    # 1. Dynamically grab the bucket and file name from the S3 'event'
    try:
        # Navigate the S3 event JSON structure
        bucket_name = event['Records'][0]['s3']['bucket']['name']
        
        # 'unquote_plus' handles file names with spaces (S3 converts spaces to '+')
        file_key = urllib.parse.unquote_plus(
            event['Records'][0]['s3']['object']['key'], encoding='utf-8'
        )
    except KeyError:
        print("Error: Event does not contain expected S3 structure.")
        return {'statusCode': 400, 'body': 'Invalid event format'}

    try:
        # Step 2: Download the .sql file from S3 to /tmp
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
            s3_client.download_fileobj(bucket_name, file_key, tmp)
            tmp_path = tmp.name

        # Step 3: Read into dataframe and process
        data = pd.read_csv(tmp_path, sep='\t', encoding='utf-8-sig')
        ex = DataExtractor(data)
        df, dates = ex.extract_revenue_data()

        # Step 4: Write output file to /tmp
        output_key  = f"{date.today().strftime('%Y-%m-%d')}_SearchKeywordPerformance.tab"
        output_path = f"/tmp/{output_key}"
        df.to_csv(output_path, sep='\t', index=False)

        # Step 5: Upload result back to S3 under output/ prefix
        s3_client.upload_file(output_path, bucket_name, f"output/{output_key}")


        return {
            'statusCode': 200,
            'body': json.dumps(f"Output written to s3://{bucket_name}/output/{output_key}")
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }