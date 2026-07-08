import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface User {
    role: "owner" | "staff";
    accessToken: string;
  }

  interface Session {
    user: {
      id: string;
      role: "owner" | "staff";
    } & DefaultSession["user"];
  }
}
