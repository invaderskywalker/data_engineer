import os
import smtplib
import email.utils
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from jinja2 import Template
from dotenv import load_dotenv

load_dotenv()

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
SENDER_NAME = "trmeric"


def send_email_notification(
    receiver_email,
    subject,
    body_html,
    cc_list=None,
    bcc_list=None,
    attachments=None
):
    try:
        # print("EMAIL:", SENDER_EMAIL)
        # print("PASSWORD:", SENDER_PASSWORD)
        cc_list = cc_list or []
        bcc_list = bcc_list or []

        message = MIMEMultipart()
        message["From"] = email.utils.formataddr((SENDER_NAME, SENDER_EMAIL))

        dec_email = receiver_email
        message["To"] = dec_email
        message["Subject"] = subject

        if cc_list:
            message["Cc"] = ", ".join(cc_list)

        message.attach(MIMEText(body_html, "html"))

        # Attach files
        if attachments:
            for file_path in attachments:
                with open(file_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                    message.attach(part)

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(
                SENDER_EMAIL,
                [dec_email] + cc_list + bcc_list,
                message.as_string()
            )

        return {"status": "success"}

    except Exception as e:
        return {"status": "error", "message": str(e)}
    