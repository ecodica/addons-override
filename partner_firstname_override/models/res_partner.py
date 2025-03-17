from odoo import models, api

class ResPartner(models.Model):
    _inherit = 'res.partner'
    _description ='Inherit res.partner'
    
    @api.model
    def default_get(self, fields_list):
        '''Override the OCA default_get method to add the name field to avoid duplicating the "name" field appendance to fields_list.'''
        fields_list = list(fields_list)
        if ("firstname" in fields_list or "lastname" in fields_list) and "name" not in fields_list:
            fields_list.append("name")
        result = super(ResPartner, self).default_get(fields_list)
        inverted = self._get_inverse_name(
            self._get_whitespace_cleaned_name(result.get("name", "")),
            result.get("is_company", False)
        )
        for field in list(inverted.keys()):
            if field in fields_list:
                result[field] = inverted.get(field)
        return result