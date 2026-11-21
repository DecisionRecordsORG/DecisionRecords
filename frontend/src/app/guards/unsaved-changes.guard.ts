import { CanDeactivateFn } from '@angular/router';
import { Observable } from 'rxjs';

/** Implemented by routed components that can hold input the user has not saved yet. */
export interface HasUnsavedChanges {
  /**
   * Resolve to true when it is safe to leave: either nothing would be lost,
   * or the user has confirmed that their changes can be discarded.
   */
  confirmDiscardChanges(): Observable<boolean> | boolean;
}

/** Asks the component before the router navigates away from it. */
export const unsavedChangesGuard: CanDeactivateFn<HasUnsavedChanges> = (component) => {
  return component?.confirmDiscardChanges ? component.confirmDiscardChanges() : true;
};
