import { DECISION_FORM_COPY } from './decision-form-copy';

describe('DECISION_FORM_COPY', () => {
  const entries = Object.entries(DECISION_FORM_COPY);
  const allText = entries.flatMap(([, copy]) => [copy.placeholder, copy.hint]);

  it('gives every decision field a placeholder and a hint', () => {
    expect(entries.map(([field]) => field)).toEqual(['title', 'context', 'decision', 'consequences']);
    for (const text of allText) {
      expect(text.trim().length).toBeGreaterThan(10);
    }
  });

  it('is written for any team, not only software teams', () => {
    const softwareOnly = /architect|ADR|software|technical|system|implement|code|deploy/i;
    for (const text of allText) {
      expect(text).not.toMatch(softwareOnly);
    }
  });

  it('follows the copy style: no exclamation marks, em dashes or trailing ellipses', () => {
    for (const text of allText) {
      expect(text).not.toMatch(/!|—|\.\.\.|…/);
    }
  });
});
