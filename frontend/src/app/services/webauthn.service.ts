import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, from, switchMap, tap } from 'rxjs';
import {
  User,
  AuthConfig,
  WebAuthnCredential,
  WebAuthnRegistrationOptions,
  WebAuthnAuthenticationOptions
} from '../models/decision.model';
import { AuthService } from './auth.service';

@Injectable({
  providedIn: 'root'
})
export class WebAuthnService {
  private apiUrl = '/api';

  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) {}

  /**
   * Check if WebAuthn is supported in the browser
   * Uses multiple detection methods for robustness
   * See: https://github.com/MasterKale/SimpleWebAuthn
   * See: https://passkeys.dev/docs/tools-libraries/libraries/
   */
  isWebAuthnSupported(): boolean {
    // First check if we're in a browser environment
    if (typeof window === 'undefined') {
      console.log('[WebAuthn] Not in browser environment (SSR)');
      return false;
    }

    // Check for secure context (required for WebAuthn)
    // WebAuthn only works on HTTPS or localhost
    const isSecureContext = window.isSecureContext ??
      (window.location.protocol === 'https:' ||
       window.location.hostname === 'localhost' ||
       window.location.hostname === '127.0.0.1');

    // Check for PublicKeyCredential - try multiple approaches
    // Some environments may expose it differently
    const hasPublicKeyCredential =
      (typeof window.PublicKeyCredential !== 'undefined') ||
      (typeof PublicKeyCredential !== 'undefined');

    const isFunction =
      (typeof window.PublicKeyCredential === 'function') ||
      (typeof PublicKeyCredential === 'function');

    const supported = isSecureContext && hasPublicKeyCredential && isFunction;

    console.log('[WebAuthn] Checking support:', {
      isSecureContext,
      protocol: window.location?.protocol,
      hostname: window.location?.hostname,
      hasPublicKeyCredential,
      isFunction,
      windowPublicKeyCredential: typeof window.PublicKeyCredential,
      globalPublicKeyCredential: typeof PublicKeyCredential,
      supported
    });

    return supported;
  }

  /**
   * Check if platform authenticator (Face ID, Touch ID, Windows Hello) is available
   * This determines if we can offer passkey registration
   * See: https://passkeys.dev/docs/use-cases/bootstrapping/
   *
   * Note: Even if this returns false, users might still be able to use security keys
   * or cross-platform authenticators. We use this primarily for UI recommendations.
   */
  async isPlatformAuthenticatorAvailable(): Promise<boolean> {
    if (!this.isWebAuthnSupported()) {
      console.log('[WebAuthn] WebAuthn not supported in this browser');
      return false;
    }
    try {
      // Use window.PublicKeyCredential for consistency
      const pkc = window.PublicKeyCredential || PublicKeyCredential;
      if (typeof pkc.isUserVerifyingPlatformAuthenticatorAvailable === 'function') {
        const available = await pkc.isUserVerifyingPlatformAuthenticatorAvailable();
        console.log('[WebAuthn] Platform authenticator available:', available);
        return available;
      }
      console.log('[WebAuthn] isUserVerifyingPlatformAuthenticatorAvailable not available');
      return false;
    } catch (error) {
      console.error('[WebAuthn] Error checking platform authenticator:', error);
      return false;
    }
  }

  /**
   * Check if any authenticator method is available (platform or cross-platform)
   * This is more permissive - returns true if WebAuthn is supported at all
   */
  canAttemptPasskeyRegistration(): boolean {
    const supported = this.isWebAuthnSupported();
    console.log('[WebAuthn] Can attempt passkey registration:', supported);
    return supported;
  }

  /**
   * Check if conditional UI (autofill) is supported
   * See: https://passkeys.dev/docs/use-cases/bootstrapping/
   */
  async isConditionalMediationAvailable(): Promise<boolean> {
    if (!this.isWebAuthnSupported()) {
      return false;
    }
    try {
      const pkc = window.PublicKeyCredential || PublicKeyCredential;
      // @ts-ignore - This is a newer API that TypeScript may not have types for
      if (pkc.isConditionalMediationAvailable) {
        // @ts-ignore
        return await pkc.isConditionalMediationAvailable();
      }
      return false;
    } catch {
      return false;
    }
  }

  /**
   * Get authentication config for a domain
   */
  getAuthConfig(domain: string): Observable<AuthConfig> {
    return this.http.get<AuthConfig>(`${this.apiUrl}/auth/auth-config/${domain}`);
  }

  /**
   * Register a new user with WebAuthn (or add a new credential for existing user)
   */
  register(email: string, name?: string): Observable<{ message: string; user: User }> {
    // Step 1: Get registration options from server
    return this.http.post<WebAuthnRegistrationOptions>(
      `${this.apiUrl}/webauthn/register/options`,
      { email, name }
    ).pipe(
      // Step 2: Create credential using browser WebAuthn API
      switchMap(options => from(this.createCredential(options))),
      // Step 3: Send credential to server for verification
      switchMap(credential => this.verifyRegistration(credential)),
      // Step 4: Reload current user
      tap(() => this.authService.loadCurrentUser())
    );
  }

  /**
   * Authenticate user with WebAuthn
   */
  authenticate(email?: string): Observable<{ message: string; user: User }> {
    // Step 1: Get authentication options from server
    return this.http.post<WebAuthnAuthenticationOptions>(
      `${this.apiUrl}/webauthn/authenticate/options`,
      email ? { email } : {}
    ).pipe(
      // Step 2: Get credential using browser WebAuthn API
      switchMap(options => from(this.getCredential(options))),
      // Step 3: Send credential to server for verification
      switchMap(credential => this.verifyAuthentication(credential)),
      // Step 4: Reload current user
      tap(() => this.authService.loadCurrentUser())
    );
  }

  /**
   * Add a new passkey for the current user
   */
  addCredential(): Observable<WebAuthnRegistrationOptions> {
    return this.http.post<WebAuthnRegistrationOptions>(
      `${this.apiUrl}/user/credentials`,
      {}
    );
  }

  /**
   * Get all credentials for current user
   */
  getCredentials(): Observable<WebAuthnCredential[]> {
    return this.http.get<WebAuthnCredential[]>(`${this.apiUrl}/user/credentials`);
  }

  /**
   * Delete a credential
   */
  deleteCredential(credentialId: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(
      `${this.apiUrl}/user/credentials/${credentialId}`
    );
  }

  /**
   * Create a new WebAuthn credential (browser API)
   */
  private async createCredential(options: WebAuthnRegistrationOptions): Promise<any> {
    const publicKeyCredentialCreationOptions: PublicKeyCredentialCreationOptions = {
      rp: {
        name: options.rp.name,
        id: options.rp.id,
      },
      user: {
        id: this.base64UrlToArrayBuffer(options.user.id),
        name: options.user.name,
        displayName: options.user.displayName,
      },
      challenge: this.base64UrlToArrayBuffer(options.challenge),
      pubKeyCredParams: options.pubKeyCredParams.map(param => ({
        type: param.type as PublicKeyCredentialType,
        alg: param.alg,
      })),
      timeout: options.timeout || 60000,
      excludeCredentials: options.excludeCredentials?.map(cred => ({
        type: cred.type as PublicKeyCredentialType,
        id: this.base64UrlToArrayBuffer(cred.id),
        transports: cred.transports as AuthenticatorTransport[],
      })),
      authenticatorSelection: options.authenticatorSelection ? {
        residentKey: options.authenticatorSelection.residentKey as ResidentKeyRequirement,
        userVerification: options.authenticatorSelection.userVerification as UserVerificationRequirement,
        authenticatorAttachment: options.authenticatorSelection.authenticatorAttachment as AuthenticatorAttachment,
      } : undefined,
      attestation: (options.attestation || 'none') as AttestationConveyancePreference,
    };

    const credential = await navigator.credentials.create({
      publicKey: publicKeyCredentialCreationOptions,
    }) as PublicKeyCredential;

    return this.credentialToJSON(credential);
  }

  /**
   * Get a WebAuthn credential for authentication (browser API)
   */
  private async getCredential(options: WebAuthnAuthenticationOptions): Promise<any> {
    const publicKeyCredentialRequestOptions: PublicKeyCredentialRequestOptions = {
      challenge: this.base64UrlToArrayBuffer(options.challenge),
      timeout: options.timeout || 60000,
      rpId: options.rpId,
      allowCredentials: options.allowCredentials?.map(cred => ({
        type: cred.type as PublicKeyCredentialType,
        id: this.base64UrlToArrayBuffer(cred.id),
        transports: cred.transports as AuthenticatorTransport[],
      })),
      userVerification: (options.userVerification || 'preferred') as UserVerificationRequirement,
    };

    const credential = await navigator.credentials.get({
      publicKey: publicKeyCredentialRequestOptions,
    }) as PublicKeyCredential;

    return this.credentialToJSON(credential);
  }

  /**
   * Verify registration with the server
   */
  private verifyRegistration(credential: any): Observable<{ message: string; user: User }> {
    return this.http.post<{ message: string; user: User }>(
      `${this.apiUrl}/webauthn/register/verify`,
      { credential }
    );
  }

  /**
   * Verify authentication with the server
   */
  private verifyAuthentication(credential: any): Observable<{ message: string; user: User }> {
    return this.http.post<{ message: string; user: User }>(
      `${this.apiUrl}/webauthn/authenticate/verify`,
      { credential }
    );
  }

  /**
   * Convert a PublicKeyCredential to a JSON-serializable object
   */
  private credentialToJSON(credential: PublicKeyCredential): any {
    const response = credential.response as AuthenticatorAttestationResponse | AuthenticatorAssertionResponse;

    const result: any = {
      id: credential.id,
      rawId: this.arrayBufferToBase64Url(credential.rawId),
      type: credential.type,
      response: {
        clientDataJSON: this.arrayBufferToBase64Url(response.clientDataJSON),
      },
    };

    if ('attestationObject' in response) {
      // Registration response
      result.response.attestationObject = this.arrayBufferToBase64Url(response.attestationObject);
      if (response.getTransports) {
        result.response.transports = response.getTransports();
      }
    }

    if ('authenticatorData' in response) {
      // Authentication response
      result.response.authenticatorData = this.arrayBufferToBase64Url(response.authenticatorData);
      result.response.signature = this.arrayBufferToBase64Url(response.signature);
      if (response.userHandle) {
        result.response.userHandle = this.arrayBufferToBase64Url(response.userHandle);
      }
    }

    return result;
  }

  /**
   * Convert a base64url string to an ArrayBuffer
   */
  private base64UrlToArrayBuffer(base64url: string): ArrayBuffer {
    // Add padding if needed
    let base64 = base64url.replace(/-/g, '+').replace(/_/g, '/');
    const padding = base64.length % 4;
    if (padding) {
      base64 += '='.repeat(4 - padding);
    }

    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
  }

  /**
   * Convert an ArrayBuffer to a base64url string
   */
  private arrayBufferToBase64Url(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
  }
}
