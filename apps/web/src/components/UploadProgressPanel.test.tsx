import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import UploadProgressPanel from "./UploadProgressPanel";
import type { UploadProgress } from "../api";

/**
 * What this panel is for, and therefore what these tests are about.
 *
 * The complaint it answers: uploading a policy document showed a bare
 * "Uploading…" for a minute and a half. The reviewer's question during that
 * wait is not "how far along is it" — it is "is this still running, or has it
 * hung?" A spinner cannot answer that, and neither can a progress bar built
 * from elapsed time, because such a bar keeps moving while the work is dead.
 *
 * THE RULE THE WHOLE SURFACE RESTS ON: TRUTHFUL, OR ABSENT
 *
 * Every figure here is one the server measured. Nothing is interpolated. There
 * is deliberately no percentage and no bar: the request has no denominator
 * until the parse ends, so any bar would be a guess wearing the clothes of a
 * measurement — and precisely the number someone uses to decide whether to keep
 * waiting. `there is no percentage anywhere` below pins that, because it is the
 * kind of thing that gets "improved" back in by someone who has not read this.
 *
 * WHY SO MANY TESTS ARE ABOUT ABSENCE
 *
 * A panel that invents a figure fails in the one direction a reader cannot
 * detect: a plausible number is indistinguishable from a real one. So the
 * assertions that matter most here are the ones that pin what must NOT appear —
 * no percentage, an em dash rather than 0 for an unmeasured count, no "done"
 * marking on a stage still running, and no quiet warning on a healthy upload
 * whose only anomaly is a client clock that disagrees with the server's.
 */

const OPERATION = "op-under-test";
const FILE = "staff-handbook.pdf";
const FILE_BYTES = 2 * 1024 * 1024;

/** The server's own pipeline. Kept as data the tests feed in, never imported
 *  from src, so a panel that quietly grew its own copy of the sequence would
 *  show up here as a disagreement rather than as agreement with itself. */
const STAGES = ["storing", "reading", "checking", "saving", "indexing"];

let polls: UploadProgress[] = [];
let pollCount = 0;
let pollUrls: string[] = [];

function progress(overrides: Partial<UploadProgress> = {}): UploadProgress {
  return {
    active: true,
    operation_id: OPERATION,
    status: "running",
    stage: "reading",
    stages: STAGES,
    stage_index: 2,
    stage_total: STAGES.length,
    file_bytes: FILE_BYTES,
    clause_count: null,
    indexed_count: null,
    warning_count: null,
    has_interleaved_warning: false,
    error: null,
    started_at: 1_700_000_000,
    updated_at: 1_700_000_000,
    elapsed_seconds: 3,
    ...overrides,
  };
}

/** Serve the queued readings in order, repeating the last one so a component
 *  that polls once more than expected still gets a coherent answer rather than
 *  a crash that would be misread as a rendering fault. */
function queue(...readings: UploadProgress[]) {
  polls = readings;
  pollCount = 0;
}

beforeEach(() => {
  polls = [];
  pollCount = 0;
  pollUrls = [];

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
      pollUrls.push(url);
      const reading = polls[Math.min(pollCount, polls.length - 1)] ?? { active: false };
      pollCount += 1;
      return {
        ok: true,
        status: 200,
        // A fresh object per poll, as `res.json()` gives in production. Handing
        // back the same reference would make React skip the re-render and the
        // panel would look stuck for a reason no user could ever hit.
        json: async () => ({ ...reading }),
      } as unknown as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function renderPanel(overrides: Record<string, unknown> = {}) {
  return render(
    <UploadProgressPanel
      running
      operationId={OPERATION}
      fileName={FILE}
      fileSizeBytes={FILE_BYTES}
      elapsedMs={7000}
      {...overrides}
    />
  );
}

/** Wait for the first poll to have been rendered. */
async function settle() {
  await waitFor(() => expect(pollCount).toBeGreaterThan(0));
  await act(async () => {
    await Promise.resolve();
  });
}

describe("before the server has said anything", () => {
  it("says the file is being sent, and claims no share of the transfer", async () => {
    // The honest statement in this window is narrow: the browser is sending the
    // body and the handler has not started. `fetch` does not report upload
    // progress for a body of this kind, so any "43% sent" here would be
    // invented.
    queue({ active: false } as UploadProgress);
    renderPanel();
    await settle();

    expect(screen.getByText(`Sending ${FILE}`)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/%/);
  });

  it("shows the measured size and elapsed time, which are real", async () => {
    queue({ active: false } as UploadProgress);
    renderPanel();
    await settle();

    expect(document.body.textContent).toContain("2.0 MB");
    expect(document.body.textContent).toContain("elapsed");
  });

  it("does not poll at all without an operation id", async () => {
    renderPanel({ operationId: null });
    await act(async () => {
      await Promise.resolve();
    });
    expect(pollCount).toBe(0);
  });
});

describe("the stage pipeline reports what the server reported", () => {
  it("polls the operation id it was given", async () => {
    queue(progress());
    renderPanel();
    await settle();

    expect(pollUrls.some((u) => u.includes(OPERATION))).toBe(true);
    expect(pollUrls.every((u) => u.includes("/api/documents/upload-progress/"))).toBe(true);
  });

  it("marks the current stage active and only earlier ones done", async () => {
    // stage_index 3 == "checking". "storing" and "reading" are behind it and
    // done; "checking" is running; "saving" and "indexing" have not begun. A
    // stage drawn done while it is still the live one is the "says finished
    // when it is not" defect this pipeline exists to avoid.
    queue(progress({ stage: "checking", stage_index: 3 }));
    renderPanel();
    await settle();

    const active = document.querySelectorAll(".extract-stage--active");
    const done = document.querySelectorAll(".extract-stage--done");
    expect(active.length).toBe(1);
    expect(active[0].textContent).toContain("checks");
    expect(done.length).toBe(2);
  });

  it("states the step position rather than a fraction of the work", async () => {
    queue(progress({ stage: "saving", stage_index: 4 }));
    renderPanel();
    await settle();

    expect(document.body.textContent).toContain("step 4 of 5");
  });

  it("shows an em dash, never 0, for a count the server has not measured", async () => {
    // The distinction is load-bearing. `null` means "not measured yet"; `0`
    // means "none found". A document nobody has read and a document with no
    // clauses are different facts and must not render identically.
    queue(progress({ clause_count: null, indexed_count: null, warning_count: null }));
    renderPanel();
    await settle();

    const values = Array.from(document.querySelectorAll(".extract-stage-value")).map(
      (n) => n.textContent
    );
    expect(values.filter((v) => v === "—").length).toBeGreaterThan(0);
    expect(values).not.toContain("0");
  });

  it("shows a real zero once the server has measured one", async () => {
    // The other half of the same rule: a measured zero is a finding and must be
    // shown as one, not hidden behind the same dash that means "unknown".
    vi.useFakeTimers();
    queue(progress({ stage: "indexing", stage_index: 5, clause_count: 8, indexed_count: 0 }));
    renderPanel();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200);
    });

    const values = Array.from(document.querySelectorAll(".extract-stage-value")).map(
      (n) => n.textContent
    );
    expect(values).toContain("0");
  });

  it("never renders a percentage or a progress bar", async () => {
    // The rule the whole surface rests on. If this fails, someone has added an
    // interpolated figure and the panel has stopped being a measurement.
    queue(progress({ stage: "reading", stage_index: 2, clause_count: 412 }));
    renderPanel();
    await settle();

    expect(document.body.textContent).not.toMatch(/%/);
    expect(document.querySelector(".ant-progress")).toBeNull();
    expect(document.querySelector("progress")).toBeNull();
    expect(document.querySelector('[role="progressbar"]')).toBeNull();
  });
});

describe("the interleaved-text warning", () => {
  it("is shown, and says to fix the source file", async () => {
    queue(progress({ has_interleaved_warning: true, warning_count: 3 }));
    renderPanel();
    await settle();

    expect(screen.getByText(/interleaved text found in the source file/i)).toBeTruthy();
  });

  it("is absent when the server did not report one", async () => {
    // The control. A tag that renders unconditionally would satisfy the test
    // above while telling every uploader their document is damaged.
    queue(progress({ has_interleaved_warning: false }));
    renderPanel();
    await settle();

    expect(screen.queryByText(/interleaved text found/i)).toBeNull();
  });

  it("does not present the upload as failed", async () => {
    // Informational means informational: the warning is not an error state and
    // must not colour the panel as one, or the reviewer will read a successful
    // load as a broken one.
    queue(progress({ has_interleaved_warning: true, warning_count: 2 }));
    const { container } = renderPanel();
    await settle();

    expect(container.querySelector(".extract-progress--failed")).toBeNull();
    expect(screen.queryByText(/Could not read/)).toBeNull();
  });
});

describe("terminal states", () => {
  it("renders the completed state, and it is reachable", async () => {
    // Guards against claiming a completion the reader can never see. The panel
    // is asserted to render `Finished …` from a terminal poll while still
    // mounted; DocumentsPage.upload.test.tsx owns what replaces it afterwards.
    queue(progress({ status: "completed", stage: "indexing", stage_index: 5, clause_count: 412, indexed_count: 409 }));
    renderPanel();
    await settle();

    expect(screen.getByText(`Finished ${FILE}`)).toBeTruthy();
    // Every stage reads done on completion; none is left mid-flight.
    expect(document.querySelectorAll(".extract-stage--active").length).toBe(0);
    expect(document.querySelectorAll(".extract-stage--done").length).toBe(STAGES.length);
  });

  it("renders the failure with the reason, and says the file was kept", async () => {
    queue(
      progress({
        status: "failed",
        stage: "reading",
        stage_index: 2,
        error: "cannot open PDF: No /Root object",
      })
    );
    const { container } = renderPanel();
    await settle();

    expect(screen.getByText(`Could not read ${FILE}`)).toBeTruthy();
    expect(document.body.textContent).toContain("cannot open PDF: No /Root object");
    // The sentence that stops a reviewer re-uploading needlessly.
    expect(document.body.textContent).toMatch(/stored and kept/i);
    expect(container.querySelector(".extract-progress--failed")).not.toBeNull();
  });

  it("stops polling once the status is terminal", async () => {
    // Finished records are retained for minutes so the last poll can read them,
    // so `active` stays true after the end. Keying on it would poll a finished
    // upload for the whole retention window.
    vi.useFakeTimers();
    queue(progress({ status: "completed", stage: "indexing", stage_index: 5 }));
    renderPanel();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    const afterFirst = pollCount;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(pollCount).toBe(afterFirst);
  });

  it("stops polling when it unmounts mid-upload", async () => {
    vi.useFakeTimers();
    queue(progress({ status: "running" }));
    const { unmount } = renderPanel();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });

    unmount();
    const atUnmount = pollCount;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(pollCount).toBe(atUnmount);
  });

  it("keeps its last reading when a poll fails", async () => {
    // A failed poll is a fact about the network, not about the upload, and must
    // never be shown as a failed upload.
    vi.useFakeTimers();
    queue(progress({ stage: "reading", stage_index: 2, clause_count: 412 }));
    renderPanel();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    expect(document.body.textContent).toContain("step 2 of 5");

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      })
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(document.body.textContent).toContain("step 2 of 5");
    expect(screen.queryByText(/Could not read/)).toBeNull();
  });
});

describe("the quiet warning is computed from server time only", () => {
  /** Server says: started 600s ago, last wrote 590s ago -> quiet for 590s. */
  const quietReading = progress({
    started_at: 1_000_000,
    updated_at: 1_000_010,
    elapsed_seconds: 600,
  });

  /** Server says: started 600s ago, wrote 1s ago -> healthy, whatever the
   *  client's clock believes. */
  const healthyReading = progress({
    started_at: 1_000_000,
    updated_at: 1_000_599,
    elapsed_seconds: 600,
  });

  /** Advance one poll interval at a time.
   *
   *  This matters. The quiet counter increments once per render in which the
   *  reading was quiet, and in production each poll lands in its own tick and
   *  therefore its own render. Collapsing five seconds into a single timer jump
   *  lets React batch several polls into one render, so the counter would see
   *  one reading where a real browser sees five — a harness artifact that would
   *  read as a panel that never flags a stall. */
  async function pollTimes(count: number) {
    for (let i = 0; i < count; i += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1100);
      });
    }
  }

  it("reports a genuinely stalled upload after two consecutive quiet polls", async () => {
    vi.useFakeTimers();
    queue(quietReading);
    const { container } = renderPanel();
    await pollTimes(3);

    // Pinned so a failure below distinguishes "the panel did not flag it" from
    // "the harness never delivered enough readings to flag".
    expect(pollCount).toBeGreaterThanOrEqual(2);
    expect(container.firstElementChild?.className).toContain("extract-progress--quiet");
    expect(document.body.textContent).toMatch(/No update for/i);
    // The copy states the measured gap, not a verdict: a long single-pass parse
    // legitimately looks like this and must not be reported as a stopped upload.
    expect(document.body.textContent).toMatch(/long parse rather than a stopped upload/i);
  });

  it("does not report quiet on a single reading", async () => {
    // One slow poll is not evidence of a stall, and a panel that says so will
    // be disbelieved when it matters.
    vi.useFakeTimers();
    queue(quietReading, healthyReading, healthyReading);
    renderPanel();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });

    expect(document.body.textContent).not.toMatch(/No update for/i);
  });

  it("is unaffected by a client clock hours away from the server's", async () => {
    // The defect this replaced: quiet time computed as client `Date.now()`
    // minus the server's `updated_at`. A browser a few minutes ahead marked
    // every healthy upload quiet on its first poll; a browser behind never
    // reported a real stall. Both readings were wrong for a reason that has
    // nothing to do with the upload, and neither was visible to the reader.
    //
    // These timestamps are ~1970 in client terms, so a client-clock
    // computation would put the last write about fifty-five years ago.
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-06-01T12:00:00Z"));
    queue(healthyReading, healthyReading, healthyReading);
    renderPanel();
    await pollTimes(4);

    expect(pollCount).toBeGreaterThanOrEqual(3);
    expect(document.body.textContent).not.toMatch(/No update for/i);
  });

  it("clears the quiet state once the upload finishes", async () => {
    vi.useFakeTimers();
    queue(
      quietReading,
      quietReading,
      quietReading,
      progress({ status: "completed", stage: "indexing", stage_index: 5 })
    );
    renderPanel();
    await pollTimes(5);

    expect(document.body.textContent).not.toMatch(/No update for/i);
    expect(screen.getByText(`Finished ${FILE}`)).toBeTruthy();
  });
});

describe("the reading survives without animation", () => {
  it("settles counts without an animation frame under reduced motion", async () => {
    // A real reduced-motion control, not an assumption. `matchMedia` is stubbed
    // to report the reduce preference, `requestAnimationFrame` is watched, and
    // the assertion is that the figures are correct anyway AND that no frame was
    // ever requested to get them there. Motion here decorates a real number; it
    // must never be the thing that carries it.
    const frames = vi.fn((cb: FrameRequestCallback) => {
      cb(0);
      return 1;
    });
    vi.stubGlobal("requestAnimationFrame", frames);
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("prefers-reduced-motion"),
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    );

    queue(
      progress({ stage: "reading", stage_index: 2, clause_count: 100 }),
      progress({ stage: "indexing", stage_index: 5, clause_count: 412, indexed_count: 409 })
    );
    renderPanel();
    await settle();
    await waitFor(() => expect(pollCount).toBeGreaterThanOrEqual(2));
    await waitFor(() => {
      const values = Array.from(document.querySelectorAll(".extract-stage-value")).map(
        (n) => n.textContent
      );
      expect(values).toContain("412");
    });

    const values = Array.from(document.querySelectorAll(".extract-stage-value")).map(
      (n) => n.textContent
    );
    expect(values).toContain("409");
    expect(frames).not.toHaveBeenCalled();
  });

  it("shows the final counts when motion is allowed too", async () => {
    // The control for the control: with reduced motion off, the same figures
    // must still arrive. A count-up that never settles on the real value would
    // pass the test above and fail every sighted reader.
    queue(progress({ stage: "indexing", stage_index: 5, clause_count: 412, indexed_count: 409 }));
    renderPanel();
    await settle();

    const values = Array.from(document.querySelectorAll(".extract-stage-value")).map(
      (n) => n.textContent
    );
    expect(values).toContain("412");
    expect(values).toContain("409");
  });

  it("announces its state through exactly one live region", async () => {
    // Nested live regions are the defect this pins. The panel renders inside the
    // page's upload wait area, and if both are live a screen reader announces a
    // stage change twice, or attributes it to the wrong region. There must be
    // one owner, and the animated pipeline and ticking clock must sit outside
    // it so a count-up is not narrated digit by digit.
    queue(progress());
    const { container } = renderPanel();
    await settle();

    const live = container.querySelectorAll('[role="status"], [aria-live]');
    expect(live.length).toBe(1);
    // Both halves are asserted: a region that announces (`status`) and one that
    // announces politely. Checking only `aria-live` would accept a role that
    // does not announce at all, which is a change no rendered assertion here
    // would otherwise notice.
    expect(live[0].getAttribute("role")).toBe("status");
    expect(live[0].getAttribute("aria-live")).toBe("polite");
    // The state it announces, and not the figures that churn.
    expect(live[0].textContent).toContain(`Reading ${FILE}`);
    expect(live[0].textContent).not.toContain("elapsed");
    expect(live[0].querySelector(".extract-stage-value")).toBeNull();
  });

  it("announces a failure through that same single region", async () => {
    queue(progress({ status: "failed", stage: "reading", stage_index: 2, error: "no /Root object" }));
    const { container } = renderPanel();
    await settle();

    const live = container.querySelectorAll('[role="status"], [aria-live]');
    expect(live.length).toBe(1);
    expect(live[0].textContent).toContain(`Could not read ${FILE}`);
    expect(live[0].textContent).toContain("no /Root object");
  });
});
