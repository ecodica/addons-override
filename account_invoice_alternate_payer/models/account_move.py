# Copyright 2018 Eficent Business and IT Consulting Services, S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    alternate_payer_id = fields.Many2one(
        "res.partner",
        string="Alternate Payer",
        inverse="_inverse_alternate_payer_id",
        readonly=True,
        states={"draft": [("readonly", False)]},
        help="If set, this will be the partner that we expect to pay or to "
        "be paid by. If not set, the payor is by default the "
        "commercial",
    )

    @api.depends("commercial_partner_id", "alternate_payer_id")
    def _compute_bank_partner_id(self):
        super()._compute_bank_partner_id()
        for move in self:
            if move.is_outbound() and move.alternate_payer_id:
                move.bank_partner_id = move.alternate_payer_id

    # no need for this
    # @api.onchange("alternate_payer_id")
    # def _onchange_alternate_payer_id(self):
    #     return self._onchange_partner_id()

    @api.onchange('alternate_payer_id')
    def _inverse_alternate_payer_id(self):
        for invoice in self:
            if invoice.is_invoice(True):
                for line in (invoice.line_ids + invoice.invoice_line_ids):
                    if line.account_id.account_type in ('asset_receivable', 'liability_payable') and \
                            line.partner_id != invoice.alternate_payer_id:
                        line.partner_id = invoice.alternate_payer_id
                        # line._inverse_partner_id()

    # Not existing in v16, nor needed
    # def _recompute_payment_terms_lines(self):
    #     super()._recompute_payment_terms_lines()
    #     for invoice in self:
    #         if invoice.alternate_payer_id:
    #             invoice.line_ids.filtered(
    #                 lambda r: r.account_id.user_type_id.type
    #                 in ("receivable", "payable")
    #             ).update({"partner_id": invoice.alternate_payer_id.id})

    # ported
    def _compute_payments_widget_to_reconcile_info(self):
        super(
            AccountMove, self.filtered(lambda r: not r.alternate_payer_id)
        )._compute_payments_widget_to_reconcile_info()
        for move in self.filtered("alternate_payer_id"):
            move.invoice_outstanding_credits_debits_widget = False
            move.invoice_has_outstanding = False

            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue

            pay_term_lines = move.line_ids\
                .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))

            domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.alternate_payer_id.id),
                ('reconciled', '=', False),
                '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
            ]

            payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

            if move.is_inbound():
                domain.append(('balance', '<', 0.0))
                payments_widget_vals['title'] = _('Outstanding credits')
            else:
                domain.append(('balance', '>', 0.0))
                payments_widget_vals['title'] = _('Outstanding debits')

            for line in self.env['account.move.line'].search(domain):

                if line.currency_id == move.currency_id:
                    # Same foreign currency.
                    amount = abs(line.amount_residual_currency)
                else:
                    # Different foreign currencies.
                    amount = line.company_currency_id._convert(
                        abs(line.amount_residual),
                        move.currency_id,
                        move.company_id,
                        line.date,
                    )

                if move.currency_id.is_zero(amount):
                    continue

                payments_widget_vals['content'].append({
                    'journal_name': line.ref or line.move_id.name,
                    'amount': amount,
                    'currency_id': move.currency_id.id,
                    'id': line.id,
                    'move_id': line.move_id.id,
                    'date': fields.Date.to_string(line.date),
                    'account_payment_id': line.payment_id.id,
                })

            if not payments_widget_vals['content']:
                continue

            move.invoice_outstanding_credits_debits_widget = payments_widget_vals
            move.invoice_has_outstanding = True



