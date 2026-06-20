export const authRoutes = ["/login", "/register"] as const;

export const protectedRoutes = [
  "/chat",
  "/wrong-questions",
  "/translator",
  "/profile",
  "/favorites",
  "/following",
  "/followers",
] as const;

export const adminRoutes = ["/admin"] as const;

export function isAdminRoute(pathname: string) {
  return adminRoutes.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`)
  );
}

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
