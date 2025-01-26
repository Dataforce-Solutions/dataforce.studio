from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from dataforce_studio.settings import config


class EmailHandler:
    _email_client = SendGridAPIClient(config.SENDGRID_API_KEY)

    def __init__(self, sender_email: str = "noreply@dataforce.studio") -> None:
        self.sender_email = sender_email

    def send_activation_email(
        self, email: str, activation_link: str, name: str
    ) -> None:
        message = Mail(
            from_email=self.sender_email,
            to_emails=email,
            subject="Welcome to Dataforce Studio",
        )
        message.template_id = "d-82a44c5556ad4da9ad625b1bcb440b57"
        message.dynamic_template_data = {
            "name": name,
            "confirm_email_link": activation_link,
        }

        self._email_client.send(message)

    def send_password_reset_email(self, email: str, reset_password_link: str) -> None:
        message = Mail(
            from_email=self.sender_email,
            to_emails=email,
            subject="Reset Your Password",
        )
        message.template_id = "d-c66a964b9d2e4f83978066e5180b4c59"
        message.dynamic_template_data = {
            "reset_password_link": reset_password_link,
        }

        self._email_client.send(message)
