import os
import smtplib
from email.message import EmailMessage


class RegistrationEmailError(Exception):
    """Raised when the registration verification email cannot be sent."""


def send_registration_email(to_address: str, code: str) -> None:
    host = os.getenv('SMTP_HOST')
    port_str = os.getenv('SMTP_PORT', '587')
    user = os.getenv('SMTP_USER')
    password = os.getenv('SMTP_PASSWORD')
    from_addr = os.getenv('SMTP_FROM') or user

    if not host or not user or not password:
        raise RegistrationEmailError(
            'Email could not be sent: mail service is not configured on the server.'
        )

    try:
        port = int(port_str)
    except ValueError:
        raise RegistrationEmailError(
            'Email could not be sent: invalid SMTP configuration.'
        ) from None

    msg = EmailMessage()
    msg['Subject'] = 'Your registration verification code'
    msg['From'] = from_addr
    msg['To'] = to_address
    msg.set_content(
        f'Your verification code is: {code}\n\n'
        'If you did not create an account, you can ignore this email.'
    )

    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
    except Exception:
        raise RegistrationEmailError(
            'Account was created but the verification email could not be sent. '
            'Please try again later or contact support.'
        ) from None
