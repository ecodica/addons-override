# Part of PraetorX. See LICENSE file for full copyright and licensing details.
from odoo import fields, models

from odoo.addons.ai.utils import llm_providers


def _embedding_model_selection(self):
    # Odoo builds EMBEDDING_MODELS_SELECTION once at import time; read the
    # live provider list so endpoint embedding models become selectable.
    return [(p.embedding_model, p.display_name) for p in llm_providers.PROVIDERS]


class AIEmbedding(models.Model):
    _inherit = "ai.embedding"

    embedding_model = fields.Selection(selection=_embedding_model_selection)
