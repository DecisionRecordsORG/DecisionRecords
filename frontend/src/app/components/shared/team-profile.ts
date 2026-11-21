/**
 * Team profile: the two optional questions a tenant admin can answer about
 * the team. The size codes match TEAM_SIZE_OPTIONS in models.py; the backend
 * rejects any other value.
 */
export interface TeamSizeOption {
  code: string;
  label: string;
}

export const TEAM_SIZE_OPTIONS: TeamSizeOption[] = [
  { code: '1-5', label: '1 to 5 people' },
  { code: '6-25', label: '6 to 25 people' },
  { code: '26-100', label: '26 to 100 people' },
  { code: '101-500', label: '101 to 500 people' },
  { code: '501+', label: 'More than 500 people' }
];

export const TEAM_FOCUS_MAX_LENGTH = 200;

export const TEAM_FOCUS_QUESTION = 'What does your team make decisions about?';
export const TEAM_FOCUS_PLACEHOLDER = 'For example: hiring, supplier contracts, product pricing';

export interface TeamProfileAnswers {
  team_focus?: string | null;
  team_size?: string | null;
}

/**
 * The request body for the answers that were actually given, or null when
 * nothing was answered (so no request is made and nothing is overwritten).
 */
export function teamProfileBody(teamFocus: string | null | undefined, teamSize: string | null | undefined): TeamProfileAnswers | null {
  const body: TeamProfileAnswers = {};
  const focus = (teamFocus || '').trim();
  if (focus) {
    body.team_focus = focus.slice(0, TEAM_FOCUS_MAX_LENGTH);
  }
  if (teamSize && TEAM_SIZE_OPTIONS.some(option => option.code === teamSize)) {
    body.team_size = teamSize;
  }
  return Object.keys(body).length > 0 ? body : null;
}
