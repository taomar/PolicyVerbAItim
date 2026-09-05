import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import PolicyIndexConsolePage, { consoleRowIsRebuildable } from "./PolicyIndexConsolePage";
import { canAccessPage, surfaceAccess } from "./rbac";
import type { PolicyIndexConsole, PolicyIndexConsoleRow } from "./api";

/**
 * Who may see the index console, and what it is honest about.
 *
 * WHY THIS SCREEN EXISTS
 *
 * The recorded index state was only ever visible one project at a time, on that
 * project's Overview tab. The question an operator actually has — "is anything
 * in this deployment unmatchable right now, and since when" — could only be
 * answered by opening every project in turn. A project whose index quietly
 * failed four publishes ago was indistinguishable from one nobody had opened.
 *
 * WHAT THESE TESTS ARE MOSTLY ABOUT
 *
 * Two things a console gets wrong in ways nobody notices until it costs an
 * afternoon:
 *
 *   - **collapsing the health words.** Three of the seven would then be wrong.
 *     `unvalidated` is refused by retrieval exactly as a broken index is, but
 *     the repair is a validation rather than a full re-render; `empty` is a
 *     project with nothing published, where nothing is wrong at all.
 *   - **rendering a failure as terminal.** A broken index that cannot be
 *     repaired from the one screen built to find it is a dead end, so `failed`
 *     must stay rebuildable.
 */

function row(overrides: Partial<PolicyIndexConsoleRow> = {}): PolicyIndexConsoleRow {
  return {
    policy_set_key: "alpha",
    policy_set_name: "Alpha project",
    index_name: "policy-cases-alpha-abc",
    health: "healthy",
    last_attempt: "built",
    freshness: "current",
    active_version_number: 3,
    indexed_version_number: 3,
    attempted_version_number: 3,
    document_count: 74,
    built_at: "2026-08-18T12:00:00Z",
    attempted_at: "2026-08-18T12:00:00Z",
    error: null,
    projection_profile: "english-v1",
    expected_projection_profile: "english-v1",
    quality_state: "passed",
    quality_profile: "faithfulness-v1",
    quality_checked_documents: 74,
    quality_structural_findings: 0,
    quality_min_similarity: 0.82,
    quality_mean_similarity: 0.94,
    quality_validated_at: "2026-08-18T12:00:00Z",
    latest_build: { active: false },
    ...overrides,
  };
}

function consoleReport(overrides: Partial<PolicyIndexConsole> = {}): PolicyIndexConsole {
  return { projects: [row()], active: { active: false }, ...overrides };
}

let report: PolicyIndexConsole;
let rebuildStatus = 200;
let requestedUrls: string[] = [];

beforeEach(() => {
  report = consoleReport();
  rebuildStatus = 200;
  requestedUrls = [];

  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      requestedUrls.push(`${init?.method ?? "GET"} ${url}`);
      if (url.includes("/policy-index/rebuild")) {
        if (rebuildStatus === 409) {
          return {
            ok: false,
            status: 409,
            json: async () => ({
              detail: {
                message: "another policy index build is already running",
                active: { active: true, operation_id: "op-other", policy_set_key: "beta" },
              },
            }),
          } as unknown as Response;
        }
        return {
          ok: true,
          status: 200,
          json: async () => ({ state: "built", operation_id: "op-new" }),
        } as unknown as Response;
      }
      if (url.includes("/api/policy-index/builds/")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ active: false }),
        } as unknown as Response;
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({ ...report }),
      } as unknown as Response;
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("who may reach the console", () => {
  it("is visible to an administrator", () => {
    expect(canAccessPage("admin", "policy-index")).toBe(true);
  });

  it.each(["viewer", "policy_author"])("is hidden from %s", (role) => {
    // An author repairs their own project's index from the project page, which
    // is where the work is. Enumerating every project's index name and failure
    // history is an operator's view of the estate — and the server agrees: the
    // aggregate endpoint is ADMINISTER-band and answers 403 whatever the
    // interface offers.
    expect(canAccessPage(role, "policy-index")).toBe(false);
  });

  it("is hidden from an unknown role by the closed default", () => {
    expect(canAccessPage("auditor-we-never-defined", "policy-index")).toBe(false);
    expect(canAccessPage(undefined, "policy-index")).toBe(false);
  });

  it("resolves to a deliberate decision for every role, not an accidental absence", () => {
    // The control for the refusals above: `surfaceAccess` returns a closed
    // default for anything it does not recognise, so "hidden" alone cannot
    // distinguish "deliberately denied" from "never added to the map".
    for (const role of ["viewer", "policy_author", "admin"]) {
      expect(
        surfaceAccess(role, "policy-index").blockedReason,
        role,
      ).not.toBe(surfaceAccess(role, "a-surface-that-does-not-exist").blockedReason);
    }
  });

  it("does not cost an administrator anything else", () => {
    // Guards against a map edit that granted this surface by overwriting a
    // neighbouring entry.
    for (const id of ["dashboard", "projects", "document-inbox", "evaluate", "integration"]) {
      expect(canAccessPage("admin", id), id).toBe(true);
    }
  });
});

describe("what the console shows", () => {
  it("lists every project, including the one that has never been indexed", async () => {
    // A console that silently omitted them would answer "which projects are
    // unindexed" with a blank space — the one answer that looks like good news.
    report = consoleReport({
      projects: [
        row(),
        row({
          policy_set_key: "beta",
          policy_set_name: "Beta project",
          health: "not_built",
          last_attempt: "never_attempted",
          document_count: 0,
          built_at: null,
          quality_state: null,
        }),
      ],
    });
    render(<PolicyIndexConsolePage />);

    await waitFor(() => expect(screen.getByText("Alpha project")).toBeTruthy());
    expect(screen.getByText("Beta project")).toBeTruthy();
    expect(screen.getByText("Healthy")).toBeTruthy();
    expect(screen.getByText("Never built")).toBeTruthy();
  });

  it("keeps the health states apart rather than reducing them to good and bad", async () => {
    report = consoleReport({
      projects: [
        row({ policy_set_key: "a", policy_set_name: "A", health: "healthy" }),
        row({ policy_set_key: "b", policy_set_name: "B", health: "unvalidated" }),
        row({ policy_set_key: "c", policy_set_name: "C", health: "stale" }),
        row({ policy_set_key: "d", policy_set_name: "D", health: "failed" }),
        row({ policy_set_key: "e", policy_set_name: "E", health: "empty" }),
      ],
    });
    render(<PolicyIndexConsolePage />);

    await waitFor(() => expect(screen.getByText("Healthy")).toBeTruthy());
    // Each of these means something different to the person reading it, and two
    // of them are repaired by different actions.
    expect(screen.getByText("Unvalidated")).toBeTruthy();
    expect(screen.getByText("Stale")).toBeTruthy();
    expect(screen.getByText("Failed")).toBeTruthy();
    expect(screen.getByText("Nothing to index")).toBeTruthy();
  });

  it("shows the recorded failure reason for a broken index", async () => {
    report = consoleReport({
      projects: [row({ health: "failed", error: "Azure AI Search accepted 61 of 74 documents" })],
    });
    render(<PolicyIndexConsolePage />);
    await waitFor(() => expect(screen.getByText(/61 of 74 documents/)).toBeTruthy());
  });

  it("says a corpus was never checked rather than implying it passed", async () => {
    // Absent is not a pass. Retrieval refuses on an unchecked corpus exactly as
    // it refuses on a failed one, so a blank cell here would be the one
    // rendering that contradicts what the project actually does.
    report = consoleReport({
      projects: [row({ health: "unvalidated", quality_state: null, quality_checked_documents: null })],
    });
    render(<PolicyIndexConsolePage />);
    await waitFor(() => expect(screen.getByText("never checked")).toBeTruthy());
  });
});

describe("repairing one project", () => {
  it("offers a rebuild on a failed index and starts one", async () => {
    // The dead end this prevents: a broken project rendered as terminal, with
    // no control and no route back, on the one screen built to find it.
    report = consoleReport({ projects: [row({ health: "failed", error: "the build failed" })] });
    render(<PolicyIndexConsolePage />);

    const button = await screen.findByRole("button", { name: "Rebuild" });
    expect(button.hasAttribute("disabled")).toBe(false);
    await act(async () => {
      fireEvent.click(button);
    });

    await waitFor(() =>
      expect(
        requestedUrls.some((entry) => entry.startsWith("POST") && entry.includes("/policy-index/rebuild")),
      ).toBe(true),
    );
    // The id is generated before the request, because the response does not
    // exist until the build has finished — which is after the point anybody
    // wanted to watch it.
    const rebuild = requestedUrls.find((entry) => entry.includes("/policy-index/rebuild"));
    expect(rebuild).toMatch(/operation_id=/);
  });

  it("offers no rebuild where a rebuild is not the repair", () => {
    // `unvalidated` is fixed by a validation, which re-renders nothing;
    // offering the expensive repair for the cheap fault sends an operator to do
    // the wrong thing. `empty` has no work to do at all.
    expect(consoleRowIsRebuildable(row({ health: "failed" }))).toBe(true);
    expect(consoleRowIsRebuildable(row({ health: "stale" }))).toBe(true);
    expect(consoleRowIsRebuildable(row({ health: "not_built" }))).toBe(true);
    expect(consoleRowIsRebuildable(row({ health: "unvalidated" }))).toBe(false);
    expect(consoleRowIsRebuildable(row({ health: "empty" }))).toBe(false);
    expect(consoleRowIsRebuildable(row({ health: "healthy" }))).toBe(false);
    expect(consoleRowIsRebuildable(row({ health: "building" }))).toBe(false);
  });

  it("disables every rebuild while any build is running, including another project's", async () => {
    // The slot is deployment-wide. A control that stayed enabled would send a
    // request the server answers with 409, which reads to the operator as a
    // broken button rather than as a queue they are not in.
    report = consoleReport({
      projects: [row({ health: "failed" })],
      active: { active: true, operation_id: "op-other", policy_set_key: "beta", status: "running" },
    });
    render(<PolicyIndexConsolePage />);

    const button = await screen.findByRole("button", { name: "Rebuild" });
    await waitFor(() => expect(button.hasAttribute("disabled")).toBe(true));
  });

  it("reports a refused rebuild as a conflict, not as a failure", async () => {
    // Nothing about the project changed and nothing is broken: another build
    // holds the one slot. Shown as an error, this would send somebody looking
    // for a fault that does not exist.
    report = consoleReport({ projects: [row({ health: "failed" })] });
    rebuildStatus = 409;
    render(<PolicyIndexConsolePage />);

    // Found outside `act`: an async `findBy` inside it competes with the timers
    // `act` is batching, and the query resolves against a tree that has not been
    // flushed yet.
    const button = await screen.findByRole("button", { name: "Rebuild" });
    await act(async () => {
      fireEvent.click(button);
    });
    await waitFor(() => expect(screen.getByText("Rebuild did not start")).toBeTruthy());
    expect(screen.getByText(/only one runs at a time/i)).toBeTruthy();
    expect(screen.queryByText("Rebuild could not be started")).toBeNull();
  });

  it("adopts a build already running when the page is opened", async () => {
    // THE NAVIGATE-AWAY-AND-BACK CASE. A build started by a publish keeps
    // running after its response returned and after the user went elsewhere.
    // The page recovers it from the server rather than from anything it
    // remembers, which is why a build started on another replica is visible too.
    report = consoleReport({
      active: {
        active: true,
        operation_id: "op-already-running",
        policy_set_key: "alpha",
        status: "running",
        stage: "rendering",
        stages: ["collecting", "rendering"],
        stage_index: 2,
        stage_total: 2,
      },
    });
    render(<PolicyIndexConsolePage />);

    await waitFor(() =>
      expect(
        requestedUrls.some((entry) => entry.includes("/api/policy-index/builds/op-already-running")),
      ).toBe(true),
    );
  });
});
