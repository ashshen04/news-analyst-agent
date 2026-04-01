"""Tests for notifier.py — email sending with mocked SMTP."""

from unittest.mock import MagicMock, patch


class TestSendEmail:
    @patch("notifier.smtplib.SMTP_SSL")
    def test_sends_email(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        from notifier import send_email

        send_email("Subject", "<p>Body</p>", "user@example.com")
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()

    @patch("notifier.smtplib.SMTP_SSL")
    def test_accepts_list_of_addresses(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        from notifier import send_email

        send_email("Subject", "<p>Body</p>", ["a@b.com", "c@d.com"])
        msg = mock_server.send_message.call_args[0][0]
        assert "a@b.com" in msg["To"]
        assert "c@d.com" in msg["To"]
