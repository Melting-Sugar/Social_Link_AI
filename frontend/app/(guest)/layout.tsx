import { cookies } from "next/headers";
import { redirect } from "next/navigation";

// Mirror of app/(authed)/layout.tsx: login/register/forgot-username/
// forgot-password shouldn't be shown to someone who already has a
// session — redirect home instead. reset-password/terms/privacy are
// deliberately NOT in this group (or (authed)) — they must stay reachable
// regardless of auth state (reset-password is opened from an emailed
// link that may arrive to an already-logged-in browser; terms/privacy
// are legal documents a logged-out prospective user needs too).
const REFRESH_COOKIE_NAME = "refresh_token";

export default async function GuestLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  if (cookieStore.has(REFRESH_COOKIE_NAME)) {
    redirect("/");
  }

  return <>{children}</>;
}
