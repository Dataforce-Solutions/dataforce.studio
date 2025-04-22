from sendgrid import SendGridAPIClient  # type: ignore
from sendgrid.helpers.mail import Mail  # type: ignore

from dataforce_studio.settings import config


class EmailHandler:
    _email_client = SendGridAPIClient(config.SENDGRID_API_KEY)

    def __init__(self, sender_email: str = "noreply@dataforce.studio") -> None:
        self.sender_email = sender_email

    def send_activation_email(
        self, email: str, activation_link: str, name: str | None
    ) -> None:
        message = Mail(
            from_email=self.sender_email,
            to_emails=email,
            subject="Welcome to Dataforce Studio",
        )
        message.template_id = "d-6f44f2afe9c44bbfa523eba28092e078"
        message.dynamic_template_data = {
            "name": name or "",
            "confirm_email_link": activation_link,
        }

        self._email_client.send(message)

    def send_password_reset_email(
        self, email: str, reset_password_link: str, name: str | None
    ) -> None:
        message = Mail(
            from_email=self.sender_email,
            to_emails=email,
            subject="Reset Your Password",
        )
        message.template_id = "d-1a3be5478f454efeb7afc791e69ec613"
        message.dynamic_template_data = {
            "reset_password_link": reset_password_link,
            "name": name or "",
        }

        self._email_client.send(message)
