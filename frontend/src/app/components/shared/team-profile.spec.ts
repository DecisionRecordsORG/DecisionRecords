import { TEAM_FOCUS_MAX_LENGTH, TEAM_SIZE_OPTIONS, teamProfileBody } from './team-profile';

describe('team profile', () => {
  it('offers the same size ranges the backend accepts', () => {
    expect(TEAM_SIZE_OPTIONS.map(option => option.code)).toEqual(['1-5', '6-25', '26-100', '101-500', '501+']);
    expect(TEAM_SIZE_OPTIONS.map(option => option.label)).toEqual([
      '1 to 5 people', '6 to 25 people', '26 to 100 people', '101 to 500 people', 'More than 500 people'
    ]);
  });

  describe('teamProfileBody', () => {
    it('is null when nothing was answered, so no request is made', () => {
      expect(teamProfileBody('', null)).toBeNull();
      expect(teamProfileBody('   ', null)).toBeNull();
      expect(teamProfileBody(null, undefined)).toBeNull();
      expect(teamProfileBody(undefined, '')).toBeNull();
    });

    it('sends only the answer that was given', () => {
      expect(teamProfileBody('Hiring', null)).toEqual({ team_focus: 'Hiring' });
      expect(teamProfileBody('', '6-25')).toEqual({ team_size: '6-25' });
    });

    it('sends both answers, trimmed', () => {
      expect(teamProfileBody('  Hiring and pay  ', '501+')).toEqual({ team_focus: 'Hiring and pay', team_size: '501+' });
    });

    it('leaves out a size that is not one of the listed ranges', () => {
      expect(teamProfileBody('Hiring', 'huge')).toEqual({ team_focus: 'Hiring' });
      expect(teamProfileBody('', 'huge')).toBeNull();
    });

    it('cuts an answer that is longer than the limit', () => {
      const body = teamProfileBody('x'.repeat(TEAM_FOCUS_MAX_LENGTH + 50), null);

      expect(body?.team_focus?.length).toBe(TEAM_FOCUS_MAX_LENGTH);
    });
  });
});
