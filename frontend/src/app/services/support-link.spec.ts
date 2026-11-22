import { buildSupportUrl, supportPageAddress, HOSTED_SUPPORT_URL } from './support-link';

describe('support link', () => {
  const hosted = { marketing_pages: true };
  const selfHosted = { marketing_pages: false };

  describe('supportPageAddress', () => {
    it('is the website support page on the hosted service', () => {
      expect(HOSTED_SUPPORT_URL).toBe('https://decisionrecords.org/support');
      expect(supportPageAddress(hosted)).toBe('https://decisionrecords.org/support');
    });

    it('is nothing on a self-hosted installation with nothing configured', () => {
      expect(supportPageAddress(selfHosted)).toBeNull();
      expect(supportPageAddress({})).toBeNull();
      expect(supportPageAddress(null)).toBeNull();
      expect(supportPageAddress(undefined)).toBeNull();
    });

    it('uses a configured address on a self-hosted installation', () => {
      expect(supportPageAddress({ marketing_pages: false, support_url: ' https://help.example.org/it ' }))
        .toBe('https://help.example.org/it');
    });

    it('prefers a configured address over the hosted default', () => {
      expect(supportPageAddress({ marketing_pages: true, support_url: 'https://help.example.org' }))
        .toBe('https://help.example.org');
    });

    it('hides the link when the configured value is not an http(s) address', () => {
      expect(supportPageAddress({ marketing_pages: true, support_url: 'none' })).toBeNull();
      expect(supportPageAddress({ marketing_pages: true, support_url: 'javascript:alert(1)' })).toBeNull();
      expect(supportPageAddress({ marketing_pages: true, support_url: 'mailto:it@example.org' })).toBeNull();
    });

    it('ignores an empty or non-text configured value', () => {
      expect(supportPageAddress({ marketing_pages: true, support_url: '  ' })).toBe(HOSTED_SUPPORT_URL);
      expect(supportPageAddress({ marketing_pages: true, support_url: null })).toBe(HOSTED_SUPPORT_URL);
      expect(supportPageAddress({ marketing_pages: false, support_url: 42 })).toBeNull();
    });
  });

  describe('buildSupportUrl', () => {
    it('returns nothing when there is no support page', () => {
      expect(buildSupportUrl(selfHosted, { topic: 'signin', email: 'ada@acme.test', org: 'acme.test' })).toBeNull();
    });

    it('asks about signing in by default', () => {
      expect(buildSupportUrl(hosted)).toBe('https://decisionrecords.org/support?topic=signin');
    });

    it('passes the topic, the email address and the organisation domain, encoded', () => {
      expect(buildSupportUrl(hosted, { topic: 'email', email: 'ada+work@acme.test', org: 'acme.test' }))
        .toBe('https://decisionrecords.org/support?topic=email&email=ada%2Bwork%40acme.test&org=acme.test');
    });

    it('trims the values and lowercases the organisation domain', () => {
      const url = new URL(buildSupportUrl(hosted, { email: '  ada@acme.test ', org: ' ACME.Test ' })!);
      expect(url.searchParams.get('email')).toBe('ada@acme.test');
      expect(url.searchParams.get('org')).toBe('acme.test');
    });

    it('leaves out an email address or organisation that is missing or malformed', () => {
      for (const details of [
        { email: '', org: '' },
        { email: null, org: null },
        { email: 'ada', org: 'acme' },
        { email: 'ada@acme', org: 'acme test.com' },
        { email: 'ada @acme.test', org: 'acme.test/login?x=1' },
        { email: 'a'.repeat(250) + '@acme.test', org: '-acme.test' }
      ]) {
        expect(buildSupportUrl(hosted, details)).toBe('https://decisionrecords.org/support?topic=signin');
      }
    });

    it('passes only topic, email and org', () => {
      const url = new URL(buildSupportUrl(hosted, { topic: 'signin', email: 'ada@acme.test', org: 'acme.test' })!);
      const names: string[] = [];
      url.searchParams.forEach((_value, name) => names.push(name));
      expect(names).toEqual(['topic', 'email', 'org']);
    });

    it('keeps the path and query of a configured address', () => {
      expect(buildSupportUrl({ support_url: 'https://help.example.org/it?lang=en' }, { org: 'acme.test' }))
        .toBe('https://help.example.org/it?lang=en&topic=signin&org=acme.test');
    });
  });
});
