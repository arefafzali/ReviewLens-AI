const WORKSPACE_STORAGE_KEY = "reviewlens.workspace_id";
const PRODUCT_STORAGE_KEY = "reviewlens.product_id";

function chatSessionStorageKey(workspaceId: string, productId: string): string {
  return `reviewlens.chat_session_id.${workspaceId}.${productId}`;
}

function stableUuidFallback(): string {
  const randomHex = Math.random().toString(16).slice(2).padEnd(12, "0").slice(0, 12);
  return `00000000-0000-4000-8000-${randomHex}`;
}

function createStableId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return stableUuidFallback();
}

function getOrCreateId(storageKey: string): string {
  if (typeof window === "undefined") {
    return createStableId();
  }

  const existing = window.localStorage.getItem(storageKey);
  if (existing) {
    return existing;
  }

  const created = createStableId();
  window.localStorage.setItem(storageKey, created);
  return created;
}

export function getWorkspaceContextIds(): { workspaceId: string; productId: string } {
  const workspaceFromEnv = process.env.NEXT_PUBLIC_REVIEWLENS_WORKSPACE_ID;
  const productFromEnv = process.env.NEXT_PUBLIC_REVIEWLENS_PRODUCT_ID;

  return {
    workspaceId: workspaceFromEnv ?? getOrCreateId(WORKSPACE_STORAGE_KEY),
    productId: productFromEnv ?? getOrCreateId(PRODUCT_STORAGE_KEY),
  };
}

export function getStoredChatSessionId(workspaceId: string, productId: string): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(chatSessionStorageKey(workspaceId, productId));
}

export function setStoredChatSessionId(workspaceId: string, productId: string, chatSessionId: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(chatSessionStorageKey(workspaceId, productId), chatSessionId);
}
