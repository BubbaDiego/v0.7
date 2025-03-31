import os
import json
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from twilio.rest import Client

# Import constants from your config_constants module
from config.config_constants import COM_CONFIG_PATH

# Configure module-level logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("xCom")


def load_com_config():
    """
    Loads the communication configuration from the JSON file defined by COM_CONFIG_PATH.
    Includes enhanced error detection for missing files and JSON decode errors.
    """
    try:
        # Check if the configuration file exists.
        if not COM_CONFIG_PATH.exists():
            raise FileNotFoundError(f"Configuration file not found at {COM_CONFIG_PATH}")

        with open(COM_CONFIG_PATH, "r", encoding="utf-8") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError as jde:
                raise ValueError(f"Invalid JSON in configuration file at {COM_CONFIG_PATH}: {jde}")

        logger.debug("Communication configuration loaded successfully from %s", COM_CONFIG_PATH)
        return config
    except Exception as e:
        logger.error("Failed to load communication configuration: %s", e, exc_info=True)
        # Optionally, re-raise the exception or return a default configuration
        return {}


def send_email(recipient: str, subject: str, body: str, config: dict = None) -> bool:
    """
    Sends an email using the SMTP provider defined in the configuration.
    If 'recipient' is empty, the default recipient from configuration is used.
    """
    if config is None:
        config = load_com_config()

    email_config = config.get("communication", {}).get("providers", {}).get("email", {})
    if not email_config.get("enabled", False):
        logger.error("Email provider is disabled in configuration.")
        return False

    smtp_config = email_config.get("smtp", {})
    server = smtp_config.get("server")
    port = smtp_config.get("port")
    username = smtp_config.get("username")
    password = smtp_config.get("password")
    if not recipient:
        recipient = smtp_config.get("default_recipient")

    if not all([server, port, username, password, recipient]):
        logger.error("Missing email configuration details.")
        return False

    try:
        msg = MIMEText(body, "plain")
        msg["Subject"] = subject
        msg["From"] = username
        msg["To"] = recipient

        context = ssl.create_default_context()
        with smtplib.SMTP(server, port) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.login(username, password)
            smtp.send_message(msg)
        logger.info("Email sent successfully to %s", recipient)
        return True
    except Exception as e:
        logger.error("Error sending email: %s", e, exc_info=True)
        return False


def send_sms(recipient: str, message: str, config: dict = None) -> bool:
    """
    Sends an SMS via an email-to-SMS gateway.
    The carrier gateway is appended to the recipient phone number.
    If recipient is empty, a default is used.
    This function reuses the email sending functionality.
    """
    if config is None:
        config = load_com_config()

    sms_config = config.get("communication", {}).get("providers", {}).get("sms", {})
    if not sms_config.get("enabled", False):
        logger.error("SMS provider is disabled in configuration.")
        return False

    carrier_gateway = sms_config.get("carrier_gateway")
    if not recipient:
        recipient = sms_config.get("default_recipient")
    if not carrier_gateway or not recipient:
        logger.error("Missing SMS configuration details.")
        return False

    # Construct the email address for SMS delivery
    sms_email = f"{recipient}@{carrier_gateway}"
    subject = ""  # Typically, SMS messages don't need a subject
    # Reuse the send_email function to send the SMS as an email
    return send_email(sms_email, subject, message, config=config)


def send_call(recipient: str, message: str, config: dict = None):
    """
    Triggers a phone call via Twilio Studio.
    If recipient is empty, the default phone number from configuration is used.
    Returns the execution SID on success, or False on failure.
    """
    if config is None:
        config = load_com_config()

    twilio_config = config.get("communication", {}).get("providers", {}).get("twilio", {})
    if not twilio_config.get("enabled", False):
        logger.error("Twilio provider is disabled in configuration.")
        return False

    account_sid = twilio_config.get("account_sid")
    auth_token = twilio_config.get("auth_token")
    flow_sid = twilio_config.get("flow_sid")
    default_to_phone = twilio_config.get("default_to_phone")
    default_from_phone = twilio_config.get("default_from_phone")

    if not recipient:
        recipient = default_to_phone

    if not all([account_sid, auth_token, flow_sid, recipient, default_from_phone]):
        logger.error("Missing Twilio configuration details.")
        return False

    try:
        client = Client(account_sid, auth_token)
        execution = client.studio.v2.flows(flow_sid).executions.create(
            to=recipient,
            from_=default_from_phone,
            parameters={"custom_message": message}
        )
        logger.info("Call triggered successfully. Execution SID: %s", execution.sid)
        return execution.sid
    except Exception as e:
        logger.error("Error sending call via Twilio: %s", e, exc_info=True)
        return False


# For testing purposes when running this module directly
if __name__ == "__main__":
    config = load_com_config()
    # Test sending an email
    email_result = send_email("", "Test Subject", "Hello, this is a test email.", config=config)
    logger.info("Email result: %s", email_result)

    # Test sending an SMS
    sms_result = send_sms("", "This is a test SMS message.", config=config)
    logger.info("SMS result: %s", sms_result)

    # Test triggering a call
    call_result = send_call("", "This is a test call message.", config=config)
    logger.info("Call result: %s", call_result)
