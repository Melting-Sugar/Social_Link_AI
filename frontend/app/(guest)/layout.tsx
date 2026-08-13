import { GuestGuard } from "@/components/GuestGuard";

// Mirror of app/(authed)/layout.tsx: login/register/forgot-username/
// forgot-password shouldn't be shown to someone who already has a
// session — redirect home instead. See GuestGuard for why this is
// client-side only (same cross-domain reasoning as (authed)/layout.tsx).
// reset-password/terms/privacy are deliberately NOT in this group (or
// (authed)) — they must stay reachable regardless of auth state
// (reset-password is opened from an emailed link that may arrive to an
// already-logged-in browser; terms/privacy are legal documents a
// logged-out prospective user needs too).
export default function GuestLayout({ children }: { children: React.ReactNode }) {
  return <GuestGuard>{children}</GuestGuard>;
}
