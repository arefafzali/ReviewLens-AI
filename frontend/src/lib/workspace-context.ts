const WORKSPACE_STORAGE_KEY = "reviewlens.workspace_id";
const LEGACY_PRODUCT_STORAGE_KEY = "reviewlens.product_id";

function activeProductStorageKey(workspaceId: string): string {
  return `reviewlens.active_product_id.${workspaceId}`;
}

function urlProductMapStorageKey(workspaceId: string): string {
  return `reviewlens.url_product_map.${workspaceId}`;
}

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

function getWorkspaceId(): string {
  const workspaceFromEnv = process.env.NEXT_PUBLIC_REVIEWLENS_WORKSPACE_ID;
  return workspaceFromEnv ?? getOrCreateId(WORKSPACE_STORAGE_KEY);
}

function getStoredUrlProductMap(workspaceId: string): Record<string, string> {
  if (typeof window === "undefined") {
    return {};
  }

  const raw = window.localStorage.getItem(urlProductMapStorageKey(workspaceId));
  if (!raw) {
    return {};
  }

  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return Object.fromEntries(
      Object.entries(parsed).filter(
        (entry): entry is [string, string] => typeof entry[0] === "string" && typeof entry[1] === "string" && Boolean(entry[1]),
      ),
    );
  } catch {
    return {};
  }
}

function setStoredUrlProductMap(workspaceId: string, map: Record<string, string>): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(urlProductMapStorageKey(workspaceId), JSON.stringify(map));
}

function normalizeSourceUrl(raw: string): string {
  const parsed = new URL(raw.trim());
  parsed.hash = "";

  ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid"].forEach((param) => {
    parsed.searchParams.delete(param);
  });

  if (parsed.pathname.length > 1 && parsed.pathname.endsWith("/")) {
    parsed.pathname = parsed.pathname.slice(0, -1);
  }

  return parsed.toString();
}

function deriveProductName(sourceUrl: string): string {
  try {
    const parsed = new URL(sourceUrl);
    const segments = parsed.pathname
      .split("/")
      .map((segment) => segment.trim())
      .filter(Boolean)
      .filter((segment) => segment.toLowerCase() !== "reviews" && segment.toLowerCase() !== "review");

    const candidate = segments.length > 0 ? segments[segments.length - 1] : parsed.hostname;
    return candidate
      .replace(/[-_]+/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 255) || "Analyst Product";
  } catch {
    return "Analyst Product";
  }
}

function deriveCsvProductName(fileName: string): string {
  const trimmed = fileName.trim();
  if (!trimmed) {
    return "CSV Product";
  }

  return trimmed
    .replace(/\.csv$/i, "")
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 255) || "CSV Product";
}

function fallbackHash(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return Math.abs(hash >>> 0).toString(16).padStart(8, "0");
}

async function hashText(value: string): Promise<string> {
  if (typeof crypto !== "undefined" && crypto.subtle && typeof TextEncoder !== "undefined") {
    try {
      const bytes = new TextEncoder().encode(value);
      const digest = await crypto.subtle.digest("SHA-256", bytes);
      return Array.from(new Uint8Array(digest))
        .map((byte) => byte.toString(16).padStart(2, "0"))
        .join("");
    } catch {
      return fallbackHash(value);
    }
  }
  return fallbackHash(value);
}

function getOrCreateProductContextForSourceKey(
  workspaceId: string,
  sourceKey: string,
  sourceUrl: string,
  productName: string,
): { workspaceId: string; productId: string; sourceUrl: string; productName: string } {
  const map = getStoredUrlProductMap(workspaceId);
  const existingProductId = map[sourceKey];
  const productId = existingProductId ?? createStableId();

  if (!existingProductId) {
    setStoredUrlProductMap(workspaceId, {
      ...map,
      [sourceKey]: productId,
    });
  }

  setActiveProductId(workspaceId, productId);

  return {
    workspaceId,
    productId,
    sourceUrl,
    productName,
  };
}

function getOrCreateActiveProductId(workspaceId: string): string {
  const productFromEnv = process.env.NEXT_PUBLIC_REVIEWLENS_PRODUCT_ID;
  if (productFromEnv) {
    return productFromEnv;
  }

  const activeKey = activeProductStorageKey(workspaceId);
  if (typeof window === "undefined") {
    return createStableId();
  }

  const activeProduct = window.localStorage.getItem(activeKey);
  if (activeProduct) {
    return activeProduct;
  }

  const legacyProduct = window.localStorage.getItem(LEGACY_PRODUCT_STORAGE_KEY);
  if (legacyProduct) {
    window.localStorage.setItem(activeKey, legacyProduct);
    return legacyProduct;
  }

  const created = createStableId();
  window.localStorage.setItem(activeKey, created);
  return created;
}

export function setActiveProductId(workspaceId: string, productId: string): void {
  if (typeof window === "undefined") {
    return;
  }

  if (process.env.NEXT_PUBLIC_REVIEWLENS_PRODUCT_ID) {
    return;
  }

  window.localStorage.setItem(activeProductStorageKey(workspaceId), productId);
}

export function getOrCreateProductContextForUrl(targetUrl: string): {
  workspaceId: string;
  productId: string;
  sourceUrl: string;
  productName: string;
} {
  const workspaceId = getWorkspaceId();
  const normalizedUrl = normalizeSourceUrl(targetUrl);
  return getOrCreateProductContextForSourceKey(
    workspaceId,
    normalizedUrl,
    normalizedUrl,
    deriveProductName(normalizedUrl),
  );
}

export async function getOrCreateProductContextForCsv(fileName: string, csvContent: string): Promise<{
  workspaceId: string;
  productId: string;
  sourceUrl: string;
  productName: string;
}> {
  const workspaceId = getWorkspaceId();
  const fingerprint = await hashText(`${fileName.trim()}\n${csvContent}`);
  const sourceKey = `csv:${fingerprint}`;
  const sourceUrl = `https://csv.upload.local/${fingerprint}`;

  return getOrCreateProductContextForSourceKey(
    workspaceId,
    sourceKey,
    sourceUrl,
    deriveCsvProductName(fileName),
  );
}

export function getWorkspaceContextIds(): { workspaceId: string; productId: string } {
  const workspaceId = getWorkspaceId();

  return {
    workspaceId,
    productId: getOrCreateActiveProductId(workspaceId),
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
