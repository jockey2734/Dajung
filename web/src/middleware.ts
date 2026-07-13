export { auth as middleware } from "@/auth";

export const config = {
  matcher: ["/chat/:path*", "/pantry/:path*", "/files/:path*", "/admin/:path*", "/password"],
};
