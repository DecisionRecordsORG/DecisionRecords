/**
 * Labels, placeholder and helper text for the decision form fields.
 *
 * The decision modal and the full-page decision form are separate components
 * that must describe the fields in the same words. Both read this copy.
 *
 * This is the General decision template: the wording for any team recording
 * any kind of decision (a pricing change, a supplier choice, a hiring policy),
 * not only software teams. A tenant can choose another template; the forms
 * then take their copy from the API (see decision-template.service.ts) and
 * use this one only until it has loaded. It must stay equal to the General
 * template in decision_templates.py; a backend test compares the two.
 */
export interface DecisionFieldCopy {
  label: string;
  placeholder: string;
  hint: string;
}

export type DecisionFormCopy = Readonly<Record<'title' | 'context' | 'decision' | 'consequences', DecisionFieldCopy>>;

export const DECISION_FORM_COPY: DecisionFormCopy = {
  title: {
    label: 'Title',
    placeholder: 'For example: Move to quarterly pricing reviews',
    hint: 'A short name people will recognise in a list.'
  },
  context: {
    label: 'Context',
    placeholder: 'What prompted this decision? Describe the situation, the problem and anything that limits your options.',
    hint: 'The background someone needs to understand why this came up.'
  },
  decision: {
    label: 'Decision',
    placeholder: 'What did you decide? State the choice plainly and mention the options you turned down.',
    hint: 'What was decided, in words that make sense on their own.'
  },
  consequences: {
    label: 'Consequences',
    placeholder: 'What changes because of this? Include the benefits, the costs and the risks you accept.',
    hint: 'What follows from the decision, good and bad.'
  }
};
