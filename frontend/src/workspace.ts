import type { ApiClient } from './api';
import type { Actor, WorkspaceData } from './types';

export interface WorkspaceProps {
  api: ApiClient; actor: Actor; data: WorkspaceData;
  refresh: () => Promise<void>;
  onError: (error: unknown) => void;
  onMessage: (message: string) => void;
}
