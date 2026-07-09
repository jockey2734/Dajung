import { afterEach, describe, expect, it, vi } from "vitest";

// The real `next-auth` package transitively imports `next/server`, which
// fails to resolve under vitest's Node-ESM loader (works fine inside actual
// Next.js builds — this is a vitest/next-auth interop gap, not a bug in our
// code). We only need CredentialsSignin's shape (a subclassable Error with
// a `.code`), so stub the package instead of fighting module resolution.
// 실제 `next-auth`는 `next/server`를 끌어오는데 vitest의 Node-ESM 로더에서
// resolve가 안 된다(실제 Next.js 빌드에선 정상 — vitest/next-auth 궁합
// 문제지 우리 코드 버그 아님). CredentialsSignin의 모양(코드가 있는
// 서브클래싱 가능한 Error)만 필요하므로 모듈 resolve와 씨름하는 대신 스텁한다.
vi.mock("next-auth", () => ({
  CredentialsSignin: class CredentialsSignin extends Error {
    code?: string;
    constructor(code?: string) {
      super(code);
      this.code = code;
    }
  },
}));

const { ApiSigninError, credentialsSignin } = await import("@/lib/credentials-signin");

function jsonResponse(body: unknown, ok: boolean) {
  return { ok, json: async () => body } as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("credentialsSignin", () => {
  it("throws validation without calling the API when fields are missing", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    await expect(credentialsSignin(undefined, "pw")).rejects.toMatchObject({
      code: "validation",
    });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("returns the user + accessToken on a 200 from /auth/signin", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            access_token: "jwt-token",
            user: { id: "u1", email: "a@b.com", name: "임운하", role: "owner" },
          },
          true,
        ),
      ),
    );

    const result = await credentialsSignin("a@b.com", "correct-password");

    expect(result).toEqual({
      id: "u1",
      email: "a@b.com",
      name: "임운하",
      role: "owner",
      accessToken: "jwt-token",
    });
  });

  it("throws the API's error code (e.g. bad_credentials) on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ error: { code: "bad_credentials", message: "..." } }, false),
      ),
    );

    await expect(credentialsSignin("a@b.com", "wrong")).rejects.toThrow(ApiSigninError);
    await expect(credentialsSignin("a@b.com", "wrong")).rejects.toMatchObject({
      code: "bad_credentials",
    });
  });

  it("falls back to bad_credentials if the error body isn't parseable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => {
          throw new Error("not json");
        },
      } as unknown as Response),
    );

    await expect(credentialsSignin("a@b.com", "wrong")).rejects.toMatchObject({
      code: "bad_credentials",
    });
  });
});
