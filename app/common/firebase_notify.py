import firebase_admin
from firebase_admin import credentials
from firebase_admin import messaging
import flask


def firebase_send_notify(title: str, body: str, data: dict = None,
                         topic: str = 'all', target_token: str = None):
    cred = credentials.Certificate(flask.current_app.config.get('FIREBASE_CERTIFICATE'))
    default_app = firebase_admin.initialize_app(cred)  # noqa

    # This registration token comes from the client FCM SDKs.
    # registration_token = flask.current_app.config.get('FIREBASE_REGISTERATION_TOKEN')

    data = data if data else {}

    # See documentation on defining a message payload.
    message = messaging.Message(
        # android=messaging.AndroidConfig(
        #     ttl=datetime.timedelta(seconds=3600),
        #     priority='normal',
        # ),
        android=None,
        apns=None,
        webpush=None,

        data={
            'click_action': 'FLUTTER_NOTIFICATION_CLICK',
        },
        notification=messaging.Notification(title=title, body=body),
        # notification=None,

        fcm_options=None,

        topic=topic,
        token=target_token,
        # condition=None,
    )

    # Send a message to the device corresponding to the provided
    # registration token.
    response = messaging.send(message)
    # Response is a message ID string.
    print('Successfully sent message:', response)
