export const authRoutes = ["/login", "/register"] as const;

export const protectedRoutes = [
  "/chat",
  "/wrong-questions",
  "/profile",
  "/favorites",
  "/following",
  "/followers",
] as const;

export function isAuthRoute(pathname: string) {
  return authRoutes.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`)
  );
}

export function isProtectedRoute(pathname: string) {
  return protectedRoutes.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`)
  );
}
