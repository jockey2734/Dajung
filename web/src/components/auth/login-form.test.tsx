import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const signInMock = vi.fn();
vi.mock("next-auth/react", () => ({ signIn: (...args: unknown[]) => signInMock(...args) }));

const pushMock = vi.fn();
const refreshMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, refresh: refreshMock }),
  useSearchParams: () => new URLSearchParams(),
}));

const { LoginForm } = await import("@/components/auth/login-form");

afterEach(() => {
  cleanup();
  signInMock.mockReset();
  pushMock.mockReset();
  refreshMock.mockReset();
});

async function fillAndSubmit(email: string, password: string) {
  const user = userEvent.setup();
  render(<LoginForm />);
  await user.type(screen.getByLabelText("이메일"), email);
  await user.type(screen.getByLabelText("비밀번호"), password);
  await user.click(screen.getByRole("button", { name: "로그인" }));
}

describe("LoginForm", () => {
  it("renders serving-plan §3's bad_credentials message on failure", async () => {
    signInMock.mockResolvedValue({
      error: "CredentialsSignin",
      code: "bad_credentials",
      status: 401,
      ok: false,
      url: null,
    });

    await fillAndSubmit("a@b.com", "wrong-password");

    expect(
      await screen.findByText("이메일 또는 비밀번호가 올바르지 않습니다."),
    ).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("renders the locked_out message on a 429", async () => {
    signInMock.mockResolvedValue({
      error: "CredentialsSignin",
      code: "locked_out",
      status: 429,
      ok: false,
      url: null,
    });

    await fillAndSubmit("a@b.com", "wrong-password");

    expect(
      await screen.findByText("로그인 시도가 너무 많습니다. 1시간 후 다시 시도해 주세요."),
    ).toBeInTheDocument();
  });

  it("navigates to /chat and refreshes on success, without showing an error", async () => {
    signInMock.mockResolvedValue({ error: undefined, status: 200, ok: true, url: "/chat" });

    await fillAndSubmit("a@b.com", "correct-password");

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/chat"));
    expect(refreshMock).toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
