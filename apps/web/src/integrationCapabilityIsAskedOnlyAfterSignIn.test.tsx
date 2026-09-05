/**
 * When the deployment-shape probe is allowed to run, and what it may reveal.
 *
 * `IntegrationPage.test.tsx` covers the *role* half of Integration's
 * visibility. This file covers the other half: the runtime capability probe in
 * `App.tsx`, which was previously unguarded by any test.
 *
 * Two properties are held here.
 *
 * 1. **Nothing is asked before there is a session.** The probe's answer is only
 *    consumable by the menu and the navigation guard, and both live behind the
 *    session gate, so asking earlier is an unauthenticated request for an
 *    answer nobody can read. It also had a real cost: an extra fetch on the
 *    login screen consumed the single mocked `Response` in
 *    `authLogin.test.tsx`, and because a body may only be read once the sign-in
 *    call downstream of it failed. That test is deliberately left as it was —
 *    it was describing the application correctly.
 *
 * 2. **Integration stays hidden until the probe says `true`.** Not-yet-answered
 *    and failed resolve the same way as "no". Each refusal below is paired with
 *    a control — a positive case that does reveal the surface, and a
 *    neighbouring menu item that stays present — so "hidden" cannot be a render
 *    that silently produced nothing.
 *
 * `hiddenNavIds` is the single authority for "may this page be shown". It is
 * consulted in three places — the rendered menu, the navigation guard, and the
 * page actually rendered. The third was added after an audit found that the
 * content area keyed off the raw `page` state, so a selection made while
 * permitted kept rendering after it stopped being permitted. Asserting on the
 * menu therefore does *not* assert on the route, and the last describe below
 * covers the route directly.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { App as AntApp, ConfigProvider } from "antd";
import { ActorProvider } from "./ActorContext";
import App from "./App";
import { integrationApi } from "./api";
import { storeSession, type Session } from "./auth";

const CAPABILITY_PATH = "/api/integration/capability";
const KEYS_PATH = "/api/integration/keys";
const LOGIN_PATH = "/api/auth/login";

type CapabilityAnswer = { manages_subscription_keys: boolean } | "reject";

function adminSession(overrides: Partial<Session> = {}): Session {
  return {
    accessToken: "tok-test",
    expiresAt: new Date(Date.now() + 3600_000).toISOString(),
    role: "admin",
    name: "Ada Admin",
    ...overrides,
  };
}

/**
 * A fetch stub that answers per call rather than handing every caller the same
 * `Response`. A shared response object is not merely untidy: its body can be
 * read once, so the second reader gets `TypeError: Body is unusable`.
 *
 * The returned `state` is mutable so a test can change the deployment's answer,
 * or make the next call unauthorized, part-way through — which is how the
 * session-change case below is driven through the real 401 path rather than by
 * reaching into the component.
 */
function routedFetch(capability: CapabilityAnswer) {
  const state = {
    capability,
    /** When set, every non-login call answers 401, as an expired token would. */
    unauthorized: false,
    loginRole: "admin" as Session["role"],
  };
  const urls: string[] = [];
  const spy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = typeof input === "string" ? input : (input as Request).url ?? String(input);
    urls.push(url);

    // Sign-in must keep working while the rest of the API is refusing, since
    // that is precisely the state a user signs back in from.
    if (url.includes(LOGIN_PATH)) {
      return Promise.resolve(
        json({
          access_token: "tok-after-reauth",
          token_type: "bearer",
          expires_at: new Date(Date.now() + 3600_000).toISOString(),
          role: state.loginRole,
          name: "Ada Admin",
        }),
      );
    }

    if (state.unauthorized) return Promise.resolve(json({ detail: "expired" }, 401));

    if (url.includes(CAPABILITY_PATH)) {
      if (state.capability === "reject") return Promise.reject(new TypeError("network down"));
      return Promise.resolve(json(state.capability));
    }
    if (url.includes(KEYS_PATH)) return Promise.resolve(json({ keys: [] }));
    // Everything else the shell loads on entry. The shapes only need to be
    // harmless; this file is not asserting on them.
    if (url.includes("policy-set")) return Promise.resolve(json([]));
    return Promise.resolve(json({}));
  });
  return { spy, urls, state, capabilityCalls: () => urls.filter((u) => u.includes(CAPABILITY_PATH)) };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }));
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function renderApp() {
  return render(
    <ConfigProvider>
      <AntApp>
        <ActorProvider>
          <App />
        </ActorProvider>
      </AntApp>
    </ConfigProvider>,
  );
}

const integrationItems = () => screen.queryAllByRole("menuitem", { name: /Integration/ });
const dashboardItems = () => screen.queryAllByRole("menuitem", { name: /Dashboard/ });

describe("the deployment-shape probe is not asked before sign-in", () => {
  it("makes no capability request while there is no session", async () => {
    const fetched = routedFetch({ manages_subscription_keys: true });

    renderApp();

    // Control: the render really happened and really is the signed-out screen.
    // Without this, "no request was made" would also pass for a render that
    // threw before reaching any effect.
    expect(screen.getByText("AI to read. Evidence to prove. Determinism to decide.")).toBeTruthy();

    // Give any unguarded effect a chance to fire before concluding it did not.
    await Promise.resolve();
    expect(fetched.capabilityCalls()).toEqual([]);
  });

  it("asks once the session exists", async () => {
    storeSession(adminSession());
    const fetched = routedFetch({ manages_subscription_keys: true });

    renderApp();

    // The paired positive control for the test above: the same probe that must
    // not fire while signed out must fire once signed in, otherwise the first
    // assertion could be satisfied by a probe that never runs at all.
    await waitFor(() => expect(fetched.capabilityCalls().length).toBeGreaterThan(0));
  });
});

describe("Integration is revealed only by a true capability answer", () => {
  it("shows Integration to an administrator when the deployment issues its own keys", async () => {
    storeSession(adminSession());
    routedFetch({ manages_subscription_keys: true });

    renderApp();

    await waitFor(() => expect(integrationItems().length).toBeGreaterThan(0));
  });

  it("hides Integration when the deployment does not issue its own keys", async () => {
    storeSession(adminSession());
    routedFetch({ manages_subscription_keys: false });

    renderApp();

    // Control: the shell rendered and its menu is populated, so the absence
    // below is a refusal rather than an empty render.
    await waitFor(() => expect(dashboardItems().length).toBeGreaterThan(0));
    expect(integrationItems()).toEqual([]);
  });

  it("hides Integration when the probe fails", async () => {
    storeSession(adminSession());
    routedFetch("reject");

    renderApp();

    await waitFor(() => expect(dashboardItems().length).toBeGreaterThan(0));
    expect(integrationItems()).toEqual([]);
  });

  it("hides Integration from a non-administrator even when the deployment issues its own keys", async () => {
    // The two conditions are independent: a true probe must not be able to
    // grant the surface on its own.
    storeSession(adminSession({ role: "policy_author" }));
    routedFetch({ manages_subscription_keys: true });

    renderApp();

    await waitFor(() => expect(dashboardItems().length).toBeGreaterThan(0));
    expect(integrationItems()).toEqual([]);
  });
});

/**
 * The route half.
 *
 * Hiding a menu entry removes the way in; it does not remove a page already
 * open. `page` is component state that survives a 401, because the App-level
 * handler for a cleared session only drops the session — an explicit sign-out
 * reloads the document, but an expired token does not. So a user could open
 * Integration under a session permitted to see it, lose that session, sign in
 * as someone else, and still be looking at the page: the menu entry would be
 * gone while the component below it kept rendering.
 *
 * These cases drive the whole cycle through the real code path — a genuine 401
 * from `request()`, the real login form — rather than reaching into state, so
 * they fail if any link in that chain stops enforcing the rule.
 */
describe("an Integration page already open is re-checked against the new session", () => {
  const INTEGRATION_PAGE_MARKER = "Generate a key";
  const integrationPage = () => screen.queryAllByText(INTEGRATION_PAGE_MARKER);

  async function openIntegration() {
    await waitFor(() => expect(integrationItems().length).toBeGreaterThan(0));
    fireEvent.click(integrationItems()[0]);
    await waitFor(() => expect(integrationPage().length).toBeGreaterThan(0));
  }

  /** Expire the session the way the server does, then sign in as someone new. */
  async function reauthenticate(
    fetched: ReturnType<typeof routedFetch>,
    as: { role: Session["role"]; capability: CapabilityAnswer },
  ) {
    fetched.state.unauthorized = true;
    await act(async () => {
      await integrationApi.list().catch(() => undefined);
    });
    await waitFor(() =>
      expect(screen.getByText("AI to read. Evidence to prove. Determinism to decide.")).toBeTruthy(),
    );

    fetched.state.unauthorized = false;
    fetched.state.capability = as.capability;
    fetched.state.loginRole = as.role;

    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "ada" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(dashboardItems().length).toBeGreaterThan(0));
  }

  it("stops rendering it when the deployment no longer issues its own keys", async () => {
    storeSession(adminSession());
    const fetched = routedFetch({ manages_subscription_keys: true });

    renderApp();
    await openIntegration();

    await reauthenticate(fetched, { role: "admin", capability: { manages_subscription_keys: false } });

    expect(integrationItems()).toEqual([]);
    expect(integrationPage()).toEqual([]);
  });

  it("stops rendering it when the new session's role may not see it", async () => {
    // The other half of the same rule: the deployment still issues keys, but
    // this principal may not manage them.
    storeSession(adminSession());
    const fetched = routedFetch({ manages_subscription_keys: true });

    renderApp();
    await openIntegration();

    await reauthenticate(fetched, {
      role: "policy_author",
      capability: { manages_subscription_keys: true },
    });

    expect(integrationItems()).toEqual([]);
    expect(integrationPage()).toEqual([]);
  });

  it("keeps rendering it when the new session may still see it", async () => {
    // The control for both refusals above. Without it, they would also pass if
    // re-authentication simply never restored any page at all.
    storeSession(adminSession());
    const fetched = routedFetch({ manages_subscription_keys: true });

    renderApp();
    await openIntegration();

    await reauthenticate(fetched, {
      role: "admin",
      capability: { manages_subscription_keys: true },
    });

    await waitFor(() => expect(integrationPage().length).toBeGreaterThan(0));
    expect(integrationItems().length).toBeGreaterThan(0);
  });
});
