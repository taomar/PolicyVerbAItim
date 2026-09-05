import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import PolicyIndexProgressPanel, {
  buildHeadline,
  figureForStage,
} from "./PolicyIndexProgressPanel";
import type { PolicyIndexBuildProgress } from "../api";

/**
 * What this panel is for, and therefore what these tests are about.
 *
 * A policy index build re-renders every published policy through a model, embeds
 * the renderings and rewrites a search index. On a real project that is minutes,
 * and until this existed the only thing on screen was a spinning button — so a
 * publisher could not tell a slow render from a hung one, or say whether the
 * wait was in the model or in the index.
 *
 * THE RULE THE WHOLE SURFACE RESTS ON: TRUTHFUL, OR ABSENT
 *
 * Every figure here is one the server measured. Nothing is interpolated. There
 * is deliberately no percentage: the stages before rendering have no denominator
 * at all — how many documents a build will write is unknown until the corpus has
 * been rendered — so any bar spanning them would be a guess wearing the clothes
 * of a measurement, and precisely the number somebody uses to decide whether to
 * keep waiting.
 *
 * WHY SO MANY OF THESE TESTS ARE ABOUT ABSENCE
 *
 * A panel that invents a figure fails in the one direction a reader cannot
 * detect: a plausible number is indistinguishable from a real one. So the
 * assertions that matter most pin what must NOT appear — no percentage, an em
 * dash rather than 0 for an unmeasured count, no "done" marking on a stage still
 * running, and no failure language on a build that simply has not started.
 */

const OPERATION = "op-under-test";

/** The server's own pipeline. Kept as data the tests feed in, never imported
 *  from src, so a panel that quietly grew its own copy of the sequence would
 *  show up here as a disagreement rather than as agreement with itself. */
const STAGES = [
  "collecting",
  "rendering",
  "embedding",
  "indexing",
  "uploading",
  "sweeping",
  "validating",
  "publishing",
];

let polls: PolicyIndexBuildProgress[] = [];
let pollCount = 0;
let pollUrls: string[] = [];
let reducedMotion = false;

function progress(
  overrides: Partial<PolicyIndexBuildProgress> = {},
): PolicyIndexBuildProgress {
  return {
    active: true,
    operation_id: OPERATION,
    policy_set_key: "alpha",
    trigger: "rebuild",
    actor: null,
    status: "running",
    stage: "rendering",
    stages: STAGES,
    stage_index: 2,
    stage_total: STAGES.length,
    projection_count: 12,
    rendered_count: null,
    embedded_count: null,
    expected_document_count: null,
    acknowledged_count: null,
    swept_count: null,
    error: null,
    elapsed_seconds: 9,
    seconds_since_update: 1,
    terminal: false,
    recent: true,
    holds_build_slot: true,
    ...overrides,
  };
}

function queue(...readings: PolicyIndexBuildProgress[]) {
  polls = readings;
  pollCount = 0;
}

beforeEach(() => {
  polls = [];
  pollCount = 0;
  pollUrls = [];
  reducedMotion = false;

  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: query.includes("reduced-motion") ? reducedMotion : false,
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
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("the build's stages and counts", () => {
  it("reads the operation back from the server rather than trusting what it was handed", async () => {
    // This is what makes the panel survive navigating away and back: the record
    // is a row on the server, so a component mounted long after the build began
    // asks for it and gets the truth. A panel that rendered only its `initial`
    // prop would show whatever the previous page happened to know.
    queue(progress({ stage: "uploading", stage_index: 5, acknowledged_count: 40 }));
    render(<PolicyIndexProgressPanel operationId={OPERATION} />);

    await waitFor(() => expect(screen.getByTestId("policy-index-progress")).toBeTruthy());
    expect(pollUrls.some((url) => url.includes(`/api/policy-index/builds/${OPERATION}`))).toBe(
      true,
    );
    await waitFor(() => expect(screen.getByText("40")).toBeTruthy());
  });

  it("says which step of the pipeline is running, and it is a real position", async () => {
    queue(progress({ stage: "embedding", stage_index: 3 }));
    render(<PolicyIndexProgressPanel operationId={OPERATION} />);
    await waitFor(() => expect(screen.getByText(/step 3 of 8/)).toBeTruthy());
  });

  it("shows an em dash, never 0, for a count the build has not measured", async () => {
    // The load-bearing distinction. A project whose rendering has not started
    // and one that rendered nothing are different facts, and a panel that showed
    // both as 0 would report them identically.
    queue(progress({ rendered_count: null, projection_count: 12 }));
    const { container } = render(<PolicyIndexProgressPanel operationId={OPERATION} />);
    await waitFor(() => expect(screen.getByText("12")).toBeTruthy());

    const values = Array.from(container.querySelectorAll(".extract-stage-value")).map(
      (node) => node.textContent,
    );
    expect(values).toContain("—");
    // And specifically not a zero standing in for the absent measurement.
    expect(values.filter((v) => v === "0")).toHaveLength(0);
  });

  it("does not mark the running stage as done", async () => {
    // "Says finished when it is not" is the defect the whole surface exists to
    // remove, so it is pinned rather than assumed.
    queue(progress({ stage: "rendering", stage_index: 2 }));
    const { container } = render(<PolicyIndexProgressPanel operationId={OPERATION} />);
    await waitFor(() => expect(container.querySelector(".extract-stage--active")).toBeTruthy());

    const stages = Array.from(container.querySelectorAll(".extract-stage"));
    const active = stages.findIndex((node) => node.className.includes("extract-stage--active"));
    expect(active).toBe(1);
    expect(stages[active].className).not.toContain("extract-stage--done");
    // Everything before it is done; nothing after it is.
    expect(stages[0].className).toContain("extract-stage--done");
    expect(stages[2].className).not.toContain("extract-stage--done");
  });

  it("publishes the one real denominator, and only once the build has it", async () => {
    // Before rendering finishes nobody knows how many documents there will be,
    // so the line is absent rather than showing a total of zero.
    queue(progress({ expected_document_count: null }));
    render(<PolicyIndexProgressPanel operationId={OPERATION} />);
    await waitFor(() => expect(screen.getByText(/step 2 of 8/)).toBeTruthy());
    expect(screen.queryByText(/documents accepted/)).toBeNull();

    // A separate mount rather than a re-render of the unmounted one: the claim
    // is about what a build publishes at two different points in its life, not
    // about React reconciliation.
    cleanup();
    queue(
      progress({
        stage: "uploading",
        stage_index: 5,
        expected_document_count: 74,
        acknowledged_count: 61,
      }),
    );
    render(<PolicyIndexProgressPanel operationId={`${OPERATION}-2`} />);
    await waitFor(() =>
      expect(screen.getByText(/61 of 74 documents accepted/)).toBeTruthy(),
    );
  });
});

describe("what must never appear", () => {
  it("renders no percentage anywhere", async () => {
    // The thing most likely to be "improved" back in by somebody who has not
    // read why it is missing.
    queue(
      progress({
        stage: "uploading",
        stage_index: 5,
        expected_document_count: 74,
        acknowledged_count: 61,
      }),
    );
    const { container } = render(<PolicyIndexProgressPanel operationId={OPERATION} />);
    await waitFor(() => expect(screen.getByText(/61 of 74/)).toBeTruthy());

    expect(container.textContent).not.toMatch(/%/);
    expect(container.textContent).not.toMatch(/\bpercent/i);
    // Nor a progress bar element that a percentage would have to live in.
    expect(container.querySelector('[role="progressbar"]')).toBeNull();
  });

  it("renders nothing at all when there is no operation to watch", () => {
    const { container } = render(<PolicyIndexProgressPanel operationId={null} />);
    expect(container.textContent).toBe("");
  });

  it("renders nothing for an operation the server has no record of", async () => {
    // A page that navigated back before its build started must not show an
    // error where there is none. `active: false` is a normal answer.
    queue({ active: false } as PolicyIndexBuildProgress);
    const { container } = render(<PolicyIndexProgressPanel operationId={OPERATION} />);
    await waitFor(() => expect(pollUrls.length).toBeGreaterThan(0));
    expect(container.querySelector('[data-testid="policy-index-progress"]')).toBeNull();
  });
});

describe("terminal states", () => {
  it("reports a finished build as finished and stops polling", async () => {
    queue(progress({ status: "completed", stage: "publishing", stage_index: 8, terminal: true }));
    render(<PolicyIndexProgressPanel operationId={OPERATION} />);
    await waitFor(() => expect(screen.getByText(/Policy index rebuilt/)).toBeTruthy());

    const after = pollUrls.length;
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(pollUrls.length).toBe(after);
  });

  it("reports a failure with the server's own reason, and says nothing was lost", async () => {
    queue(
      progress({
        status: "failed",
        terminal: true,
        error: "Azure AI Search accepted 61 of 74 documents",
      }),
    );
    render(<PolicyIndexProgressPanel operationId={OPERATION} />);
    await waitFor(() =>
      expect(screen.getByText(/Policy index build did not finish/)).toBeTruthy(),
    );
    expect(screen.getByText(/61 of 74 documents/)).toBeTruthy();
    // The published policies are untouched by a failed index build, and the
    // panel says so — otherwise a failure here reads as data loss.
    expect(screen.getByText(/nothing was deleted/i)).toBeTruthy();
  });

  it("reports a build that never started as not started, not as a failure", async () => {
    // `deferred` is a different fact from `failed`, with a different repair:
    // wait for the running build to finish and retry, rather than investigate.
    // Painting it as a failure sends somebody looking for a fault that does not
    // exist.
    queue(
      progress({
        status: "deferred",
        stage: null,
        stage_index: 0,
        terminal: true,
        error: "another policy index build is already running",
      }),
    );
    const { container } = render(<PolicyIndexProgressPanel operationId={OPERATION} />);
    await waitFor(() =>
      expect(screen.getByText(/has not started yet/)).toBeTruthy(),
    );
    expect(screen.getByText(/only one runs at a time/i)).toBeTruthy();
    expect(container.textContent).not.toMatch(/did not finish/);
    // No pipeline is drawn: a build that never ran reached no stage, and drawing
    // eight greyed steps would imply it is somewhere in them.
    expect(container.querySelector(".extract-pipeline")).toBeNull();
  });

  it("warns when a build reported success but left the manifest unready", async () => {
    // The fact retrieval actually refuses on. A build that says "built" beside
    // an incomplete manifest is a project that will not answer, and finding that
    // out later as a case that will not run is the expensive way.
    queue(
      progress({
        status: "completed",
        terminal: true,
        stage: "publishing",
        stage_index: 8,
        manifest_state: "incomplete",
      }),
    );
    render(<PolicyIndexProgressPanel operationId={OPERATION} />);
    await waitFor(() => expect(screen.getByText(/manifest is incomplete/)).toBeTruthy());
  });
});

describe("accessibility", () => {
  it("has exactly one live region, and it is polite", async () => {
    // Exactly one: this panel sits inside pages with their own wait areas, and
    // nested live regions announce a change twice or ambiguously.
    queue(progress());
    const { container } = render(<PolicyIndexProgressPanel operationId={OPERATION} />);
    await waitFor(() => expect(screen.getByRole("status")).toBeTruthy());

    expect(container.querySelectorAll('[aria-live]')).toHaveLength(1);
    expect(screen.getByRole("status").getAttribute("aria-live")).toBe("polite");
  });

  it("keeps the animating figures out of the live region", async () => {
    // The stage figures count up frame by frame and the elapsed clock ticks.
    // Inside the announcement they would narrate every intermediate number.
    queue(progress({ acknowledged_count: 40, stage: "uploading", stage_index: 5 }));
    const { container } = render(<PolicyIndexProgressPanel operationId={OPERATION} />);
    await waitFor(() => expect(screen.getByRole("status")).toBeTruthy());

    const region = screen.getByRole("status");
    expect(region.querySelector(".extract-stage-value")).toBeNull();
    expect(region.querySelector(".extract-progress-counters")).toBeNull();
    // But they are on the page, reachable on demand.
    expect(container.querySelector(".extract-stage-value")).toBeTruthy();
  });

  it("shows the same figure under reduced motion, without animating to it", async () => {
    reducedMotion = true;
    queue(progress({ stage: "uploading", stage_index: 5, acknowledged_count: 61 }));
    render(<PolicyIndexProgressPanel operationId={OPERATION} />);
    // The reading is identical: the number is the content and the movement is
    // decoration on it. Under reduced motion the value is set directly, so it is
    // correct on the first paint rather than after a frame loop that this
    // environment does not run.
    await waitFor(() => expect(screen.getByText("61")).toBeTruthy());
  });

  it("names the project the build belongs to", async () => {
    // The slot is deployment-wide, so a panel that did not say which project is
    // being rebuilt would let an operator attribute the work to the page they
    // happen to be looking at.
    queue(progress({ policy_set_key: "alpha" }));
    render(<PolicyIndexProgressPanel operationId={OPERATION} />);
    await waitFor(() => expect(screen.getByText("alpha")).toBeTruthy());
  });
});

describe("the pure helpers", () => {
  it("gives a build that never ran its own sentence", () => {
    expect(buildHeadline({ active: true, status: "deferred" })).toMatch(/has not started/);
    expect(buildHeadline({ active: true, status: "failed", trigger: "publish" })).toMatch(
      /did not finish/,
    );
    // The trigger is carried into the wording, because "after publishing" and
    // "requested" are the two ways a build comes to exist and a history is much
    // harder to read without it.
    expect(buildHeadline({ active: true, status: "completed", trigger: "publish" })).toMatch(
      /after publishing/,
    );
    expect(buildHeadline({ active: true, status: "completed", trigger: "rebuild" })).toMatch(
      /requested/,
    );
  });

  it("reports no figure for a stage that measures nothing", () => {
    const reading = progress({ projection_count: 12, rendered_count: 4 });
    expect(figureForStage("collecting", reading)).toBe(12);
    expect(figureForStage("rendering", reading)).toBe(4);
    // `indexing` creates the index and moves the manifest. There is nothing to
    // count, so nothing is claimed — and `undefined` renders as an em dash.
    expect(figureForStage("indexing", reading)).toBeUndefined();
    expect(figureForStage("a-stage-that-does-not-exist", reading)).toBeUndefined();
  });
});
