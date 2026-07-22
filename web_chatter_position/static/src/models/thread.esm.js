/** @odoo-module **/
/*
    Fix: concurrent "register_as_main_attachment" writes on account.move.

    When a record's chatter loads its attachments and no main attachment is set
    yet, WebClientViewAttachmentView auto-calls thread.setMainAttachment(), which
    RPCs ir.attachment.register_as_main_attachment -> writes
    account_move.message_main_attachment_id.

    With web_chatter_position several Chatter instances run simultaneously, and a
    full form `reload` (e.g. right after posting an invoice) tears down and
    recreates the thread while the previous instance's RPC may still be in flight.
    Two concurrent writes to the same account_move row race under PostgreSQL
    REPEATABLE READ and raise:

        could not serialize access due to concurrent update

    which rolls back one request and leaves the chatter widget blank until a
    manual reload. (See the comment in mazars_eco account_move.action_post, where
    the team worked around this with `soft_reload` — which then breaks for brand
    new, unsaved invoices.)

    This patch serializes the RPC per record: only one register_as_main_attachment
    call is in flight for a given thread at a time, and redundant calls that would
    set the attachment that is already main become no-ops. The in-flight set is
    module-scoped on purpose so it survives the thread being destroyed and
    recreated across a client-action reload (which is NOT a browser reload).
*/
import { registerPatch } from "@mail/model/model_core";

// Keyed by "model:id" of the thread whose main attachment is being registered.
const registeringMainAttachment = new Set();

registerPatch({
    name: "Thread",
    recordMethods: {
        /**
         * @override
         */
        async setMainAttachment(attachment) {
            // Idempotent: nothing to do if it is already the main attachment.
            if (!attachment || this.mainAttachment === attachment) {
                return;
            }
            const key = `${this.model}:${this.id}`;
            // A register RPC is already running for this record: update the local
            // state so the UI is consistent, but do not fire a second concurrent
            // write to account_move.message_main_attachment_id.
            if (registeringMainAttachment.has(key)) {
                this.update({ mainAttachment: attachment });
                return;
            }
            registeringMainAttachment.add(key);
            try {
                await this._super(attachment);
            } finally {
                registeringMainAttachment.delete(key);
            }
        },
    },
});
