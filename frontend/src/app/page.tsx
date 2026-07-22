"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { KanbanBoard } from "@/components/KanbanBoard";
import { fetchSession, logout } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    fetchSession().then((isAuthenticated) => {
      if (isAuthenticated) {
        setAuthenticated(true);
      } else {
        router.replace("/login");
      }
    });
  }, [router]);

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  if (!authenticated) {
    return null;
  }

  return <KanbanBoard onLogout={handleLogout} />;
}
