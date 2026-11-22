import { SITE_URL } from './seo.service';

/**
 * Link to the public support page, for people who cannot sign in.
 *
 * The page lives on the website, outside this app, and needs no sign-in. It
 * accepts three query parameters: `topic`, `email` and `org` (the
 * organisation's email domain). Nothing else is ever passed.
 */

export type SupportTopic = 'signin' | 'email' | 'bug' | 'account' | 'other';

/** The support page of the hosted service. */
export const HOSTED_SUPPORT_URL = `${SITE_URL}/support`;

export interface SupportLinkSettings {
  /** True on the hosted service, which has the website next to the app. */
  marketing_pages?: boolean;
  /** Address of a support page chosen by whoever runs the installation. */
  support_url?: unknown;
}

export interface SupportLinkDetails {
  topic?: SupportTopic;
  email?: string | null;
  org?: string | null;
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const DOMAIN_PATTERN = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$/;

/**
 * Where the support page is, or null when the link must not be shown.
 *
 * - A `support_url` in the settings wins when it is an http(s) address.
 * - A `support_url` that is anything else (for example "none") hides the link.
 * - With no `support_url`, the hosted service uses its own support page and a
 *   self-hosted installation shows no link: its users should not be sent to
 *   the hosted service's support.
 */
export function supportPageAddress(settings: SupportLinkSettings | null | undefined): string | null {
  const configured = typeof settings?.support_url === 'string' ? settings.support_url.trim() : '';
  if (configured) {
    return /^https?:\/\/\S+$/i.test(configured) ? configured : null;
  }
  return settings?.marketing_pages ? HOSTED_SUPPORT_URL : null;
}

/**
 * The support page address with the topic and, when they are known and well
 * formed, the email address and organisation domain. Returns null when there
 * is no support page to link to.
 */
export function buildSupportUrl(
  settings: SupportLinkSettings | null | undefined,
  details: SupportLinkDetails = {}
): string | null {
  const address = supportPageAddress(settings);
  if (!address) {
    return null;
  }

  let url: URL;
  try {
    url = new URL(address);
  } catch {
    return null;
  }

  url.searchParams.set('topic', details.topic || 'signin');

  const email = (details.email || '').trim();
  if (email.length <= 254 && EMAIL_PATTERN.test(email)) {
    url.searchParams.set('email', email);
  }

  const org = (details.org || '').trim().toLowerCase();
  if (org.length <= 253 && DOMAIN_PATTERN.test(org)) {
    url.searchParams.set('org', org);
  }

  return url.toString();
}
