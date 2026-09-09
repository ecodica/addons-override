# TODO: Just a skech , idea, WIP

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home


class CustomHome(Home):
    @http.route('/web/login', type='http', auth="none")
    def web_login(self, redirect=None, **kw):
        # 1. Get the user's real IP address
        # Use X-Forwarded-For if you are behind Nginx or Cloudflare
        client_ip = request.httprequest.environ.get('HTTP_X_FORWARDED_FOR', request.httprequest.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

        # 2. Check if this IP is mapped to an Odoo user profile
        # Note: Requires adding an 'allowed_ip' field to the res.users model
        if not kw.get('login'):
            allowed_ip = request.env['allowed.ips'].sudo().search([
                ('ip_address', '=', client_ip)
            ], limit=1)

            if allowed_ip and allowed_ip.user_ip_id.auto_username:
                # Prefill the login key inside the dictionary passed to the template
                kw['login'] = allowed_ip.user_ip_id.login

        # 3. Hand the request back to Odoo's native login rendering
        return super(CustomHome, self).web_login(redirect=redirect, **kw)
