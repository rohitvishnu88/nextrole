"use client";
import { createContext, useContext, useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { Me } from "@/lib/types";
import { PageCircle } from "@/components/ui/PageCircle";
import { UsageProvider } from "@/lib/useUsage";

const MeContext = createContext<Me | null>(null);

export function useMe(): Me | null {
  return useContext(MeContext);
}

type State =
  | { kind: "loading" }
  | { kind: "signed_in"; me: Me }
  | { kind: "signed_out"; error: "" | "failed" }
  | { kind: "not_invited"; email: string };

function Screen({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="relative overflow-hidden min-h-screen px-6 pt-24">
      <PageCircle colour="blue" />
      <div className="relative max-w-xl space-y-6">
        <p className="font-bold text-lg">nextrole.</p>
        <h1 className="text-6xl font-bold leading-none">{title}</h1>
        {children}
      </div>
    </div>
  );
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const authError = params.get("auth_error");
    if (authError === "not_invited") {
      setState({ kind: "not_invited", email: params.get("email") ?? "" });
      return;
    }
    api.getMe()
      .then(me => setState({ kind: "signed_in", me }))
      .catch((e: unknown) => {
        if (e instanceof api.ApiError && e.status === 403) {
          const detail = e.detail as { email?: string } | undefined;
          setState({ kind: "not_invited", email: detail?.email ?? "" });
        } else {
          setState({ kind: "signed_out", error: authError === "failed" ? "failed" : "" });
        }
      });
  }, []);

  if (state.kind === "loading") return null;

  if (state.kind === "signed_in") {
    return (
      <MeContext.Provider value={state.me}>
        <UsageProvider>{children}</UsageProvider>
      </MeContext.Provider>
    );
  }

  if (state.kind === "not_invited") {
    return (
      <Screen title="invite only">
        <p className="text-base">
          This app is invite-only. Ask Rohit to add {state.email ? <span className="font-bold">{state.email}</span> : "your Google email"}.
        </p>
        <a href="/api/auth/login" className="inline-block border-[1.5px] border-ink px-4 py-2 text-sm font-bold hover:bg-ink hover:text-paper">
          try another account
        </a>
      </Screen>
    );
  }

  return (
    <Screen title="sign in">
      <p className="text-base">Tailor resumes, track applications and search for jobs — your data stays private to you.</p>
      {state.error === "failed" && (
        <p className="text-sm bg-red/10 border-l-[3px] border-red px-3 py-2">sign-in failed — try again.</p>
      )}
      <a href="/api/auth/login" className="inline-block bg-ink text-paper px-5 py-2.5 text-sm font-bold hover:bg-ink/80">
        sign in with google
      </a>
    </Screen>
  );
}
