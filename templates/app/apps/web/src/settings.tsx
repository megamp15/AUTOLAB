// Settings: a list of pages on the left, grouped, and the chosen page beside it. The Admin
// group is for admins, on the admins' address only.
import { LogOut, ShieldCheck, UserRound, type LucideIcon } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { ApiError, api } from "./api.js";
import { Problem, say, type User } from "./parts.js";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Ticker } from "@/components/ui/ticker";

type Page = { id: string; label: string; icon: LucideIcon };
type Group = { label: string; pages: Page[] };

const Heading = ({ children, count }: { children: string; count?: number }) => (
  <h1 className="mono-caps mb-4 flex items-baseline justify-between text-foreground">
    {children}
    {count === undefined ? null : <span className="text-muted-foreground"><Ticker value={count} format={(shown) => String(Math.round(shown)).padStart(2, "0")} /></span>}
  </h1>
);

function Account({ user, onSignedOut }: { user: User; onSignedOut: () => void }) {
  return (
    <>
      <Heading>Account</Heading>
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 border-y py-4 text-sm">
        <dt className="mono-caps text-muted-foreground">Name</dt><dd>{user.name}</dd>
        <dt className="mono-caps text-muted-foreground">Email</dt><dd className="truncate">{user.email}</dd>
      </dl>
      <Button type="button" variant="outline" className="mt-4" onClick={() => void api("POST", "/auth/logout").then(onSignedOut)}><LogOut />Sign out</Button>
    </>
  );
}

/** Who may sign in. Adding a person here is the only way an account comes to exist. */
function UserAccess({ me }: { me: User }) {
  const [users, setUsers] = useState<User[]>([]);
  const [given, setGiven] = useState<{ email: string; password: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const load = () => void api<{ users: User[] }>("GET", "/admin/users").then((reply) => setUsers(reply.users), (failure) => setError(say(failure)));
  useEffect(load, []);
  const run = async (work: () => Promise<void>) => {
    setError(null);
    try {
      await work();
      load();
    } catch (failure) {
      setError(say(failure));
    }
  };
  const add = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    void run(async () => {
      const made = await api<{ user: User; password: string | null }>("POST", "/admin/users", { email: data.get("email"), name: data.get("name"), password: data.get("password") === "on" });
      setGiven({ email: made.user.email, password: made.password });
      form.reset();
    });
  };
  const reset = (user: User) => void run(async () => setGiven({ email: user.email, password: (await api<{ password: string }>("POST", `/admin/users/${user.id}/reset`)).password }));
  const remove = (user: User) => void run(async () => {
    await api("DELETE", `/admin/users/${user.id}`);
    setRemoving(null);
    setGiven(null);
  });
  return (
    <>
      <Heading count={users.length}>User access</Heading>
      <ul className="divide-y border-y">
        {users.map((user) => (
          <li key={user.id} className="flex flex-wrap items-center justify-end gap-2 py-2.5">
            <span className="min-w-0 flex-1 basis-40">
              {user.name}
              <small className="block truncate text-xs text-muted-foreground">{user.email}{user.isAdmin ? " · admin" : ""}{user.mustChange ? " · has not signed in yet" : ""}</small>
            </span>
            {removing === user.id ? (
              <>
                <Button type="button" variant="destructive" size="sm" onClick={() => remove(user)}>Remove {user.name}</Button>
                <Button type="button" variant="outline" size="sm" onClick={() => setRemoving(null)}>Keep</Button>
              </>
            ) : (
              <>
                <Button type="button" variant="outline" size="sm" onClick={() => reset(user)}>Reset password</Button>
                {user.id === me.id ? null : <Button type="button" variant="outline" size="sm" onClick={() => setRemoving(user.id)}>Remove</Button>}
              </>
            )}
          </li>
        ))}
      </ul>
      {given ? (
        <p className="mt-4 rounded-md border px-3 py-2.5 text-sm" role="status">
          {given.password ? <>One-time password for {given.email}: <code className="font-mono select-all">{given.password}</code></> : <>{given.email} can sign in with Google or Pocket ID.</>}
        </p>
      ) : null}
      <form className="mt-4 flex flex-wrap items-center gap-2" onSubmit={add}>
        <Input className="min-w-36 flex-1" name="name" placeholder="Name" aria-label="Name" required />
        <Input className="min-w-36 flex-1" name="email" type="email" placeholder="Email" aria-label="Email" required />
        <Label className="text-muted-foreground"><Checkbox name="password" defaultChecked />Password</Label>
        <Button type="submit">Add</Button>
      </form>
      <div className="mt-3"><Problem>{error}</Problem></div>
    </>
  );
}

export function Settings({ user, page, onSignedOut }: { user: User; page: string | undefined; onSignedOut: () => void }) {
  // Accounts are managed on the admins' address only; on the public one the server answers
  // 404 and the Admin group is not shown.
  const [adminHere, setAdminHere] = useState(false);
  useEffect(() => {
    if (user.isAdmin) api("GET", "/admin/users").then(() => setAdminHere(true), (failure) => setAdminHere(!(failure instanceof ApiError && failure.status === 404)));
  }, [user.isAdmin]);
  const groups: Group[] = [
    { label: "You", pages: [{ id: "account", label: "Account", icon: UserRound }] },
    ...(adminHere ? [{ label: "Admin", pages: [{ id: "users", label: "User access", icon: ShieldCheck }] }] : []),
  ];
  const current = groups.flatMap((group) => group.pages).find((item) => item.id === page)?.id ?? "account";
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 md:flex-row md:gap-10 md:py-8">
      <nav aria-label="Settings" className="flex shrink-0 gap-6 overflow-x-auto md:w-48 md:flex-col md:gap-5">
        {groups.map((group) => (
          <div key={group.label}>
            <p className="mono-caps mb-1.5 text-[0.65rem] text-muted-foreground">{group.label}</p>
            <ul className="flex gap-1 md:flex-col">
              {group.pages.map(({ id, label, icon: Icon }) => (
                <li key={id}>
                  <a href={`#/settings/${id}`} aria-current={current === id ? "page" : undefined} className="flex items-center gap-2 border-l-2 border-transparent px-2.5 py-1.5 text-sm whitespace-nowrap text-muted-foreground hover:text-foreground aria-[current]:border-primary aria-[current]:text-foreground">
                    <Icon className="size-4" />{label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <section className="min-w-0 flex-1">
        {current === "users" && adminHere ? <UserAccess me={user} /> : <Account user={user} onSignedOut={onSignedOut} />}
      </section>
    </div>
  );
}
