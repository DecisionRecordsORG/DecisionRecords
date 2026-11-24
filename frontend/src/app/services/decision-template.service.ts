import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, retry, shareReplay } from 'rxjs';
import { DECISION_FORM_COPY, DecisionFormCopy } from '../components/shared/decision-form-copy';

/**
 * Decision templates: the headings, prompts, example titles and decision
 * types a tenant sees for its decisions. The catalogue lives in the backend
 * (decision_templates.py) and is read from the API; nothing is duplicated here
 * except the General copy the forms show until the template has loaded.
 */
export interface DecisionTemplateField {
  placeholder: string;
  hint: string;
}

export interface DecisionTemplateSection extends DecisionTemplateField {
  label: string;
}

export interface DecisionTemplate {
  id: string;
  label: string;
  description: string;
  title: DecisionTemplateField;
  sections: {
    context: DecisionTemplateSection;
    decision: DecisionTemplateSection;
    consequences: DecisionTemplateSection;
  };
  decision_types: string[];
  suggested_pack_ids: string[];
  suggested_packs: { id: string; label: string }[];
  example_titles: string[];
  caution: string | null;
  is_default: boolean;
}

export interface IndustrySection {
  code: string;   // NACE Rev. 2.1 section letter, A to V
  title: string;  // Official English title, shown unchanged
  suggested_template_id: string;
}

export interface DecisionTemplateCatalog {
  templates: DecisionTemplate[];
  default_template_id: string;
  industries: IndustrySection[];
  industry_credit: string;
  guarantee: string;
}

/** GET /api/tenant/decision-template */
export interface TenantDecisionTemplate {
  template_id: string;
  template_chosen: boolean;
  template: DecisionTemplate;
  industry: string | null;
  industry_title: string | null;
  suggested_template_id: string;
  guarantee: string;
  can_manage: boolean;
  show_notice: boolean;
  // Only on the answer to a save
  message?: string;
  added_pack_ids?: string[];
}

/** PUT /api/tenant/decision-template: a field that is left out keeps its value. */
export interface TenantDecisionTemplateUpdate {
  template_id?: string | null;
  industry?: string | null;
  enable_suggested_packs?: boolean;
}

/** POST /api/tenant/decisions/bulk-type */
export interface BulkDecisionTypeResult {
  message: string;
  decision_type: string | null;
  updated: number;
  unchanged: number;
  skipped_ids: number[];
}

/** The server refuses a larger batch. */
export const BULK_DECISION_TYPE_MAX = 200;

/** The form copy (labels, placeholders, hints) for a template; General while none has loaded. */
export function formCopyFor(template: DecisionTemplate | null | undefined): DecisionFormCopy {
  if (!template) {
    return DECISION_FORM_COPY;
  }
  return {
    title: { label: DECISION_FORM_COPY.title.label, ...template.title },
    context: { ...template.sections.context },
    decision: { ...template.sections.decision },
    consequences: { ...template.sections.consequences }
  };
}

/**
 * The types to offer for one decision: the template's list, plus the type the
 * decision already has when the template does not list it (a type kept from
 * an earlier template is shown as it is and can stay).
 */
export function decisionTypeOptions(
  template: DecisionTemplate | null | undefined,
  storedType: string | null | undefined
): string[] {
  const types = [...(template?.decision_types || [])];
  if (storedType && !types.includes(storedType)) {
    types.push(storedType);
  }
  return types;
}

@Injectable({
  providedIn: 'root'
})
export class DecisionTemplateService {
  private catalog$: Observable<DecisionTemplateCatalog> | null = null;

  constructor(private http: HttpClient) {}

  /** The templates and the industry list. Static, so it is fetched once. */
  getCatalog(): Observable<DecisionTemplateCatalog> {
    if (!this.catalog$) {
      this.catalog$ = this.http
        .get<DecisionTemplateCatalog>('/api/decision-templates/catalog')
        .pipe(shareReplay({ bufferSize: 1, refCount: false }));
    }
    return this.catalog$;
  }

  /**
   * The signed-in member's tenant template. Not cached: an admin may have just changed it.
   * Tried up to three times: when it fails the forms fall back to the General headings,
   * which would be the wrong headings for a tenant on another template.
   */
  getTenantTemplate(): Observable<TenantDecisionTemplate> {
    return this.http
      .get<TenantDecisionTemplate>('/api/tenant/decision-template')
      .pipe(retry({ count: 2, delay: 400 }));
  }

  updateTenantTemplate(update: TenantDecisionTemplateUpdate): Observable<TenantDecisionTemplate> {
    return this.http.put<TenantDecisionTemplate>('/api/tenant/decision-template', update);
  }

  dismissNotice(): Observable<TenantDecisionTemplate> {
    return this.http.post<TenantDecisionTemplate>('/api/tenant/decision-template/dismiss-notice', {});
  }

  /** Set (or with null, clear) the type of several decisions. Admins and stewards only. */
  bulkSetDecisionType(decisionIds: number[], decisionType: string | null): Observable<BulkDecisionTypeResult> {
    return this.http.post<BulkDecisionTypeResult>('/api/tenant/decisions/bulk-type', {
      decision_ids: decisionIds,
      decision_type: decisionType
    });
  }
}
