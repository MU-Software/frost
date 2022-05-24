import flask
import app.common.mailgun.aws_ses as mailgun_aws
import app.common.mailgun.gmail as mailgun_gmail


def send_mail(fromaddr: str, toaddr: str, subject: str, message: str, raise_on_fail: bool = False) -> bool:
    mail_sent: bool = True
    if flask.current_app.config.get('MAIL_ENABLE'):
        try:
            mail_provider = flask.current_app.config.get('MAIL_PROVIDER', 'AMAZON')
            if mail_provider == 'AMAZON':
                mailgun_aws.send_mail(fromaddr=fromaddr, toaddr=toaddr, subject=subject, message=message)
            elif mail_provider == 'GOOGLE':
                mailgun_gmail.send_mail(
                    google_client_id=flask.current_app.config.get('GOOGLE_CLIENT_ID'),
                    google_client_secret=flask.current_app.config.get('GOOGLE_CLIENT_SECRET'),
                    google_refresh_token=flask.current_app.config.get('GOOGLE_REFRESH_TOKEN'),
                    fromaddr=fromaddr, toaddr=toaddr, subject=subject, message=message)
            else:
                raise NotImplementedError(f'Mail provider "{mail_provider}" is not supported')
            mail_sent = True
        except Exception as err:
            mail_sent = False

            if raise_on_fail:
                raise err
    return mail_sent
