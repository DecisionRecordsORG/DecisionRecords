import { DECISION_FORM_COPY } from '../components/shared/decision-form-copy';
import { DecisionTemplate, DecisionTemplateCatalog, TenantDecisionTemplate } from './decision-template.service';

/**
 * Test data for specs of components that read the decision template. Shaped
 * like the API answers; the real catalogue lives in decision_templates.py.
 */
export const GENERAL_TEMPLATE: DecisionTemplate = {
  id: 'general',
  label: 'General',
  description: 'Fits any kind of decision.',
  title: { placeholder: DECISION_FORM_COPY.title.placeholder, hint: DECISION_FORM_COPY.title.hint },
  sections: {
    context: { ...DECISION_FORM_COPY.context },
    decision: { ...DECISION_FORM_COPY.decision },
    consequences: { ...DECISION_FORM_COPY.consequences }
  },
  decision_types: ['Policy', 'Spending'],
  suggested_pack_ids: ['core', 'people'],
  suggested_packs: [{ id: 'core', label: 'Core' }, { id: 'people', label: 'People & Policy' }],
  example_titles: ['Move to quarterly pricing reviews', 'Appoint a second packaging supplier for the autumn range'],
  caution: null,
  is_default: true
};

export const GOVERNANCE_TEMPLATE: DecisionTemplate = {
  id: 'governance',
  label: 'Governance and committee',
  description: 'For boards, trustees, committees and officers.',
  title: {
    placeholder: 'For example: Adopt the revised safeguarding policy from 1 September',
    hint: 'A short name people will recognise in a list.'
  },
  sections: {
    context: { label: 'Matter and background', placeholder: 'What was put for decision, and by whom?', hint: 'What was put for decision.' },
    decision: { label: 'Decision and reasons', placeholder: 'Give the decision in its exact wording.', hint: 'The exact wording and the reasons.' },
    consequences: {
      label: 'Alternatives, interests and implications',
      placeholder: 'Which alternatives were considered and rejected?',
      hint: 'Alternatives rejected and implications.'
    }
  },
  decision_types: ['Appointment', 'Service change'],
  suggested_pack_ids: ['core', 'people', 'finance'],
  suggested_packs: [
    { id: 'core', label: 'Core' },
    { id: 'people', label: 'People & Policy' },
    { id: 'finance', label: 'Finance & Procurement' }
  ],
  example_titles: ['Adopt the revised safeguarding policy from 1 September', 'Award the grounds maintenance contract for 2027 to 2030'],
  caution: 'Do not record decisions about identifiable patients, pupils or service users here.',
  is_default: false
};

export const TEMPLATE_CATALOG: DecisionTemplateCatalog = {
  templates: [GENERAL_TEMPLATE, GOVERNANCE_TEMPLATE],
  default_template_id: 'general',
  industries: [
    { code: 'C', title: 'Manufacturing', suggested_template_id: 'general' },
    { code: 'Q', title: 'Education', suggested_template_id: 'governance' }
  ],
  industry_credit: 'Industry sections: NACE Rev. 2.1, Eurostat, CC BY 4.0',
  guarantee: 'Changing the template changes headings and prompts only. Your decisions are not altered, and you can change back at any time.'
};

export function tenantTemplate(overrides: Partial<TenantDecisionTemplate> = {}): TenantDecisionTemplate {
  return {
    template_id: 'general',
    template_chosen: false,
    template: GENERAL_TEMPLATE,
    industry: null,
    industry_title: null,
    suggested_template_id: 'general',
    guarantee: TEMPLATE_CATALOG.guarantee,
    can_manage: false,
    show_notice: false,
    ...overrides
  };
}

export function governanceTenantTemplate(overrides: Partial<TenantDecisionTemplate> = {}): TenantDecisionTemplate {
  return tenantTemplate({
    template_id: 'governance',
    template_chosen: true,
    template: GOVERNANCE_TEMPLATE,
    ...overrides
  });
}
