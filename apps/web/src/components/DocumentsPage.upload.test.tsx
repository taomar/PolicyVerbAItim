import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { render } from "../testing/renderWithActor";
import { DocumentsPage } from "./DocumentsPage";
import {
  formatElapsed,
  formatFileSize,
  uploadOutcome,
  uploadWaitState,
} from "../uploadFeedback";

/**
 * While an upload is in flight the page must say something a reviewer can act
 * on, and when it finishes it must report what actually came back.
 *
 * The complaint this guards: the control showed a bare "Uploading…" for about
 * ninety seconds. No file, no size, no clock, no statement of what the server
 * was doing or what would happen next. The reviewer's real question during
 * that wait is not "how far along is it" — it is "is this still running, or
 * has it hung?", and nothing on screen answered that.
 *
 * WHAT MAKES THE CLOCK ASSERTION THE IMPORTANT ONE
 *
 * A presence check alone is weak here. A panel that renders a frozen "0:00"
 * satisfies "the elapsed time is shown" while failing the only thing the
 * elapsed time is for. So the test below advances fake timers and asserts the
 * rendered value CHANGED to a specific later value. If the interval is
 * removed, the panel still renders and still contains a clock, and this test
 * still fails — which is the point.
 *
 * FLOOR PLACEMENT
 *
 * The verdicts in this file are presence-and-value assertions, not an offender
 * list and not a set difference, so neither placement rule applies directly.
 * The equivalent risk is the one that has bitten this codebase before: a query
 * that matches nothing in BOTH the fixed and the broken build, so the test
 * "fails before and passes after" by accident of which assertion tripped
 * first. Two defences against that:
 *
 *   - every query goes through `screen`, which reads document.body, so a
 *     surface that moves into a portal is still found;
 *   - `renders the upload form at all` runs as its own test, so a wholesale
 *     render failure reports as a render failure rather than masquerading as a
 *     missing field.
 */

let resolveUpload: ((value: Response) => void) | null = null;

/** Bytes chosen to render as a clean, unambiguous "2.0 MB". */
const FILE_BYTES = 2 * 1024 * 1024;
const FILE_NAME = "staff-handbook.pdf";

/** Counts the stub endpoint reports back. Arbitrary, and never hardcoded in src. */
const CLAUSES_READ = 412;
const CLAUSES_INDEXED = 409;

function jsonResponse(body: unknown) {
  return {
    ok: true,
    status: 200,
    json: async () => body,
  } as unknown as Response;
}

function attachFile() {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  expect(input, "the upload control renders no file input").not.toBeNull();
  const file = new File(["x".repeat(64)], FILE_NAME, { type: "application/pdf" });
  // jsdom's File reports the byte length of its parts; the page reads
  // `file.size`, so pin it to the size this test reasons about.
  Object.defineProperty(file, "size", { value: FILE_BYTES });
  fireEvent.change(input, { target: { files: [file] } });
  return file;
}

/**
 * The whole wait area: the progress panel plus the one line the server cannot
 * know (what the reviewer gets when the request returns).
 *
 * This used to be reached with `findByRole("status")`, because the wrapper
 * carried `role="status"` and so the role happened to select the entire area.
 * That was an accessibility defect — the panel inside it is also a live region,
 * and nesting two means a stage change is announced twice or attributed to the
 * wrong region. The wrapper's role was removed and the panel is now the single
 * owner, which correctly makes the status role a much narrower element.
 *
 * So these tests ask the container for content and the role for announcement.
 * The distinction is the point: `waitArea()` is "what is on screen during the
 * wait", `findByRole("status")` is "what a screen reader is told about it".
 */
function waitArea(): HTMLElement {
  const area = document.querySelector(".upload-wait") as HTMLElement | null;
  expect(area, "the upload wait area is not on screen").not.toBeNull();
  return area as HTMLElement;
}

async function startUpload() {
  attachFile();
  // Title and Owner are required, and the page now enforces them before the
  // POST leaves (pinned in DocumentsPage.validation.test.tsx). These flow tests
  // are about what the reviewer is told DURING and AFTER a valid upload, so they
  // need a valid form to reach that state. Setting these satisfies a
  // newly-enforced precondition; it does not relax any assertion below — every
  // in-flight and returned-state check is unchanged.
  fireEvent.change(screen.getByPlaceholderText("Workplace Hardware Provisioning Policy"), {
    target: { value: "Staff Handbook" },
  });
  fireEvent.change(screen.getByPlaceholderText("it-team"), {
    target: { value: "hr-team" },
  });
  // The accessible name of this control is pinned separately by "renders the
  // upload form at all". Here the lookup reports what it actually saw when it
  // cannot find the button, because the interesting failures are the ones where
  // the button is present under a different label — "Reading document…" while a
  // previous request is still settling — and a bare timeout hides that.
  let button: HTMLButtonElement | null = null;
  await waitFor(
    () => {
      const buttons = Array.from(document.querySelectorAll("button"));
      const labels = buttons.map((b) => (b.textContent ?? "").trim());
      button = (buttons.find((b) => (b.textContent ?? "").trim() === "Upload") ??
        null) as HTMLButtonElement | null;
      expect(button, `no Upload button; buttons on screen: ${JSON.stringify(labels)}`).not.toBeNull();
      expect(
        (button as unknown as HTMLButtonElement).disabled,
        "the Upload button is present but disabled"
      ).toBe(false);
    },
    { timeout: 3000 }
  );
  await act(async () => {
    fireEvent.click(button as unknown as HTMLButtonElement);
  });
}

beforeEach(() => {
  resolveUpload = null;

  // antd measures the viewport; jsdom provides neither of these.
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
    }))
  );
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  );

  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      // Order matters. `/api/documents/upload-progress/...` is a prefix match
      // for `/api/documents/upload`, so a substring test alone routes every
      // progress poll into the deferred upload branch below — which hands the
      // panel an unresolved promise AND overwrites `resolveUpload`, so the test
      // then resolves a poll instead of the POST it meant to. Route the poll
      // first, and match the POST on its exact path.
      if (url.includes("/api/documents/upload-progress/")) {
        // Nothing tracked: the panel keeps its "Sending <file>" fallback, which
        // is what these tests assert against.
        return jsonResponse({ active: false });
      }
      if (url.includes("/api/documents/upload?") || url.endsWith("/api/documents/upload")) {
        // Held open so the in-flight state can be observed, exactly as it is
        // during the real ninety-second parse.
        return new Promise<Response>((resolve) => {
          resolveUpload = resolve;
        });
      }
      if (url.includes("/api/documents")) return jsonResponse([]);
      if (url.includes("/api/policy-sets")) return jsonResponse([]);
      return jsonResponse([]);
    })
  );
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("what the reviewer is told during the wait", () => {
  it("renders the upload form at all", async () => {
    render(<DocumentsPage />);
    expect(await screen.findByRole("button", { name: /^Upload$/ })).toBeTruthy();
    expect(document.querySelector('input[type="file"]')).not.toBeNull();
  });

  it("names the file and its size while the request is open", async () => {
    render(<DocumentsPage />);
    await startUpload();

    const area = waitArea();
    expect(area.textContent).toContain(FILE_NAME);
    expect(area.textContent).toContain("2.0 MB");
  });

  it("says what the server is doing and what happens next", async () => {
    render(<DocumentsPage />);
    await startUpload();

    const area = waitArea();
    // Not a verbatim copy of the sentences — that would only assert the string
    // equals itself. These are the two facts the sentences have to carry.
    expect(area.textContent).toMatch(/clause/i);
    expect(area.textContent).toMatch(/version/i);
  });

  it("announces the upload through exactly one live region", async () => {
    // The a11y invariant the change above exists to protect. Two nested live
    // regions announce a single change twice, or attribute it to the wrong
    // one; a reader cannot tell which reading is current. One owner, and the
    // ticking clock and animated counters stay outside it so a count-up is not
    // narrated digit by digit.
    render(<DocumentsPage />);
    await startUpload();

    const live = waitArea().querySelectorAll('[role="status"], [aria-live]');
    expect(live.length).toBe(1);
    expect(live[0].getAttribute("role")).toBe("status");
    expect(live[0].getAttribute("aria-live")).toBe("polite");
  });

  it("advances the elapsed clock, so a hung request is distinguishable from a slow one", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<DocumentsPage />);
    await startUpload();

    // The clock is omitted while it would read zero — a "0s elapsed" that
    // appears before any time has passed states a measurement of nothing. What
    // has to be true is that it then tracks wall time, so the reviewer can tell
    // a slow parse from a stopped one. Asserting the later value is what proves
    // that; a fixed string re-rendered would fail here.
    const atStart = waitArea().textContent ?? "";
    expect(atStart).not.toContain("1m 05s");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(65_000);
    });

    const later = waitArea().textContent ?? "";
    expect(later).toContain("1m 05s");
    expect(later).toContain("elapsed");
  });

  it("keeps the wait panel out of the way once the request returns", async () => {
    render(<DocumentsPage />);
    await startUpload();
    expect(await screen.findByRole("status")).toBeTruthy();

    await act(async () => {
      resolveUpload?.(
        jsonResponse({
          version_number: 3,
          clause_count: CLAUSES_READ,
          clauses_search_indexed: CLAUSES_INDEXED,
          extraction_error: null,
          ingestion_diagnostics: [],
        })
      );
    });

    await waitFor(() => {
      expect(screen.queryByRole("status")).toBeNull();
    });
  });
});

describe("what the reviewer is told when it returns", () => {
  it("reports how much was read out of the document", async () => {
    render(<DocumentsPage />);
    await startUpload();
    await act(async () => {
      resolveUpload?.(
        jsonResponse({
          version_number: 3,
          clause_count: CLAUSES_READ,
          clauses_search_indexed: CLAUSES_INDEXED,
          extraction_error: null,
          ingestion_diagnostics: [],
        })
      );
    });

    await waitFor(() => {
      expect(document.body.textContent).toContain(String(CLAUSES_READ));
    });
    // The search-indexed count differs from the read count here, so it is stated.
    expect(document.body.textContent).toContain(String(CLAUSES_INDEXED));
  });

  it("does not present a document that failed to read as a plain success", async () => {
    render(<DocumentsPage />);
    await startUpload();
    await act(async () => {
      resolveUpload?.(
        jsonResponse({
          version_number: 1,
          clause_count: 0,
          clauses_search_indexed: 0,
          extraction_error: "no extractable text layer",
          ingestion_diagnostics: [{ code: "scanned_pages", message: "12 pages carry no text layer" }],
        })
      );
    });

    await waitFor(() => {
      expect(document.body.textContent).toContain("no extractable text layer");
    });
    expect(document.body.textContent).toContain("12 pages carry no text layer");
  });

  it("shows an interleaving warning without presenting the upload as failed", async () => {
    // Text read across side-by-side columns loads fine and its clauses persist;
    // what it needs is for the author to be told, in the same breath as the
    // success, that the source file has to be corrected and re-uploaded. The
    // backend ships this as `detail` rather than `message`, so a reader that
    // only understood `message` would drop it silently.
    const warning =
      "3 word(s) across 2 passage(s) have the letters of two writing systems " +
      "alternating inside them (pages [2, 4]) — correct the layout in the original " +
      "PDF or Word file and upload it as a new version.";

    render(<DocumentsPage />);
    await startUpload();
    await act(async () => {
      resolveUpload?.(
        jsonResponse({
          version_number: 4,
          clause_count: CLAUSES_READ,
          clauses_search_indexed: CLAUSES_INDEXED,
          extraction_error: null,
          ingestion_diagnostics: [
            { code: "interleaved_text_not_reading_order", severity: "warning", detail: warning },
          ],
        })
      );
    });

    await waitFor(() => {
      expect(document.body.textContent).toContain("upload it as a new version");
    });
    // Actionable, not just present: it names the artefact to fix.
    expect(document.body.textContent).toContain("original");
    // And the upload is still reported as the success it was.
    expect(document.body.textContent).toContain(String(CLAUSES_READ));
  });
});

describe("the pure pieces", () => {
  it("formats sizes across unit boundaries", () => {
    expect(formatFileSize(0)).toBe("0 B");
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(1024)).toBe("1.0 KB");
    expect(formatFileSize(1024 * 1024)).toBe("1.0 MB");
    expect(formatFileSize(1024 * 1024 * 1024)).toBe("1.0 GB");
  });

  it("declines to state a size it cannot state honestly", () => {
    expect(formatFileSize(null)).toBeNull();
    expect(formatFileSize(undefined)).toBeNull();
    expect(formatFileSize(-1)).toBeNull();
    expect(formatFileSize(Number.NaN)).toBeNull();
  });

  it("omits the size from the headline rather than printing a placeholder", () => {
    const withSize = uploadWaitState("a.pdf", 2048, 0);
    const without = uploadWaitState("a.pdf", null, 0);
    expect(withSize.headline).toContain("2.0 KB");
    expect(without.headline).toContain("a.pdf");
    expect(without.headline).not.toMatch(/null|undefined|NaN/);
  });

  it("counts up in minutes and seconds and never goes negative", () => {
    expect(formatElapsed(0)).toBe("0:00");
    expect(formatElapsed(9_000)).toBe("0:09");
    expect(formatElapsed(65_000)).toBe("1:05");
    expect(formatElapsed(600_000)).toBe("10:00");
    expect(formatElapsed(-5_000)).toBe("0:00");
  });

  it("promises no percentage it cannot compute", () => {
    const state = uploadWaitState("a.pdf", 1024, 30_000);
    const allText = `${state.headline} ${state.activity} ${state.next}`;
    expect(allText).not.toMatch(/\d+\s?%/);
  });

  it("says nothing about counts the response did not carry", () => {
    const outcome = uploadOutcome("a.pdf", { version_number: 2 });
    expect(outcome.message).toContain("version 2");
    expect(outcome.message).not.toMatch(/clause/i);
    expect(outcome.problem).toBeNull();
    expect(outcome.notes).toEqual([]);
  });

  it("agrees singular and plural with the count", () => {
    expect(uploadOutcome("a.pdf", { version_number: 1, clause_count: 1 }).message).toContain("1 clause ");
    expect(uploadOutcome("a.pdf", { version_number: 1, clause_count: 2 }).message).toContain("2 clauses");
  });

  it("stays quiet about the search-indexed count when it matches the read count", () => {
    const same = uploadOutcome("a.pdf", { version_number: 1, clause_count: 7, clauses_search_indexed: 7 });
    expect(same.message).not.toMatch(/indexed for search/);
    const differs = uploadOutcome("a.pdf", { version_number: 1, clause_count: 7, clauses_search_indexed: 4 });
    expect(differs.message).toContain("4 indexed for search so far");
  });

  it("treats zero search-indexed clauses as a normal search state, not storage loss", () => {
    const outcome = uploadOutcome("a.pdf", { version_number: 1, clause_count: 7, clauses_search_indexed: 0 });
    expect(outcome.message).toContain("7 clauses read from it");
    expect(outcome.message).toContain("none indexed for search yet");
    // The count that was read is still stated, so a zero here cannot be read
    // as "nothing was stored" -- which is what the old field name asserted.
    expect(outcome.message).not.toMatch(/0 clauses/);
    expect(outcome.problem).toBeNull();
  });

  it("reads diagnostic notes whatever shape they arrive in", () => {
    const outcome = uploadOutcome("a.pdf", {
      version_number: 1,
      ingestion_diagnostics: [
        "a bare string",
        { message: "a message field" },
        { detail: "a detail field" },
        { code: "a_code_only" },
        { unrelated: 5 },
      ],
    });
    expect(outcome.notes).toEqual(["a bare string", "a message field", "a detail field", "a_code_only"]);
  });
});

/**
 * The progress panel is wired to the request it claims to describe.
 *
 * The failure this guards is quiet and total: the page generates an operation
 * id, sends one value with the POST and polls a different one. Every individual
 * piece then works -- the POST succeeds, the poll returns a well-formed
 * `{active: false}`, the panel renders its "Sending ..." fallback -- and the
 * reviewer watches a panel that is faithfully reporting an upload that is not
 * theirs. Nothing errors, so nothing else can catch it.
 */
describe("the progress panel watches the upload that is actually running", () => {
  it("polls the same operation id it sent with the POST", async () => {
    render(<DocumentsPage />);
    await startUpload();

    const calls = (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    const urls = calls.map((c) => String(c[0]));

    const post = urls.find((u) => u.includes("/api/documents/upload?"));
    expect(post, "no upload POST was issued").toBeTruthy();
    const sent = new URL(post as string, "http://localhost").searchParams.get("operation_id");
    expect(sent, "the POST carried no operation_id").toBeTruthy();

    await waitFor(() => {
      const polled = urls.concat(
        (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls.map((c) =>
          String(c[0])
        )
      );
      expect(
        polled.some((u) => u.includes(`/api/documents/upload-progress/${sent}`)),
        "the panel polled no progress endpoint for the id it sent"
      ).toBe(true);
    });
  });

  it("keeps the returned result on screen after the panel goes away", async () => {
    // The panel is mounted only while the request is open, so completion is
    // owned by the result line rather than by an animated final stage the
    // reviewer would never be present to see. That division is only safe if the
    // result is definitely there once the panel is not.
    render(<DocumentsPage />);
    await startUpload();

    expect(screen.getByText(`Sending ${FILE_NAME}`)).toBeTruthy();

    await act(async () => {
      resolveUpload?.(
        jsonResponse({
          version_number: 3,
          clause_count: CLAUSES_READ,
          clauses_search_indexed: CLAUSES_INDEXED,
          duplicate_of: [],
        })
      );
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(screen.queryByText(`Sending ${FILE_NAME}`)).toBeNull();
    });
    expect(await screen.findByText(new RegExp(`${CLAUSES_READ} clauses read from it`))).toBeTruthy();
    expect(document.body.textContent).toContain("version 3");
  });

  it("does not leave a stale operation id watching the next upload", async () => {
    // A second upload must not inherit the first one's id, or its panel reports
    // the previous document's stages.
    render(<DocumentsPage />);
    await startUpload();
    const first = new URL(
      (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls
        .map((c) => String(c[0]))
        .find((u) => u.includes("/api/documents/upload?")) as string,
      "http://localhost"
    ).searchParams.get("operation_id");

    await act(async () => {
      resolveUpload?.(jsonResponse({ version_number: 1, duplicate_of: [] }));
      await Promise.resolve();
    });
    // Waiting for the panel to go is not enough to start a second upload. The
    // page clears the file — which unmounts the panel — before it refreshes the
    // list and before `finally` restores `uploading` to false, so for a moment
    // the panel is gone while the button still reads "Reading document…". Wait
    // for the control that actually gates a second upload. This is an ordering
    // fact about the page, not something to be fixed by reordering production
    // state resets to suit a test.
    await waitFor(() => expect(screen.queryByText(`Sending ${FILE_NAME}`)).toBeNull());
    await waitFor(
      () => {
        const labels = Array.from(document.querySelectorAll("button")).map((b) =>
          (b.textContent ?? "").trim()
        );
        expect(labels, `buttons on screen: ${JSON.stringify(labels)}`).toContain("Upload");
      },
      { timeout: 3000 }
    );

    await startUpload();
    const posts = (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls
      .map((c) => String(c[0]))
      .filter((u) => u.includes("/api/documents/upload?"));
    expect(posts.length).toBe(2);
    const second = new URL(posts[1], "http://localhost").searchParams.get("operation_id");
    expect(second).toBeTruthy();
    expect(second).not.toBe(first);
  });
});
