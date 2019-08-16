# -*- coding: utf-8 -*-
# For copyright and license notices, see __manifest__.py file in module root

import json
import re
import uuid
from functools import partial

from lxml import etree
from dateutil.relativedelta import relativedelta
from werkzeug.urls import url_encode

from odoo import api, exceptions, fields, models, _
from odoo.tools import float_is_zero, float_compare, pycompat
from odoo.tools.misc import formatLang

from odoo.exceptions import AccessError, UserError, RedirectWarning, \
    ValidationError, Warning

from odoo.addons import decimal_precision as dp
import logging

DISCOUNTS = [
             ('3.0', '3 %'),
             ('5.0', '5 %'),
             ('10.0', '10 %')]


class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    discount1 = fields.Selection(
        DISCOUNTS,
        string='Desc A',

    )
    discount2 = fields.Selection(
        DISCOUNTS,
        string='Desc B',

    )
    discount3 = fields.Selection(
        DISCOUNTS,
        string='Desc C',

    )

    @api.one
    @api.depends('price_unit', 'discount', 'discount1', 'discount2',
                 'discount3', 'invoice_line_tax_ids', 'quantity',
                 'product_id', 'invoice_id.partner_id',
                 'invoice_id.currency_id', 'invoice_id.company_id',
                 'invoice_id.date_invoice', 'invoice_id.date')
    def _compute_price(self):

        currency = self.invoice_id and self.invoice_id.currency_id or None

        discount0 = self.discount or 0.0 / 100.0

        discount1 = float(self.discount1) /100 if self.discount1 else 0
        discount2 = float(self.discount2) /100 if self.discount2 else 0
        discount3 = float(self.discount3) /100 if self.discount3 else 0

        disc = (1 - discount0) * (1 - discount1) * \
               (1 - discount2) * (1 - discount3)
        price = self.price_unit * disc

        taxes = False
        if self.invoice_line_tax_ids:
            _ = self.invoice_line_tax_ids
            taxes = _.compute_all(price, currency,
                                  self.quantity,
                                  product=self.product_id,
                                  partner=self.invoice_id.partner_id)
        self.price_subtotal = price_subtotal_signed = taxes[
            'total_excluded'] if taxes else self.quantity * price
        self.price_total = taxes[
            'total_included'] if taxes else self.price_subtotal
        if self.invoice_id.currency_id and self.invoice_id.currency_id != \
            self.invoice_id.company_id.currency_id:
            price_subtotal_signed = self.invoice_id.currency_id.with_context(
                date=self.invoice_id._get_currency_rate_date()).compute(
                price_subtotal_signed, self.invoice_id.company_id.currency_id)
        sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
        self.price_subtotal_signed = price_subtotal_signed * sign
