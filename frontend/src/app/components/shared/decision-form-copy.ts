/**
 * Placeholder and helper text for the decision form fields.
 *
 * The decision modal and the full-page decision form are separate components
 * that must describe the fields in the same words. Both read this copy.
 *
 * The wording is for any team recording any kind of decision (a pricing
 * change, a supplier choice, a hiring policy), not only software teams.
 */
export interface DecisionFieldCopy {
  placeholder: string;
  hint: string;
}

export const DECISION_FORM_COPY: Readonly<Record<'title' | 'context' | 'decision' | 'consequences', DecisionFieldCopy>> = {
  title: {
    placeholder: 'For example: Move to quarterly pricing reviews',
    hint: 'A short name people will recognise in a list.'
  },
  context: {
    placeholder: 'What prompted this decision? Describe the situation, the problem and anything that limits your options.',
    hint: 'The background someone needs to understand why this came up.'
  },
  decision: {
    placeholder: 'What did you decide? State the choice plainly and mention the options you turned down.',
    hint: 'What was decided, in words that make sense on their own.'
  },
  consequences: {
    placeholder: 'What changes because of this? Include the benefits, the costs and the risks you accept.',
    hint: 'What follows from the decision, good and bad.'
  }
};
