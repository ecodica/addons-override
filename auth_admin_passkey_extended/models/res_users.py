# Copyright 2025 Ecodica d.o.o.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.http import request
from odoo.tools import config


class ResUsers(models.Model):
    _inherit = "res.users"

    def _mfa_url(self):
        """Skip TOTP/2FA when admin passkey is used and config allows it."""
        if request and request.session.get("ignore_totp"):
            return None
        return super()._mfa_url()

    @api.model
    def _send_email_passkey(self, login_user):
        """Set ignore_totp session flag when admin passkey authenticates.

        This method is called by auth_admin_passkey's _check_credentials
        only when the passkey matches, making it the ideal hook point to
        set the session flag before _mfa_url is evaluated.
        """
        if request:
            request.session["ignore_totp"] = config.get(
                "auth_admin_passkey_ignore_totp", False
            )
        return super()._send_email_passkey(login_user)
