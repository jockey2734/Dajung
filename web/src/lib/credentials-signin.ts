import { CredentialsSignin } from "next-auth";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://api:8000";

interface SigninUser {
  id: string;
  email: string;
  name: string;
  role: "owner" | "president" | "staff";
}

interface SigninResponse {
  access_token: string;
  user: SigninUser;
}

interface ApiErrorBody {
  error: { code: string; message: string };
}

// Carries the API's error code (bad_credentials/locked_out/...) through to the
// client so LoginForm can render serving-plan §3's message without guessing.
// API 에러 코드를 클라이언트까지 전달해 LoginForm이 serving-plan §3 메시지를
// 추측 없이 그대로 렌더링하게 한다.
export class ApiSigninError extends CredentialsSignin {
  code: string;

  constructor(code: string) {
    super(code);
    this.code = code;
  }
}

export async function credentialsSignin(
  email: unknown,
  password: unknown,
): Promise<SigninUser & { accessToken: string }> {
  if (typeof email !== "string" || typeof password !== "string") {
    throw new ApiSigninError("validation");
  }

  const res = await fetch(`${API_BASE_URL}/auth/signin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as ApiErrorBody | null;
    throw new ApiSigninError(body?.error.code ?? "bad_credentials");
  }

  const data = (await res.json()) as SigninResponse;
  return {
    id: data.user.id,
    email: data.user.email,
    name: data.user.name,
    role: data.user.role,
    accessToken: data.access_token,
  };
}
