function bufferToBase64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let str = ''
  for (const b of bytes) str += String.fromCharCode(b)
  return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function base64urlToBuffer(base64url: string): ArrayBuffer {
  const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/')
  const pad = base64.length % 4 === 0 ? '' : '='.repeat(4 - (base64.length % 4))
  const binary = atob(base64 + pad)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes.buffer
}

export function supportsWebAuthn(): boolean {
  return typeof window !== 'undefined' && !!window.PublicKeyCredential
}

export type EncodedCredentialDescriptor = {
  type: PublicKeyCredentialType
  id: string
  transports?: AuthenticatorTransport[]
}

export type EncodedRegistrationOptions = {
  rp: PublicKeyCredentialRpEntity
  user: {
    id: string
    name: string
    displayName: string
  }
  challenge: string
  pubKeyCredParams: PublicKeyCredentialParameters[]
  timeout?: number
  attestation?: AttestationConveyancePreference
  authenticatorSelection?: AuthenticatorSelectionCriteria
  excludeCredentials?: EncodedCredentialDescriptor[]
}

export type EncodedAuthenticationOptions = {
  challenge: string
  rpId?: string
  timeout?: number
  userVerification?: UserVerificationRequirement
  allowCredentials?: EncodedCredentialDescriptor[]
}

const DEFAULT_MESSAGES: Record<string, string> = {
  AbortError: 'Fingerprint request was cancelled.',
  InvalidStateError: 'This device already has a saved fingerprint login for Lite.',
  NotAllowedError: 'Fingerprint prompt was dismissed or timed out.',
  NotSupportedError: 'This device does not support fingerprint login.',
  SecurityError: 'Browser blocked the fingerprint prompt. Please try again from the button.',
}

export function getWebAuthnErrorInfo(error: unknown, fallback: string): { code: string; message: string } {
  if (error instanceof DOMException) {
    return {
      code: error.name,
      message: DEFAULT_MESSAGES[error.name] ?? error.message ?? fallback,
    }
  }
  if (error instanceof Error) {
    return {
      code: error.name || 'Error',
      message: error.message || fallback,
    }
  }
  return {
    code: 'UnknownError',
    message: fallback,
  }
}

export function isWebAuthnDismissed(error: unknown): boolean {
  const { code, message } = getWebAuthnErrorInfo(error, '')
  const normalized = message.toLowerCase()
  return (
    code === 'AbortError' ||
    (code === 'NotAllowedError' && (
      normalized.includes('cancel') ||
      normalized.includes('dismiss') ||
      normalized.includes('timed out') ||
      normalized.includes('timeout')
    ))
  )
}

export async function createPasskey(options: EncodedRegistrationOptions): Promise<Record<string, unknown>> {
  const publicKey: PublicKeyCredentialCreationOptions = {
    rp: options.rp,
    user: {
      id: base64urlToBuffer(options.user.id),
      name: options.user.name,
      displayName: options.user.displayName,
    },
    challenge: base64urlToBuffer(options.challenge),
    pubKeyCredParams: options.pubKeyCredParams,
    timeout: options.timeout ?? 60000,
    attestation: options.attestation ?? 'none',
    authenticatorSelection: options.authenticatorSelection,
    excludeCredentials: (options.excludeCredentials ?? []).map((c) => ({
      type: c.type,
      id: base64urlToBuffer(c.id),
      transports: c.transports,
    })),
  }

  const credential = await navigator.credentials.create({ publicKey }) as PublicKeyCredential
  const response = credential.response as AuthenticatorAttestationResponse

  return {
    id: credential.id,
    rawId: bufferToBase64url(credential.rawId),
    type: credential.type,
    response: {
      attestationObject: bufferToBase64url(response.attestationObject),
      clientDataJSON: bufferToBase64url(response.clientDataJSON),
      transports: response.getTransports?.() ?? [],
    },
  }
}

export async function getPasskey(options: EncodedAuthenticationOptions): Promise<Record<string, unknown>> {
  const publicKey: PublicKeyCredentialRequestOptions = {
    challenge: base64urlToBuffer(options.challenge),
    rpId: options.rpId,
    timeout: options.timeout ?? 60000,
    userVerification: options.userVerification ?? 'preferred',
    allowCredentials: (options.allowCredentials ?? []).map((c) => ({
      type: c.type,
      id: base64urlToBuffer(c.id),
      transports: c.transports,
    })),
  }

  const credential = await navigator.credentials.get({ publicKey }) as PublicKeyCredential
  const response = credential.response as AuthenticatorAssertionResponse

  return {
    id: credential.id,
    rawId: bufferToBase64url(credential.rawId),
    type: credential.type,
    response: {
      authenticatorData: bufferToBase64url(response.authenticatorData),
      clientDataJSON: bufferToBase64url(response.clientDataJSON),
      signature: bufferToBase64url(response.signature),
      userHandle: response.userHandle ? bufferToBase64url(response.userHandle) : null,
    },
  }
}
