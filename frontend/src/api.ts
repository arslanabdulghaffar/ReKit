/** A fixed same-origin transport. Credentials never enter URLs or browser storage. */
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); this.name = 'ApiError'; }
}

export class ApiClient {
  constructor(private token: string, private onUnauthorized: () => void = () => {}) {}

  private async request(path: string, method: string, body?: unknown, image = false): Promise<Response> {
    // Reject absolute, protocol-relative, encoded escape, fragment, and backslash paths.
    if (!/^\/[a-zA-Z0-9_/?=&.%:-]*$/.test(path) || path.startsWith('//') || /\\|%2f|%5c|%2e|\.\./i.test(path)) {
      throw new Error('Invalid API path');
    }
    const headers: Record<string, string> = { Authorization: `Bearer ${this.token}` };
    let payload: BodyInit | undefined;
    if (body instanceof Blob) { headers['Content-Type'] = body.type; payload = body; }
    else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
    let response: Response;
    try {
      response = await fetch(`/api${path}`, { method, headers, body: payload, cache: 'no-store', credentials: 'omit', redirect: 'error' });
    } catch { throw new ApiError(0, 'The server could not be reached. Check the local backend and retry.'); }
    if (response.status === 401) { this.clear(); this.onUnauthorized(); }
    if (!response.ok) {
      let detail = 'The server could not complete this request.';
      try {
        const result = await response.json() as { detail?: unknown };
        if (typeof result.detail === 'string') detail = result.detail;
        else if (Array.isArray(result.detail)) detail = result.detail.map((item: { loc?: unknown[]; msg?: string }) => `${item.loc?.join('.') ?? 'Input'}: ${item.msg ?? 'Invalid value'}`).join('; ');
      } catch { /* Never display an untrusted HTML error response. */ }
      if (response.status === 409) detail = `State conflict: ${detail} Refresh the current record before retrying.`;
      throw new ApiError(response.status, detail);
    }
    if (image && !['image/jpeg', 'image/png', 'image/webp'].includes(response.headers.get('content-type')?.split(';')[0] ?? '')) {
      throw new ApiError(422, 'The server returned an unsupported image response.');
    }
    return response;
  }

  async get<T>(path: string): Promise<T> { return (await this.request(path, 'GET')).json() as Promise<T>; }
  async post<T>(path: string, body: unknown): Promise<T> { return (await this.request(path, 'POST', body)).json() as Promise<T>; }
  async image(path: string): Promise<Blob> { return (await this.request(path, 'GET', undefined, true)).blob(); }
  clear(): void { this.token = ''; }
}

export const idPath = (value: string): string => encodeURIComponent(value).replace(/[!'()*]/g, char => `%${char.charCodeAt(0).toString(16).toUpperCase()}`);
export const newId = (prefix: string): string => `${prefix}-${crypto.randomUUID()}`;
