import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';
import { of } from 'rxjs';

import { HasUnsavedChanges, unsavedChangesGuard } from './unsaved-changes.guard';

describe('unsavedChangesGuard', () => {
  const route = {} as ActivatedRouteSnapshot;
  const state = {} as RouterStateSnapshot;

  function run(component: HasUnsavedChanges | null) {
    return TestBed.runInInjectionContext(() =>
      unsavedChangesGuard(component as HasUnsavedChanges, route, state, state)
    );
  }

  it('returns the answer of the component', () => {
    expect(run({ confirmDiscardChanges: () => true })).toBeTrue();
    expect(run({ confirmDiscardChanges: () => false })).toBeFalse();

    const pending = of(false);
    expect(run({ confirmDiscardChanges: () => pending })).toBe(pending);
  });

  it('lets navigation through when there is no component to ask', () => {
    expect(run(null)).toBeTrue();
    expect(run({} as HasUnsavedChanges)).toBeTrue();
  });
});
