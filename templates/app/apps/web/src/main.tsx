import { StrictMode, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api.js";
import { Field, Problem, say, sayCode, type User } from "./parts.js";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Settings as SettingsIcon } from "lucide-react";
import { Centrepiece } from "./centrepiece.js";
import { Intro } from "./intro.js";
import { Backdrop } from "./backdrop.js";
import { Settings } from "./settings.js";
import { Boot, ICON_BUTTON, ThemeToggle, Wordmark } from "./theme.js";
import "./tailwind.css";

type Provider = { id: string; name: string };

/** Why a trip to a provider's login page ended back here, read once from the address and then removed from it. */
function returnedError(): string | null {
  const code = new URLSearchParams(location.search).get("signin");
  if (!code) return null;
  history.replaceState(null, "", location.pathname);
  return sayCode(code);
}

const Centered = ({ children }: { children: ReactNode }) => (
  <main className="relative grid min-h-svh place-items-center p-4">
    <div className="absolute top-3 right-3"><ThemeToggle /></div>
    {children}
  </main>
);

function SignIn({ onUser }: { onUser: (user: User) => void }) {
  const [error, setError] = useState<string | null>(returnedError);
  const [busy, setBusy] = useState(false);
  const [providers, setProviders] = useState<Provider[]>([]);
  useEffect(() => void api<{ providers: Provider[] }>("GET", "/auth/providers").then((reply) => setProviders(reply.providers), () => undefined), []);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      onUser((await api<{ user: User }>("POST", "/auth/login", { email: form.get("email"), password: form.get("password") })).user);
    } catch (failure) {
      setError(say(failure));
    }
    setBusy(false);
  };
  return (
    <Card className="w-full max-w-sm">
      <CardHeader><Wordmark className="text-lg" decode /></CardHeader>
      <CardContent>
        <form className="grid gap-4" onSubmit={(event) => void submit(event)}>
          <Field label="Email"><Input name="email" type="email" autoComplete="username" required autoFocus /></Field>
          <Field label="Password"><Input name="password" type="password" autoComplete="current-password" required /></Field>
          <Problem>{error}</Problem>
          <Button type="submit" disabled={busy}>Sign in</Button>
          {providers.map((provider) => <Button key={provider.id} variant="outline" asChild><a href={`/api/auth/oidc/${provider.id}`}>Sign in with {provider.name}</a></Button>)}
        </form>
      </CardContent>
    </Card>
  );
}

/** Shown while the password is one somebody else chose: nothing else opens until it is replaced. */
function ChoosePassword({ user, onUser }: { user: User; onUser: (user: User) => void }) {
  const [error, setError] = useState<string | null>(null);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (form.get("next") !== form.get("again")) return setError("The two new passwords are not the same.");
    setError(null);
    try {
      onUser((await api<{ user: User }>("POST", "/auth/password", { current: form.get("current"), next: form.get("next") })).user);
    } catch (failure) {
      setError(say(failure));
    }
  };
  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <CardTitle>Choose your password</CardTitle>
        <p className="text-sm text-muted-foreground">{user.email}</p>
      </CardHeader>
      <CardContent>
        <form className="grid gap-4" onSubmit={(event) => void submit(event)}>
          <Field label="The password you were given"><Input name="current" type="password" autoComplete="current-password" required autoFocus /></Field>
          <Field label="New password"><Input name="next" type="password" autoComplete="new-password" minLength={10} required /></Field>
          <Field label="New password again"><Input name="again" type="password" autoComplete="new-password" minLength={10} required /></Field>
          <Problem>{error}</Problem>
          <Button type="submit">Save</Button>
        </form>
      </CardContent>
    </Card>
  );
}

/** Which screen the address names: "#/settings/users" is the settings screen, on its "users" page. */
function useRoute(): string[] {
  const read = () => location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const changed = () => setRoute(read());
    addEventListener("hashchange", changed);
    return () => removeEventListener("hashchange", changed);
  }, []);
  return route;
}

function App() {
  // undefined: not known yet. null: signed out.
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const route = useRoute();
  // The opening screen comes first on every load, except on the way back from a provider's login page.
  const [entered, setEntered] = useState(() => new URLSearchParams(location.search).has("signin"));
  const enter = () => setEntered(true);
  useEffect(() => {
    api<{ user: User }>("GET", "/auth/me").then((reply) => setUser(reply.user), () => setUser(null));
  }, []);
  if (user === undefined) return null;
  // One backdrop under every screen, so it carries on undisturbed as they change.
  return <><Backdrop />{screen(user)}</>;

  function screen(user: User | null) {
    if (user === null && !entered) return <Intro action="Enter" ready="Standing by" leaving="Entering" onEnter={enter}><Centrepiece /></Intro>;
    if (user === null) return <Centered><Boot className="w-full max-w-sm"><SignIn onUser={setUser} /></Boot></Centered>;
    if (user.mustChange) return <Centered><Boot className="w-full max-w-sm"><ChoosePassword user={user} onUser={setUser} /></Boot></Centered>;
    return (
      <>
        <header className="flex items-center gap-1 border-b px-4 py-3">
          <a href="#/" className="flex-1"><Wordmark className="text-sm" /></a>
          <ThemeToggle />
          <a href="#/settings" aria-label="Settings" aria-current={route[0] === "settings" ? "page" : undefined} className={`${ICON_BUTTON} aria-[current]:text-primary`}><SettingsIcon /></a>
        </header>
        {route[0] === "settings" ? (
          <Settings user={user} page={route[1]} onSignedOut={() => setUser(null)} />
        ) : (
          <main className="grid min-h-[40svh] place-items-center text-sm text-muted-foreground">The library comes next.</main>
        )}
      </>
    );
  }
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
