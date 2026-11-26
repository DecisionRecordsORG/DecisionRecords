import { TestBed } from '@angular/core/testing';
import posthog from 'posthog-js';
import { ANALYTICS_OPTIONS, ANALYTICS_PROJECT_KEY, PostHogService, sanitizeAnalyticsEvent } from './posthog.service';

/**
 * What the browser may send to the analytics service. A click on a row of
 * the decision list must not send the decision's title, and an address must
 * not carry an email address or a one-time link.
 */
describe('browser analytics', () => {
  describe('options', () => {
    it('masks the text and the attributes of clicked elements', () => {
      expect(ANALYTICS_OPTIONS.mask_all_text).toBeTrue();
      expect(ANALYTICS_OPTIONS.mask_all_element_attributes).toBeTrue();
    });

    it('does not record sessions, and would mask inputs and text if it did', () => {
      expect(ANALYTICS_OPTIONS.disable_session_recording).toBeTrue();
      expect(ANALYTICS_OPTIONS.session_recording.maskAllInputs).toBeTrue();
      expect(ANALYTICS_OPTIONS.session_recording.maskTextSelector).toBe('*');
    });

    it('respects Do Not Track and sends through our own address', () => {
      expect(ANALYTICS_OPTIONS.respect_dnt).toBeTrue();
      expect(ANALYTICS_OPTIONS.api_host).toBe('https://e.decisionrecords.org');
    });
  });

  describe('sanitizeAnalyticsEvent', () => {
    interface Loose {
      event?: string;
      properties?: Record<string, unknown>;
      $set?: Record<string, unknown>;
      $set_once?: Record<string, unknown>;
    }
    const clean = (event: Loose): Loose => sanitizeAnalyticsEvent(event);

    it('removes the text of the clicked element and the page title', () => {
      const event = clean({
        event: '$autocapture',
        properties: {
          $el_text: 'Acquire Northwind Traders',
          title: 'Acquire Northwind Traders - Decision Records',
          $event_type: 'click'
        }
      });

      expect(event.properties).toEqual({ $event_type: 'click' });
    });

    it('keeps only the kind of each element in the click path', () => {
      const event = clean({
        event: '$autocapture',
        properties: {
          $elements: [
            { tag_name: 'a', $el_text: 'Acquire Northwind Traders', attr__href: '/acme.test/decision/42',
              attr__title: 'Owner: Zebedee Quince', nth_child: 2, nth_of_type: 1 },
            { tag_name: 'li', attr__class: 'decision-row', text: 'Zebedee Quince' }
          ]
        }
      });

      expect(event.properties!['$elements']).toEqual([
        { tag_name: 'a', nth_child: 2, nth_of_type: 1 },
        { tag_name: 'li' }
      ]);
      expect(JSON.stringify(event)).not.toContain('Northwind');
      expect(JSON.stringify(event)).not.toContain('Zebedee');
    });

    it('cuts the query string and the fragment off every address', () => {
      const event = clean({
        event: '$pageview',
        properties: {
          $current_url: 'https://app.decisionrecords.org/acme.test/login?email=zebedee@acme.test',
          $referrer: 'https://app.decisionrecords.org/acme.test/setup?token=one-time-link#top',
          $initial_current_url: 'https://app.decisionrecords.org/#access_token=abc',
          $pathname: '/acme.test/login',
          $host: 'app.decisionrecords.org'
        },
        $set: { $current_url: 'https://app.decisionrecords.org/x?email=zebedee@acme.test' },
        $set_once: { $initial_referrer: 'https://example.org/?q=zebedee' }
      });

      expect(event.properties).toEqual({
        $current_url: 'https://app.decisionrecords.org/acme.test/login',
        $referrer: 'https://app.decisionrecords.org/acme.test/setup',
        $initial_current_url: 'https://app.decisionrecords.org/',
        $pathname: '/acme.test/login',
        $host: 'app.decisionrecords.org'
      });
      expect(event.$set).toEqual({ $current_url: 'https://app.decisionrecords.org/x' });
      expect(event.$set_once).toEqual({ $initial_referrer: 'https://example.org/' });
      expect(JSON.stringify(event)).not.toContain('zebedee');
      expect(JSON.stringify(event)).not.toContain('one-time-link');
    });

    it('leaves other properties alone and survives an empty event', () => {
      expect(clean({ event: 'x', properties: { $browser: 'Firefox', count: 3 } }).properties)
        .toEqual({ $browser: 'Firefox', count: 3 });
      expect(clean({ event: 'x' })).toEqual({ event: 'x' });
      expect(sanitizeAnalyticsEvent(null)).toBeNull();
    });
  });

  describe('PostHogService', () => {
    let service: PostHogService;
    let init: jasmine.Spy;
    let optOut: jasmine.Spy;
    let optIn: jasmine.Spy;
    let reset: jasmine.Spy;
    let hasOptedOut: jasmine.Spy;

    beforeEach(() => {
      init = spyOn(posthog, 'init');
      optOut = spyOn(posthog, 'opt_out_capturing');
      optIn = spyOn(posthog, 'opt_in_capturing');
      reset = spyOn(posthog, 'reset');
      hasOptedOut = spyOn(posthog, 'has_opted_out_capturing').and.returnValue(false);
      TestBed.configureTestingModule({});
      service = TestBed.inject(PostHogService);
    });

    it('starts the library once, with masking and the last check on every event', () => {
      service.enable();
      service.enable();

      expect(init).toHaveBeenCalledTimes(1);
      const options = init.calls.mostRecent().args[1];
      expect(options.mask_all_text).toBeTrue();
      expect(options.mask_all_element_attributes).toBeTrue();
      const checked = options.before_send({ event: '$autocapture', properties: { $el_text: 'A title' } });
      expect(checked.properties).toEqual({});
    });

    it('does not start the library just to stop it', () => {
      service.disable();

      expect(init).not.toHaveBeenCalled();
      expect(optOut).not.toHaveBeenCalled();
      expect(service.started).toBeFalse();
    });

    it('removes the identifier an earlier visit left in this browser, and nothing else', () => {
      const libraryKey = `ph_${ANALYTICS_PROJECT_KEY}_posthog`;
      localStorage.setItem(libraryKey, '{"distinct_id":"0193-earlier-visit"}');
      localStorage.setItem('dr_something_else', 'kept');

      service.disable();

      expect(localStorage.getItem(libraryKey)).toBeNull();
      expect(localStorage.getItem('dr_something_else')).toBe('kept');
      localStorage.removeItem('dr_something_else');
    });

    it('stops sending and forgets the browser identifier when disabled', () => {
      service.enable();

      service.disable();

      expect(optOut).toHaveBeenCalledTimes(1);
      expect(reset).toHaveBeenCalledTimes(1);
    });

    it('opts out after the reset, because the library\'s reset forgets an opt-out', () => {
      const order: string[] = [];
      reset.and.callFake(() => { order.push('reset'); });
      optOut.and.callFake(() => { order.push('opt-out'); });
      service.enable();

      service.disable();

      expect(order).toEqual(['reset', 'opt-out']);
    });

    it('drops every event at the last check once disabled, whatever the library thinks', () => {
      service.enable();
      const lastCheck = init.calls.mostRecent().args[1].before_send;
      expect(lastCheck({ event: '$pageview', properties: {} })).not.toBeNull();

      service.disable();

      expect(lastCheck({ event: '$pageleave', properties: {} })).toBeNull();
      expect(lastCheck({ event: '$autocapture', properties: { $el_text: 'A title' } })).toBeNull();

      service.enable();
      expect(lastCheck({ event: '$pageview', properties: {} })).not.toBeNull();
    });

    it('throws away events that were still waiting to be sent', () => {
      service.enable();
      const library = posthog as unknown as { _requestQueue?: { _queue: unknown[] } };
      const before = library._requestQueue;
      library._requestQueue = { _queue: [{ url: '/e/', data: { event: '$autocapture' } }] };

      service.disable();

      expect(library._requestQueue._queue).toEqual([]);
      library._requestQueue = before;
    });

    it('resumes after a stop, without announcing it as an event', () => {
      service.enable();
      service.disable();
      hasOptedOut.and.returnValue(true);

      service.enable();

      expect(optIn).toHaveBeenCalledOnceWith({ captureEventName: false });
    });

    it('sends nothing through capture() before it was started', () => {
      const capture = spyOn(posthog, 'capture');

      service.capture('something');

      expect(capture).not.toHaveBeenCalled();
    });
  });
});
