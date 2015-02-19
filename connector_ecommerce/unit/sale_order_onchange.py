# -*- coding: utf-8 -*-
##############################################################################
#
#   connector-ecommerce for OpenERP
#   Copyright (C) 2013-TODAY Akretion <http://www.akretion.com>.
#     @author Sébastien BEAU <sebastien.beau@akretion.com>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of the
#   License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.addons.connector.connector import ConnectorUnit


class OnChangeManager(ConnectorUnit):
    pass


class SaleOrderOnChange(OnChangeManager):
    _model_name = None

    def _get_partner_id_onchange_param(self, order):
        """ Prepare the arguments for calling the partner_id change
        on sale order. You can overwrite this method in your own
        module if they modify the onchange signature

        :param order: a dictionary of the value of your sale order
        :type: dict

        :return: a tuple of args and kwargs for the onchange
        :rtype: tuple
        """
        args = [
            order.partner_id.id,
        ]
        kwargs = {}
        return args, kwargs

    def _play_order_onchange(self, order):
        """ Play the onchange of the sale order

        :param order: a dictionary of the value of your sale order
        :type: dict

        :return: the value of the sale order updated with the onchange result
        :rtype: dict
        """
        # Play partner_id onchange
        args, kwargs = self._get_partner_id_onchange_param(order)
        values = order.onchange_partner_id(*args, **kwargs)
        for key, value in values.get('value', {}).iteritems():
            if not getattr(order, key):
                setattr(order, key, value)

        if order.payment_method_id:
            order.onchange_payment_method_id_set_payment_term()

        if order.workflow_process_id:
            order.onchange_workflow_process_id()
        return order

    def _get_product_id_onchange_param(self, line, previous_lines, order):
        """ Prepare the arguments for calling the product_id change
        on sale order line. You can overwrite this method in your own
        module if they modify the onchange signature

        :param line: the sale order line to process
        :type: dict
        :param previous_lines: list of dict of the previous lines processed
        :type: list
        :param order: data of the sale order
        :type: dict

        :return: a tuple of args and kwargs for the onchange
        :rtype: tuple
        """
        args = [
            order.pricelist_id.id,
            line.product_id.id,
        ]

        # used in sale_markup: this is to ensure the unit price
        # sent by the e-commerce connector is used for markup calculation
        onchange_context = self.env.context.copy()
        if line.price_unit:
            onchange_context.update({'unit_price': line.price_unit,
                                     'force_unit_price': True})

        uos_qty = line.product_uos_qty
        if not uos_qty:
            uos_qty = line.product_uom_qty

        kwargs = {
            'qty': line.product_uom_qty,
            'uom': line.product_uom.id,
            'qty_uos': uos_qty,
            'uos': line.product_uos.id,
            'name': line.name,
            'partner_id': order.partner_id.id,
            'lang': False,
            'update_tax': True,
            'date_order': order.date_order,
            'packaging': line.product_packaging.id,
            'fiscal_position': order.fiscal_position.id,
            'flag': False,
            'context': onchange_context,
        }
        return args, kwargs

    def _play_line_onchange(self, line, previous_lines, order):
        """ Play the onchange of the sale order line

        :param line: the sale order line to process
        :type: dict
        :param previous_lines: list of dict of the previous line processed
        :type: list
        :param order: data of the sale order
        :type: dict

        :return: the value of the sale order updated with the onchange result
        :rtype: dict
        """
        # Play product_id onchange
        args, kwargs = self._get_product_id_onchange_param(line,
                                                           previous_lines,
                                                           order)
        context = kwargs.pop('context', {})
        values = line.with_context(context).product_id_change(*args, **kwargs)
        for key, value in values.get('value', {}).iteritems():
            if not getattr(line, key):
                setattr(line, key, value)
        return line

    def play(self, order, order_lines=None):
        """ Play the onchange of the sale order and it's lines

        It expects to receive a recordset containing one sale order.
        It could have been generated with
        ``self.env['sale.order'].new(values)`` or
        ``self.env['sale.order'].create(values)``.

        :param order: data of the sale order
        :type: recordset
        :param order_lines: data of the sale order lines
        :type: recordset

        :return: the sale order updated by the onchanges
        :rtype: recordset
        """
        # play onchange on sale order
        order = self._play_order_onchange(order)
        processed_order_lines = self.env['sale.order.line'].browse()
        # we can have both backend-dependent and oerp-native order
        # lines.
        # oerp-native lines can have been added to map
        # shipping fees with an OpenERP Product
        all_lines = order.order_line
        if order_lines:
            all_lines |= order_lines
        for line in all_lines:
            # play onchange on sale order line
            new_line = self._play_line_onchange(line,
                                                processed_order_lines,
                                                order)
            processed_order_lines += new_line
            # in place modification of the sale order line in the list
        order.order_line = processed_order_lines
        return order
