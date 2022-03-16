import datetime
import firebase_admin
from firebase_admin import credentials
from firebase_admin import messaging
import json
import os
import typing


def firebase_send_notify(title: str = None, body: str = None, data: dict = None,
                         topic: str = None, target_tokens: typing.Union[str, list[str], None] = None,
                         condition: str = None):
    try:
        cred = credentials.Certificate(os.environ.get('FIREBASE_CERTIFICATE'))
        default_app = firebase_admin.initialize_app(cred)  # noqa
    except ValueError:
        # default_app is already initialized.
        pass

    if not any((all((title, body, ), ), data, ), ):
        raise ValueError('At least one of (title, body)|data must be set')

    data = data if data else {'click_action': 'FLUTTER_NOTIFICATION_CLICK', }
    # All keys and values in data must be a string.
    # We'll try to type casting all values to json compatible string.
    tmp_dict = dict()
    for k, v in data.items():
        try:
            if isinstance(v, datetime.datetime):
                v = v.replace(tzinfo=datetime.timezone.utc)
                v_timestamp = int(v.timestamp())

                tmp_dict[str(k)] = str(v)
                tmp_dict[str(k) + '_timestamp'] = str(v_timestamp)
            else:
                tmp_dict[str(k)] = json.dumps(v)
        except Exception:
            try:
                tmp_dict[str(k)] = str(v)
            except Exception:
                tmp_dict[str(k)] = ''
    data = tmp_dict

    notification = None
    if any((title, body)):
        title = str(title) or ''
        body = str(body) or ''
        notification = messaging.Notification(title=title, body=body)

    if not isinstance(target_tokens, (list, tuple)):
        target_tokens = [target_tokens, ]

    message_payload = list()
    for target_token in target_tokens:
        message_payload.append(
            messaging.Message(
                data=data,
                notification=notification,
                token=target_token,
                topic=topic,
                # specify receiver by using multiple topic subscription status.
                # 'condition' shapes like this
                # >>> condition = "'stock-GOOG' in topics || 'industry-tech' in topics"
                condition=condition,

                # android=None,  # use messaging.AndroidConfig
                # apns=None,  # use messaging.apns
                # webpush=None,  # use messaging.WebpushConfig
                # fcm_options=None,  # use messaging.FCMOptions
            )
        )

    response = messaging.send_all(message_payload)
    print('Successfully sent message:', response)  # Response is a message ID string.
