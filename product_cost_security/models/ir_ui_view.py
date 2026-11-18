# Copyright 2024 Moduon Team S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0)
import re

from odoo import models

_DEFAULT_PRICE_RE = re.compile(
    r",\s*['\"]default_price['\"]\s*:\s*standard_price"
    r"|['\"]default_price['\"]\s*:\s*standard_price\s*,?"
)
_COST_GROUP = "product_cost_security.group_product_cost"


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    def _pcs_strip_default_price(self, node):
        for field_node in node.iter("field"):
            if field_node.get("name") not in ("seller_ids", "variant_seller_ids"):
                continue
            ctx = field_node.get("context")
            if ctx and "default_price" in ctx and "standard_price" in ctx:
                field_node.set("context", _DEFAULT_PRICE_RE.sub("", ctx))

    def _pcs_patch_product_cost_nodes(self, root, model_name, strip_default_price=False):
        if model_name not in ("product.template", "product.product"):
            return
        # hr_expense references standard_price in <span invisible="standard_price == 0">
        # under base.group_user; scope it to the cost group to match standard_price.
        for span in root.iter("span"):
            if span.get("invisible") == "standard_price == 0" and not span.get("groups"):
                span.set("groups", _COST_GROUP)
        if strip_default_price:
            self._pcs_strip_default_price(root)

    # Align core product views (hr_expense/purchase) with standard_price group
    # restrictions during view validation so upgrades do not emit false warnings.
    def _validate_view(self, node, model_name, view_type=None, editable=True, node_info=None):
        if not node_info:
            self._pcs_patch_product_cost_nodes(node, model_name, strip_default_price=True)
        return super()._validate_view(
            node, model_name, view_type=view_type, editable=editable, node_info=node_info
        )

    # Apply the hr_expense span group restriction during cached postprocessing
    # (and strip purchase context default_price when computing warning_info).
    def _postprocess_view(self, node, model_name, editable=True, node_info=None, **options):
        if not node_info:
            self._pcs_patch_product_cost_nodes(
                node,
                model_name,
                strip_default_price=bool(options.get("is_compute_warning_info")),
            )
        return super()._postprocess_view(
            node, model_name, editable=editable, node_info=node_info, **options
        )

    # Remove 'default_price': standard_price from seller_ids/variant_seller_ids context
    # for users without cost access so adding vendors does not raise NameError.
    def _postprocess_access_rights(self, tree):
        if (
            tree.get("model_access_rights") in ("product.template", "product.product")
            and not self.env.user.has_group(_COST_GROUP)
        ):
            self._pcs_strip_default_price(tree)
        return super()._postprocess_access_rights(tree)

    # Tag injected missing <field> nodes for standard_price with its field groups
    # so _postprocess_access_rights removes them for users without cost access.
    def _add_missing_fields(self, node, name_manager):
        missing_fields = super()._add_missing_fields(node, name_manager)
        for field_name, (missing_groups, _reasons) in missing_fields.items():
            if missing_groups is not False:
                # Core already set a __groups_key__ for this node.
                continue
            field_groups = name_manager._get_field_groups(field_name)
            if field_groups.is_empty() or field_groups.is_universal():
                continue
            for child in node.iter("field"):
                if child.get("name") != field_name or not child.get("invisible"):
                    continue
                if child.get("__groups_key__"):
                    continue
                child.set("__groups_key__", field_groups.key)
                break
        return missing_fields
