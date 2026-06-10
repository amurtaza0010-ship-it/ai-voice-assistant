import AuthGuard from "@/components/auth-guard";
import { Sidebar } from "@/components/layout/sidebar";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <div className="mesh-bg min-h-screen flex">
        <Sidebar />

        <main className="flex-1 overflow-hidden">
          {children}
        </main>
      </div>
    </AuthGuard>
  );
}