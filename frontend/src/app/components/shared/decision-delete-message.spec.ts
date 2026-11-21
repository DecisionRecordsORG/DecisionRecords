import { buildDecisionDeleteMessage, DECISION_DELETE_RETENTION_DAYS } from './decision-delete-message';

describe('buildDecisionDeleteMessage', () => {
  it('names the decision and the real retention window', () => {
    const message = buildDecisionDeleteMessage('DR-12');

    expect(DECISION_DELETE_RETENTION_DAYS).toBe(30);
    expect(message).toContain('Delete DR-12?');
    expect(message).toContain('permanently erased after 30 days');
  });

  it('does not claim the delete is immediate and final, nor offer a restore', () => {
    const message = buildDecisionDeleteMessage('DR-12').toLowerCase();

    expect(message).not.toContain('cannot be undone');
    expect(message).toContain('no restore option in the app');
  });
});
