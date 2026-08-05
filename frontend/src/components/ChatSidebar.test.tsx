import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { ChatSidebar } from "@/components/ChatSidebar";
import { UnauthorizedError } from "@/lib/api";

vi.mock("@/lib/chatApi", () => ({
  fetchMessages: vi.fn(),
  sendChatMessage: vi.fn(),
}));

import * as chatApi from "@/lib/chatApi";

const mockedChatApi = vi.mocked(chatApi);

beforeEach(() => {
  vi.clearAllMocks();
  mockedChatApi.fetchMessages.mockResolvedValue([]);
});

describe("ChatSidebar", () => {
  it("loads and renders prior conversation history on mount", async () => {
    mockedChatApi.fetchMessages.mockResolvedValue([
      { role: "user", content: "Hello" },
      { role: "assistant", content: "Hi there" },
    ]);

    render(<ChatSidebar onBoardChanged={vi.fn()} />);

    expect(await screen.findByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("Hi there")).toBeInTheDocument();
  });

  it("shows an empty-state hint when there is no history", async () => {
    render(<ChatSidebar onBoardChanged={vi.fn()} />);

    expect(await screen.findByText(/ask me to create, move, or edit/i)).toBeInTheDocument();
  });

  it("sends a message, shows the reply, and triggers a board refresh", async () => {
    mockedChatApi.sendChatMessage.mockResolvedValue({ reply: "Moved it to Done" });
    const onBoardChanged = vi.fn();

    render(<ChatSidebar onBoardChanged={onBoardChanged} />);
    await screen.findByText(/ask me to create/i);

    const input = screen.getByLabelText("Chat message");
    await userEvent.type(input, "move the card to done");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(screen.getByText("move the card to done")).toBeInTheDocument();
    expect(mockedChatApi.sendChatMessage).toHaveBeenCalledWith("move the card to done");

    expect(await screen.findByText("Moved it to Done")).toBeInTheDocument();
    expect(onBoardChanged).toHaveBeenCalledTimes(1);
    expect(input).toHaveValue("");
  });

  it("shows a thinking indicator while waiting for a reply", async () => {
    let resolveSend: (value: { reply: string }) => void = () => {};
    mockedChatApi.sendChatMessage.mockReturnValue(
      new Promise((resolve) => {
        resolveSend = resolve;
      })
    );

    render(<ChatSidebar onBoardChanged={vi.fn()} />);
    await screen.findByText(/ask me to create/i);

    await userEvent.type(screen.getByLabelText("Chat message"), "hi");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByText(/thinking/i)).toBeInTheDocument();

    resolveSend({ reply: "Hello!" });
    await screen.findByText("Hello!");
  });

  it("reverts the optimistic message and shows an error banner on failure", async () => {
    mockedChatApi.sendChatMessage.mockRejectedValue(new Error("boom"));

    render(<ChatSidebar onBoardChanged={vi.fn()} />);
    await screen.findByText(/ask me to create/i);

    const input = screen.getByLabelText("Chat message");
    await userEvent.type(input, "hi there");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn.t get a reply/i);
    expect(screen.queryByText("hi there")).not.toBeInTheDocument();
    expect(input).toHaveValue("hi there");
  });

  it("does not send an empty or whitespace-only message", async () => {
    render(<ChatSidebar onBoardChanged={vi.fn()} />);
    await screen.findByText(/ask me to create/i);

    await userEvent.type(screen.getByLabelText("Chat message"), "   ");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(mockedChatApi.sendChatMessage).not.toHaveBeenCalled();
  });

  it("redirects when loading history is unauthorized", async () => {
    mockedChatApi.fetchMessages.mockRejectedValue(new UnauthorizedError());
    const onSessionExpired = vi.fn();

    render(<ChatSidebar onBoardChanged={vi.fn()} onSessionExpired={onSessionExpired} />);

    await waitFor(() => expect(onSessionExpired).toHaveBeenCalledTimes(1));
  });

  it("redirects when sending a message is unauthorized", async () => {
    mockedChatApi.sendChatMessage.mockRejectedValue(new UnauthorizedError());
    const onSessionExpired = vi.fn();

    render(<ChatSidebar onBoardChanged={vi.fn()} onSessionExpired={onSessionExpired} />);
    await screen.findByText(/ask me to create/i);

    await userEvent.type(screen.getByLabelText("Chat message"), "hi");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(onSessionExpired).toHaveBeenCalledTimes(1));
  });
});
