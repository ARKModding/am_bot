import logging

import boto3
from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)

SENDER = "no-reply@arkmodding.net"
AWS_REGION = "us-west-1"


def send_email(to: str, subject: str, body_txt: str, body_html: str):
    logger.info(f"Sending Email to {to}...")
    client = boto3.client("ses", region_name=AWS_REGION)
    try:
        response = client.send_email(
            Destination={
                'ToAddresses': [to]
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': 'utf-8',
                        'Data': body_html
                    },
                    'Text': {
                        'Charset': 'utf-8',
                        'Data': body_txt
                    }
                },
                'Subject': {
                    'Charset': 'utf-8',
                    'Data': subject
                }
            },
            Source=SENDER
        )
    except ClientError as e:
        logger.warning(e.response['Error']['Message'])
    else:
        logger.info(f"Email Sent! Response: {response}")
