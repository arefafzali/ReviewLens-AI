import type {
  ChatStreamCitationsEvent,
  ChatStreamDoneEvent,
  ChatStreamErrorEvent,
  ChatStreamMetaEvent,
  ChatStreamRequestPayload,
  ChatStreamTokenEvent,
} from "@/types/api";

export type ParsedSseEvent = {
  event: string;
  data: unknown;
};

export class ChatStreamParseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ChatStreamParseError";
  }
}

export class ChatStreamTransportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ChatStreamTransportError";
  }
}

type ParserListener = (event: ParsedSseEvent) => void;

export function createSseEventParser(onEvent: ParserListener) {
  let buffer = "";

  function parseBlock(block: string): void {
    const lines = block.split(/\r?\n/);
    let eventName = "message";
    const dataLines: string[] = [];

    for (const rawLine of lines) {
      const line = rawLine.trimEnd();
      if (!line || line.startsWith(":")) {
        continue;
      }

      if (line.startsWith("event:")) {
        eventName = line.slice("event:".length).trim();
        continue;
      }

      if (line.startsWith("data:")) {
        dataLines.push(line.slice("data:".length).trimStart());
      }
    }

    if (dataLines.length === 0) {
      return;
    }

    const dataText = dataLines.join("\n");
    let parsed: unknown;
    try {
      parsed = JSON.parse(dataText);
    } catch {
      throw new ChatStreamParseError(`Unable to parse SSE event payload for event '${eventName}'.`);
    }

    onEvent({ event: eventName, data: parsed });
  }

  function processBuffer(includePartial: boolean): void {
    while (true) {
      const match = buffer.match(/\r?\n\r?\n/);
      if (!match || match.index === undefined) {
        break;
      }

      const separatorIndex = match.index;
      const separatorLength = match[0].length;
      const block = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + separatorLength);
      parseBlock(block);
    }

    if (includePartial) {
      const remaining = buffer.trim();
      if (remaining) {
        parseBlock(remaining);
      }
      buffer = "";
    }
  }

  return {
    push(chunk: string): void {
      buffer += chunk;
      processBuffer(false);
    },
    flush(): void {
      processBuffer(true);
    },
  };
}

type StreamCallbacks = {
  onMeta?: (payload: ChatStreamMetaEvent) => void;
  onCitations?: (payload: ChatStreamCitationsEvent) => void;
  onToken?: (payload: ChatStreamTokenEvent) => void;
  onDone?: (payload: ChatStreamDoneEvent) => void;
  onError?: (payload: ChatStreamErrorEvent) => void;
};

export type StreamChatCompletionArgs = StreamCallbacks & {
  payload: ChatStreamRequestPayload;
  baseUrl?: string;
  signal?: AbortSignal;
};

function defaultApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

function normalizeErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Chat streaming failed.";
}

export async function streamChatCompletion({
  payload,
  baseUrl = defaultApiBaseUrl(),
  signal,
  onMeta,
  onCitations,
  onToken,
  onDone,
  onError,
}: StreamChatCompletionArgs): Promise<ChatStreamDoneEvent> {
  const response = await fetch(`${baseUrl}/chat/stream`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    throw new ChatStreamTransportError(`Chat stream request failed with status ${response.status}.`);
  }

  if (!response.body) {
    throw new ChatStreamTransportError("Chat stream response body is not available.");
  }

  const decoder = new TextDecoder("utf-8");
  const reader = response.body.getReader();
  let doneEvent: ChatStreamDoneEvent | null = null;

  const parser = createSseEventParser((parsedEvent) => {
    if (parsedEvent.event === "meta") {
      onMeta?.(parsedEvent.data as ChatStreamMetaEvent);
      return;
    }

    if (parsedEvent.event === "citations") {
      onCitations?.(parsedEvent.data as ChatStreamCitationsEvent);
      return;
    }

    if (parsedEvent.event === "token") {
      onToken?.(parsedEvent.data as ChatStreamTokenEvent);
      return;
    }

    if (parsedEvent.event === "done") {
      doneEvent = parsedEvent.data as ChatStreamDoneEvent;
      onDone?.(doneEvent);
      return;
    }

    if (parsedEvent.event === "error") {
      const payload = parsedEvent.data as ChatStreamErrorEvent;
      onError?.(payload);
      throw new ChatStreamTransportError(payload.message || "Chat stream returned an error event.");
    }
  });

  try {
    while (true) {
      const next = await reader.read();
      if (next.done) {
        parser.push(decoder.decode());
        parser.flush();
        break;
      }

      parser.push(decoder.decode(next.value, { stream: true }));
    }
  } catch (error) {
    if (signal?.aborted) {
      throw new DOMException("Chat stream aborted.", "AbortError");
    }

    if (error instanceof ChatStreamTransportError || error instanceof ChatStreamParseError) {
      throw error;
    }

    throw new ChatStreamTransportError(normalizeErrorMessage(error));
  }

  if (!doneEvent) {
    throw new ChatStreamTransportError("Chat stream ended before a done event was received.");
  }

  return doneEvent;
}
