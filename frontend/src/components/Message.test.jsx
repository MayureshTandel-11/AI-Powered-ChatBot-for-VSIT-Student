import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Message from "./Message.jsx";

describe("Message component", () => {
  it("renders assistant message with sources", () => {
    render(
      <Message
        role="assistant"
        content="Students must maintain attendance."
        intent="attendance"
        sources={[{ document: "attendance_policy.txt", page: 1 }]}
      />
    );

    expect(screen.getByText("Students must maintain attendance.")).toBeTruthy();
    expect(screen.getByText("attendance_policy.txt (page 1)")).toBeTruthy();
    expect(screen.getByText("attendance")).toBeTruthy();
  });

  it("renders loading indicator", () => {
    const { container } = render(<Message role="assistant" content="" isLoading />);
    expect(container.querySelector(".typing-indicator")).toBeTruthy();
  });
});
