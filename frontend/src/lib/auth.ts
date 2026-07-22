export type SessionResponse = { authenticated: boolean };

export async function fetchSession(): Promise<boolean> {
  const response = await fetch("/api/session");
  if (!response.ok) {
    return false;
  }
  const data: SessionResponse = await response.json();
  return data.authenticated;
}

export async function login(username: string, password: string): Promise<boolean> {
  const response = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return response.ok;
}

export async function logout(): Promise<void> {
  await fetch("/api/logout", { method: "POST" });
}
