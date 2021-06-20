import boto3
from botocore.exceptions import ClientError


# fromaddr should be like "Sender Name <sender@example.com>"
# toaddr must be str, not list. If you send it to multiple people at once,
# the e-mail addresses of the people you send with may be exposed to each other.
def send_mail(fromaddr: str, toaddr: str, subject: str, message: str) -> str:
    # Create a new SES resource and specify a region.
    client = boto3.client('ses')

    # Try to send the email.
    try:
        response = client.send_email(
            Source=fromaddr,
            Destination={'ToAddresses': [toaddr, ], },
            Message={
                'Subject': {
                    'Charset': 'UTF-8',
                    'Data': subject,
                },
                'Body': {
                    'Html': {
                        'Charset': 'UTF-8',
                        'Data': message,
                    },
                },
            },
        )
    except ClientError as e:
        Exception(f'Error raised while sending AWS SES email - {e.response["Error"]["Message"]}')

    return response['MessageId']
