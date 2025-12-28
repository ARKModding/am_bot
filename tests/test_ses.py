"""Tests for the ses (Simple Email Service) module."""

from unittest.mock import MagicMock, patch

from am_bot.ses import AWS_REGION, SENDER, send_email


class TestSendEmail:
    """Tests for the send_email function."""

    def test_sender_constant(self):
        """Test SENDER constant is set correctly."""
        assert SENDER == "no-reply@arkmodding.net"

    def test_aws_region_constant(self):
        """Test AWS_REGION constant is set correctly."""
        assert AWS_REGION == "us-west-1"

    @patch("am_bot.ses.boto3")
    def test_send_email_success(self, mock_boto3):
        """Test successful email sending."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.send_email.return_value = {"MessageId": "test-message-id"}

        send_email(
            to="user@example.com",
            subject="Test Subject",
            body_txt="Plain text body",
            body_html="<html><body>HTML body</body></html>",
        )

        mock_boto3.client.assert_called_once_with(
            "ses", region_name="us-west-1"
        )
        mock_client.send_email.assert_called_once_with(
            Destination={"ToAddresses": ["user@example.com"]},
            Message={
                "Body": {
                    "Html": {
                        "Charset": "utf-8",
                        "Data": "<html><body>HTML body</body></html>",
                    },
                    "Text": {"Charset": "utf-8", "Data": "Plain text body"},
                },
                "Subject": {"Charset": "utf-8", "Data": "Test Subject"},
            },
            Source="no-reply@arkmodding.net",
        )

    @patch("am_bot.ses.boto3")
    def test_send_email_client_error(self, mock_boto3):
        """Test email sending handles ClientError."""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        error_response = {
            "Error": {"Message": "Email address is not verified"}
        }
        mock_client.send_email.side_effect = ClientError(
            error_response, "SendEmail"
        )

        # Should not raise, just log warning
        send_email(
            to="unverified@example.com",
            subject="Test",
            body_txt="Text",
            body_html="<p>HTML</p>",
        )

        mock_client.send_email.assert_called_once()

    @patch("am_bot.ses.boto3")
    def test_send_email_with_special_characters(self, mock_boto3):
        """Test email sending with special characters in content."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.send_email.return_value = {"MessageId": "test-id"}

        subject = "Test with émojis 🎉 and spëcial chars"
        body_txt = "Line 1\nLine 2\n\tTabbed content"
        body_html = "<p>HTML with <strong>tags</strong> & entities</p>"

        send_email(
            to="user@example.com",
            subject=subject,
            body_txt=body_txt,
            body_html=body_html,
        )

        call_kwargs = mock_client.send_email.call_args[1]
        assert call_kwargs["Message"]["Subject"]["Data"] == subject
        assert call_kwargs["Message"]["Body"]["Text"]["Data"] == body_txt
        assert call_kwargs["Message"]["Body"]["Html"]["Data"] == body_html

    @patch("am_bot.ses.boto3")
    def test_send_email_uses_utf8_charset(self, mock_boto3):
        """Test that all content uses UTF-8 charset."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.send_email.return_value = {"MessageId": "test-id"}

        send_email(
            to="user@example.com",
            subject="Test",
            body_txt="Text",
            body_html="<p>HTML</p>",
        )

        call_kwargs = mock_client.send_email.call_args[1]
        message = call_kwargs["Message"]

        assert message["Subject"]["Charset"] == "utf-8"
        assert message["Body"]["Text"]["Charset"] == "utf-8"
        assert message["Body"]["Html"]["Charset"] == "utf-8"

    @patch("am_bot.ses.boto3")
    def test_send_email_empty_bodies(self, mock_boto3):
        """Test sending email with empty bodies."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.send_email.return_value = {"MessageId": "test-id"}

        send_email(
            to="user@example.com",
            subject="Empty content test",
            body_txt="",
            body_html="",
        )

        call_kwargs = mock_client.send_email.call_args[1]
        assert call_kwargs["Message"]["Body"]["Text"]["Data"] == ""
        assert call_kwargs["Message"]["Body"]["Html"]["Data"] == ""
