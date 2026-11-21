/**
 * Days a deleted decision is kept before it is permanently erased.
 * Mirrors `retention_days` in `api_delete_decision` (app.py); keep the two in step.
 */
export const DECISION_DELETE_RETENTION_DAYS = 30;

/**
 * Confirmation copy for deleting a decision.
 *
 * Deletion is a soft delete: the record is hidden straight away and purged once the
 * retention window has passed. There is no restore action in the app or the API, so
 * the copy must not promise one.
 */
export function buildDecisionDeleteMessage(displayId: string): string {
  return `Delete ${displayId}? It will be removed from the decision list for everyone straight away ` +
    `and permanently erased after ${DECISION_DELETE_RETENTION_DAYS} days. ` +
    `There is no restore option in the app. Until it is erased, only the people who run this ` +
    `Decision Records installation can recover it.`;
}
