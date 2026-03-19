import {
  ChatStreamParseError,
  ChatStreamTransportError,
  createSseEventParser,
  streamChatCompletion,
} from "./chat-stream";

function createSseResponse(chunks: string[], status = 200): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });

  return new Response(stream, {
    status,
    headers: {
      "Content-Type": "text/event-stream",
    },
  });
}

describe("createSseEventParser", () => {
  it("parses event blocks split across chunks", () => {
    const events: Array<{ event: string; data: unknown }> = [];
    const parser = createSseEventParser((event) => events.push(event));

    parser.push('event: token\ndata: {"text":"Hello"}\n\n');
    parser.push('event: token\n');
    parser.push('data: {"text":" world"}\n\n');
    parser.flush();

    expect(events).toEqual([
      { event: "token", data: { text: "Hello" } },
      { event: "token", data: { text: " world" } },
    ]);
  });

  it("throws parse errors for invalid JSON payload", () => {
    const parser = createSseEventParser(() => undefined);

    expect(() => {
      parser.push("event: token\ndata: not-json\n\n");
    }).toThrow(ChatStreamParseError);
  });
});

describe("streamChatCompletion", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("dispatches token updates and resolves on done", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      createSseResponse([
        'event: meta\ndata: {"chat_session_id":"s1","provider":"fake","history_message_count":0}\n\n',
        'event: token\ndata: {"text":"Hello "}\n\n',
        'event: token\ndata: {"text":"world"}\n\n',
        'event: done\ndata: {"classification":"answer","chat_session_id":"s1","citations":[],"answer":"Hello world"}\n\n',
      ]),
    );

    const tokenSpy = vi.fn();
    const done = await streamChatCompletion({
      baseUrl: "http://localhost:8000",
      payload: {
        workspace_id: "w1",
        product_id: "p1",
        question: "What are users saying?",
      },
      onToken: tokenSpy,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(tokenSpy).toHaveBeenCalledWith({ text: "Hello " });
    expect(tokenSpy).toHaveBeenCalledWith({ text: "world" });
    expect(done.answer).toBe("Hello world");
    expect(done.classification).toBe("answer");
  });

  it("throws when server emits an error event", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      createSseResponse([
        'event: error\ndata: {"code":"CHAT_STREAM_ERROR","message":"provider failed"}\n\n',
      ]),
    );

    await expect(
      streamChatCompletion({
        baseUrl: "http://localhost:8000",
        payload: {
          workspace_id: "w1",
          product_id: "p1",
          question: "What are users saying?",
        },
      }),
    ).rejects.toThrow(ChatStreamTransportError);
  });

  it("throws when done event is missing", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      createSseResponse([
        'event: meta\ndata: {"chat_session_id":"s1","provider":"fake","history_message_count":0}\n\n',
        'event: token\ndata: {"text":"Hello"}\n\n',
      ]),
    );

    await expect(
      streamChatCompletion({
        baseUrl: "http://localhost:8000",
        payload: {
          workspace_id: "w1",
          product_id: "p1",
          question: "What are users saying?",
        },
      }),
    ).rejects.toThrow("done event");
  });
});
